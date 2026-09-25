#!/usr/bin/env python3
"""Collect once, probe disjoint shards, publish only a complete matching run."""
from __future__ import annotations
import argparse, dataclasses, datetime as dt, hashlib, json, os, shutil, subprocess, sys, time
from collections import defaultdict
from pathlib import Path
from urllib.parse import urlsplit
if __package__:
 from . import update as u
else:
 import update as u


def plan_digest(plan):
 return hashlib.sha256(json.dumps({k:v for k,v in plan.items() if k!='id'},sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def split_hosts(selected,count):
 """Keep a host in one shard so the two-probe host cap is global."""
 hosts=defaultdict(list)
 for c in selected:hosts[urlsplit(c.url).hostname].append(c.url)
 batches=[[] for _ in range(count)]
 for host,urls in sorted(hosts.items(),key=lambda kv:(-len(kv[1]),kv[0])):
  idx=min(range(count),key=lambda i:len(batches[i]));batches[idx].extend(urls)
 return batches


def create_plan(root,limit=None):
 settings=json.loads((root/'config/settings.json').read_text())
 if limit is not None:settings['max_candidates']=limit
 if not 1<=settings['max_candidates']<=5000 or not 1<=settings['workers']<=24 or not 8<=settings['sample_seconds']<=60 or not 1<=settings.get('shards',4)<=8:
  raise ValueError('settings out of bounds')
 sources=json.loads((root/'config/sources.json').read_text())
 items,source_results=u.collect(sources,root);previous=[]
 if (root/'reports/channels.json').exists():
  previous_rows=json.loads((root/'reports/channels.json').read_text())['channels']
  previous=[r['url'] for r in previous_rows]
  items=u.restore_previous(items,previous_rows,{s['url'] for s in sources if s.get('enabled',True)})
 selected=u.select_channels(items,settings['max_candidates'],previous,priority_channels=settings.get('priority_channels',()),priority_regions=settings.get('priority_regions',()))
 if not selected:raise ValueError('no candidates; previous playlists must not be replaced')
 plan={'created_at':u.utcnow(),'settings':settings,'sources':source_results,'candidate_urls':len(items),'selected':[dataclasses.asdict(c) for c in selected],'batches':split_hosts(selected,settings.get('shards',4))}
 plan['id']=plan_digest(plan)
 return plan


def read_plan(path):
 plan=json.loads(path.read_text())
 if plan.get('id')!=plan_digest(plan):raise ValueError('plan fingerprint mismatch')
 urls=[r['url'] for r in plan['selected']];assigned=[x for b in plan['batches'] for x in b]
 if len(urls)!=len(set(urls)) or len(assigned)!=len(set(assigned)) or set(urls)!=set(assigned):raise ValueError('invalid or duplicate shard assignments')
 return plan


def run_shard(plan,index,ffmpeg='ffmpeg'):
 if not 0<=index<len(plan['batches']):raise ValueError('invalid shard index')
 binary=shutil.which(ffmpeg)
 if not binary:raise ValueError('ffmpeg is required')
 if not shutil.which('tesseract'):raise ValueError('tesseract is required; refusing to lower checks')
 p=subprocess.run(['tesseract','--list-langs'],capture_output=True,text=True,timeout=10)
 if p.returncode or not {'chi_sim','eng'}.issubset(p.stdout.split()):raise ValueError('tesseract chi_sim and eng are required')
 urls=set(plan['batches'][index]);selected=[u.Channel(**r) for r in plan['selected'] if r['url'] in urls]
 results=u.probe_many(selected,plan['settings'],binary,True)
 return {'plan_id':plan['id'],'shard_index':index,'ocr_enabled':True,'completed_at':u.utcnow(),'results':results}


def validate_results(plan,parts):
 if len(parts)!=len(plan['batches']):raise ValueError('missing or extra shards; refusing partial publication')
 by_index={p['shard_index']:p for p in parts}
 if set(by_index)!=set(range(len(plan['batches']))):raise ValueError('duplicate or invalid shard index')
 planned={r['url']:r for r in plan['selected']};results=[]
 for index,urls in enumerate(plan['batches']):
  part=by_index[index]
  if part['plan_id']!=plan['id'] or part.get('ocr_enabled') is not True:raise ValueError('stale plan or OCR disabled')
  rows=part['results'];actual=[r['url'] for r in rows]
  if len(actual)!=len(urls) or set(actual)!=set(urls):raise ValueError('missing, duplicate or unexpected probe results')
  for r in rows:
   if r.get('ok') is True and (r.get('ocr_checked') is not True or r.get('seconds',0)<plan['settings']['sample_seconds']-.5):raise ValueError('passing result lacks required validation evidence')
   if not isinstance(r.get('ok'),bool) or not r.get('checked_at'):raise ValueError('invalid probe result')
   # Preserve the collected identity and provenance rather than trusting part metadata.
   results.append({**r,**planned[r['url']]})
 return sorted(results,key=lambda r:(r['region'],u.key(r['name']),r['url']))


def merge_results(root,plan,parts):
 results=validate_results(plan,parts)
 age=(dt.datetime.now(dt.timezone.utc)-dt.datetime.fromisoformat(plan['created_at'])).total_seconds()
 if not 0<=age<=6*3600:raise ValueError('plan expired; refusing stale publication')
 settings={**plan['settings'],'ocr_enabled':True}
 return u.publish(root,results,plan['sources'],plan['candidate_urls'],len(plan['selected']),settings,time.monotonic()-age)


def main():
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('stage',choices=['plan','probe','merge']);ap.add_argument('--root',type=Path,default=u.ROOT)
 ap.add_argument('--plan',type=Path,default=Path('work/plan.json'));ap.add_argument('--limit',type=int)
 ap.add_argument('--index',type=int);ap.add_argument('--result',type=Path);ap.add_argument('--results',type=Path,default=Path('work/results'))
 ap.add_argument('--ffmpeg',default=os.getenv('FFMPEG','ffmpeg'))
 args=ap.parse_args();root=args.root.resolve()
 if args.stage=='plan':
  plan=create_plan(root,args.limit);u.json_write(args.plan,plan)
  output={'candidates':plan['candidate_urls'],'selected':len(plan['selected']),'shard_sizes':[len(b) for b in plan['batches']],'upstreams':len(plan['sources']),'requested_candidates':sum(u.key(c['name']) in {u.key(n) for n in plan['settings'].get('priority_channels',[])} for c in plan['selected'])}
  if os.getenv('GITHUB_OUTPUT'):
   with open(os.environ['GITHUB_OUTPUT'],'a') as f:f.write('matrix='+json.dumps(list(range(len(plan['batches']))))+'\n')
 elif args.stage=='probe':
  if args.index is None or not args.result:ap.error('--index and --result are required')
  output=run_shard(read_plan(args.plan),args.index,args.ffmpeg);u.json_write(args.result,output)
  output={'shard':args.index,'tested':len(output['results']),'passed':sum(r['ok'] for r in output['results'])}
 else:
  output=merge_results(root,read_plan(args.plan),[json.loads(p.read_text()) for p in sorted(args.results.glob('part-*.json'))])
 print(json.dumps(output,ensure_ascii=False),flush=True)
 return 2 if output.get('state')=='failed_no_channels' else 0

if __name__=='__main__':sys.exit(main())
