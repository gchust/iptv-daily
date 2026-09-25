#!/usr/bin/env python3
"""Verify custom priority candidates using the same strict media/OCR pipeline."""
import dataclasses,json,os,sys
from pathlib import Path
if __package__:
 from . import update as u
 from . import pipeline as p
else:
 import update as u
 import pipeline as p


def create_priority_plan(root):
 settings=json.loads((root/'config/settings.json').read_text())
 settings.update(sample_seconds=60,probe_timeout_seconds=100,shards=1)
 names={u.key(n) for n in settings.get('priority_channels',())}
 custom=root/'data/custom.m3u'
 candidates=u.parse_playlist(custom.read_text(),'data/custom.m3u',True)
 unique={c.url:c for c in candidates if u.key(c.name) in names}
 if not unique:raise ValueError('No custom priority candidates configured')
 selected=list(unique.values())
 plan={'created_at':u.utcnow(),'settings':settings,'sources':[{'name':'Custom priority candidates','url':'data/custom.m3u','ok':True,'candidates':len(selected)}],'candidate_urls':len(selected),'selected':[dataclasses.asdict(c) for c in selected],'batches':[[c.url for c in selected]]}
 plan['id']=p.plan_digest(plan)
 return plan


def main():
 root=u.ROOT
 plan=create_priority_plan(root)
 u.json_write(root/'work/priority-plan.json',plan)
 part=p.run_shard(plan,0,os.getenv('FFMPEG','ffmpeg'))
 u.json_write(root/'work/priority-part.json',part)
 results=p.validate_results(plan,[part])
 report=u.publish_priority(root,results,{**plan['settings'],'ocr_enabled':True})
 print(json.dumps({k:v for k,v in report.items() if k not in ('results','channels','content_reviews')},ensure_ascii=False))
 return 0 if report['state']=='ok' else 2

if __name__=='__main__':sys.exit(main())
