#!/usr/bin/env python3
"""Collect public TV candidates, decode real media, publish only current passes."""
from __future__ import annotations
import argparse, concurrent.futures, dataclasses, datetime as dt, hashlib, ipaddress
import json, math, os, re, shutil, subprocess, sys, tempfile, time, unicodedata, threading
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import urlsplit, urljoin
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
UA = 'Mozilla/5.0 IPTV-Daily/1.0'
OCR_SLOTS = threading.BoundedSemaphore(2)
EXCLUDED_KINDS = {'广播','慢直播','影视轮播'}
REGIONS = {
 '湖北':['湖北','武汉','江夏','宜昌','长阳','荆州','十堰','咸宁','襄阳','荆门','仙桃','潜江','随州','恩施','黄石','黄冈','麻城','保康','通山','远安','汉川','蕲春','鄂州','天门','神农架','阳新','房县','大冶','团风','浠水','英山','红安','嘉鱼','赤壁','崇阳','通城','巴东','利川','建始','宣恩','咸丰','来凤','鹤峰','枝江','当阳','宜都','秭归','兴山','五峰','罗田','武穴','黄梅','竹山','竹溪','郧阳','郧西','丹江口','钟祥','京山','沙洋','应城','安陆','云梦','孝昌','大悟','汉南','蔡甸'],
 '广东':['广东','广州','深圳','佛山','东莞','珠海','潮州','揭阳','汕头','江门','惠州','肇庆','湛江','茂名','中山','梅州','清远','韶关','河源','阳江','汕尾','云浮'],
 '浙江':['浙江','杭州','宁波','温州','绍兴','嘉兴','湖州','金华','台州','舟山','衢州','丽水','义乌','余姚','诸暨','海宁','桐乡','临海','瑞安','乐清'],
 '江苏':['江苏','南京','苏州','无锡','常州','镇江','扬州','南通','泰州','徐州','盐城','淮安','连云港','宿迁','昆山','常熟','江阴','宜兴'],
 '福建':['福建','厦门','福州','泉州','漳州','莆田','三明','南平','龙岩','宁德','晋江'],
 '山东':['山东','青岛','济南','烟台','威海','潍坊','淄博','临沂','济宁','德州','聊城','东营','菏泽','泰安','滨州','日照','枣庄'],
 '安徽':['安徽','合肥','芜湖','蚌埠','淮南','淮北','铜陵','安庆','黄山','滁州','阜阳','宿州','六安','亳州','池州','宣城','马鞍山'],
 '湖南':['湖南','长沙','株洲','湘潭','衡阳','邵阳','岳阳','常德','张家界','益阳','郴州','永州','怀化','娄底','湘西'],
 '四川':['四川','成都','绵阳','德阳','乐山','宜宾','泸州','自贡','攀枝花','南充','达州','广元','广安','遂宁','内江','眉山','雅安','巴中','资阳','阿坝','甘孜','凉山'],
 '广西':['广西','南宁','柳州','桂林','梧州','北海','防城港','钦州','贵港','玉林','百色','贺州','河池','来宾','崇左'],
 '河南':['河南','郑州','洛阳','开封','安阳','新乡','焦作','濮阳','许昌','漯河','南阳','商丘','信阳','周口','驻马店','平顶山','三门峡','鹤壁','济源'],
 '河北':['河北','石家庄','唐山','保定','邯郸','邢台','秦皇岛','张家口','承德','沧州','廊坊','衡水'],
 '山西':['山西','太原','大同','阳泉','长治','晋城','朔州','晋中','运城','忻州','临汾','吕梁'],
 '陕西':['陕西','西安','宝鸡','咸阳','渭南','铜川','延安','榆林','汉中','安康','商洛'],
 '辽宁':['辽宁','沈阳','大连','鞍山','抚顺','本溪','丹东','锦州','营口','阜新','辽阳','盘锦','铁岭','朝阳','葫芦岛'],
 '吉林':['吉林','长春','四平','辽源','通化','白山','松原','白城','延边'],
 '黑龙江':['黑龙江','哈尔滨','齐齐哈尔','牡丹江','佳木斯','大庆','伊春','鸡西','鹤岗','双鸭山','七台河','黑河','绥化'],
 '江西':['江西','南昌','赣州','九江','上饶','抚州','宜春','吉安','景德镇','萍乡','新余','鹰潭'],
 '贵州':['贵州','贵阳','遵义','安顺','毕节','铜仁','六盘水','黔南','黔东南','黔西南'],
 '云南':['云南','昆明','曲靖','玉溪','保山','昭通','丽江','普洱','临沧','大理','楚雄','红河','文山','西双版纳','德宏','怒江','迪庆'],
 '甘肃':['甘肃','兰州','天水','武威','张掖','酒泉','平凉','庆阳','定西','陇南','白银','金昌','嘉峪关','临夏','甘南'],
 '内蒙古':['内蒙古','呼和浩特','包头','鄂尔多斯','乌海','赤峰','通辽','呼伦贝尔','巴彦淖尔','乌兰察布','兴安','锡林郭勒','阿拉善'],
 '新疆':['新疆','乌鲁木齐','克拉玛依','吐鲁番','哈密','阿克苏','喀什','和田','伊犁','昌吉','博州','巴州','塔城','阿勒泰'],
 '青海':['青海','西宁','海东','海北','黄南','海南州','果洛','玉树','海西'],
 '宁夏':['宁夏','银川','石嘴山','吴忠','固原','中卫'],
 '海南':['海南','海口','三亚','儋州','三沙'], '西藏':['西藏','拉萨','日喀则','昌都','林芝','山南','那曲'],
 '北京':['北京','BTV'], '上海':['上海','东方都市','第一财经','五星体育','纪实人文','哈哈炫动'], '天津':['天津'], '重庆':['重庆'],
 '香港':['香港','TVB','翡翠','明珠','凤凰'], '澳门':['澳门','澳视'], '台湾':['台湾','台视','中视','华视','民视','东森','三立']}
BLOCK_TEXT = ['暂不支持播放','暂时无法播放','暂无直播','暂无信号','信号中断','由于版权','版权限制','地区限制','播放失败','直播已结束','节目未开始','暂无节目','该地区无法','accessdenied','notavailableinyourregion']

@dataclasses.dataclass
class Channel:
 name: str
 url: str
 group: str = ''
 region: str = '其他'
 kind: str = '其他'
 sources: list[str] = dataclasses.field(default_factory=list)
 custom: bool = False


def utcnow():
 return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')


def safe_url(url):
 try:
  p=urlsplit(url)
  if p.scheme not in ('http','https') or not p.hostname or p.username or p.password: return False
  if any(ord(c)<32 for c in url) or any(c in url for c in ('\\','|',' ','"','<','>')): return False
  if p.hostname.lower() in ('localhost','localhost.localdomain') or p.hostname.endswith(('.local','.localhost')):return False
  try:return ipaddress.ip_address(p.hostname).is_global
  except ValueError:return '.' in p.hostname
 except ValueError:return False


def clean_name(name):
 name=unicodedata.normalize('NFKC',name).strip().lstrip('\ufeff')
 name=re.sub(r'^\[(?:BD|IPTV|HD)\]\s*','',name,flags=re.I).lstrip('💚❤❤️📺 ')
 name=re.sub(r'(?<=湖北经视)\(湖北有线\)$','',name)
 name=re.sub(r'\s*\[(?:[^]]*(?:p|geo|not 24/7|1280|1920)[^]]*)\]', '', name, flags=re.I)
 name=re.sub(r'\s*\((?:\d{3,4}p|HD|SD|高清|标清|超清)\)\s*$', '',name,flags=re.I)
 name=re.sub(r'^(?:'+ '|'.join(REGIONS)+r')\s+[I|]\s+', '',name)
 name={'绍兴综合':'绍兴新闻综合','湖北经济':'湖北经视','湖北经济电视':'湖北经视','湖北经济频道':'湖北经视'}.get(name,name)
 return re.sub(r'[\r\n"<>]', '',name).strip()[:100]


def key(name):
 s=unicodedata.normalize('NFKC',name).upper()
 s=re.sub(r'\([^)]*(?:高清|标清|超清|HD|SD|备用|测试|720|1080|2160)[^)]*\)','',s)
 s=re.sub(r'(?:超高清|超清|高清|标清|HD|SD|HEVC|H264|H265|4K|8K|1080P|720P)','',s)
 return re.sub(r'[\s_\-·]','',s)


def classify(name,group):
 region=next((p for p,words in REGIONS.items() if any(name.upper().startswith(w.upper()) for w in words)),None)
 if not region:region=next((p for p in REGIONS if p in group), '其他')
 if any(w in name+' '+group for w in ['慢直播','风景','景区','日出','云海','草甸','远眺','观景','熊猫直播','峨眉山','九华山','玉女峰','雪山','十八盘','玉皇顶','南天门','山顶','索道','栈道']):return region,'慢直播'
 if any(w in name+' '+group for w in ['轮播','强森电影','林正英','周星驰','钟馗传说','成龙电影','李连杰电影','周润发电影','刘德华电影']):return region,'影视轮播'
 if re.search(r'CCTV|央视|中国教育|^CETV|^CGTN',name,re.I):return '全国','央视/教育'
 if any(w in name for w in ['广播','电台','之声']) or re.search(r'\b(?:FM|RADIO)\b',name,re.I):return region,'广播'
 if '卫视' in name:return region,'卫视'
 if region!='其他' or any(w in group for w in ['地方','地市','区县']):return region,'地方台'
 return region,'其他'


def parse_playlist(text,source,custom=False):
 result=[]; pending=None; group=''
 for raw in text.lstrip('\ufeff').splitlines():
  line=raw.strip()
  if not line:continue
  if line.startswith('#EXTINF:'):
   # Some public lists put an extra comma before the first attribute.
   line=re.sub(r'^(#EXTINF:[^,]*),(?=(?:tvg-|group-title)[\w-]*=)',r'\1 ',line)
   attrs=dict(re.findall(r'([\w-]+)="([^"]*)"',line))
   match=re.match(r'^#EXTINF:(?:[^",]|"[^"]*")*,(.*)$',line)
   name=match.group(1).strip() if match else line.rsplit(',',1)[-1]
   pending=(name,attrs.get('group-title',''));continue
  if line.startswith('#'):continue
  if pending and line.startswith(('http://','https://')):
   name,g=pending;pending=None;urls=[line]
  elif ',' in line:
   name,tail=line.split(',',1)
   if tail.strip()=='#genre#':group=clean_name(name);pending=None;continue
   g=group;urls=re.split(r'#(?=https?://)',tail)
  else:pending=None;continue
  for u in urls:
   u=u.strip().split('$',1)[0]
   n=clean_name(name)
   if not n or not safe_url(u):continue
   if urlsplit(u).path.lower().endswith(('.mp4','.mkv','.mov','.avi','.mp3','.m4a','.wav')):continue
   region,kind=classify(n,g or name)
   if kind in EXCLUDED_KINDS:continue
   result.append(Channel(n,u,g,region,kind,[source],custom))
 return result


def fetch_text(url,timeout=15,max_bytes=12_000_000):
 if not safe_url(url):raise ValueError('unsupported URL')
 with urlopen(Request(url,headers={'User-Agent':UA}),timeout=timeout) as response:
  if not safe_url(response.url):raise ValueError('unsafe redirect')
  data=response.read(max_bytes+1)
  if len(data)>max_bytes:raise ValueError('source exceeds size limit')
  return data.decode('utf-8-sig',errors='replace')


def collect(config,root=ROOT):
 items=[];sources=[]
 custom=root/'data/custom.m3u'
 if custom.exists():items+=parse_playlist(custom.read_text(), 'data/custom.m3u',True)
 def load(s):
  try:
   parsed=parse_playlist(fetch_text(s['url']),s['url'])
   if not parsed:raise ValueError('no usable candidates in source')
   return parsed,{'name':s['name'],'url':s['url'],'ok':True,'candidates':len(parsed)}
  except Exception as e:return [],{'name':s['name'],'url':s['url'],'ok':False,'error':f'{type(e).__name__}: {e}'[:250]}
 with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
  for parsed,report in pool.map(load,[s for s in config if s.get('enabled',True)]):items+=parsed;sources.append(report)
 unique={}
 for c in items:
  if c.url in unique:
   prev=unique[c.url];prev.sources=list(dict.fromkeys(prev.sources+c.sources))
   if prev.region=='其他' and c.region!='其他':prev.region=c.region;prev.kind=c.kind
  else:unique[c.url]=c
 return list(unique.values()),sources



def restore_previous(items,rows,active_sources):
 result=list(items);present={c.url for c in result}
 for row in rows:
  if row['url'] in present or row.get('custom') or not any(s in active_sources for s in row.get('sources',[])) or not safe_url(row['url']):continue
  c=Channel(**{f.name:row[f.name] for f in dataclasses.fields(Channel)})
  c.name=clean_name(c.name);c.region,c.kind=classify(c.name,c.group)
  if c.kind in EXCLUDED_KINDS:continue
  result.append(c);present.add(c.url)
 return result


def select_channels(items,limit,previous=(),day=None,priority_channels=(),priority_regions=()):
 """Reserve requested channels/regions, then rotate fairly across channel names."""
 previous=set(previous);day=day or dt.datetime.now(dt.timezone.utc).date().isoformat()
 requested={key(clean_name(n)) for n in priority_channels}
 token=lambda c:hashlib.sha256((day+c.url).encode()).hexdigest()
 # Interleave hosts for focused channels; one mirror must not take every slot.
 def fair(candidates,rounds=4):
  buckets=defaultdict(list)
  for c in sorted(candidates,key=token):buckets[key(c.name)].append(c)
  for name,bucket in buckets.items():
   hosts=defaultdict(list)
   for c in bucket:hosts[urlsplit(c.url).hostname].append(c)
   buckets[name]=[c for i in range(max(map(len,hosts.values()),default=0)) for h in hosts.values() for c in h[i:i+1]]
  return [c for i in range(rounds) for b in buckets.values() for c in b[i:i+1]]
 focused=fair([c for c in items if key(c.name) in requested],128)[:min(128,max(1,limit//4))]
 priority=sorted([c for c in items if c.custom or c.url in previous],key=lambda c:(not c.custom,c.kind!='地方台',token(c)))
 regional=fair([c for c in items if c.region in priority_regions and c.kind=='地方台'],6)[:min(240,max(1,limit//5))]
 others=[c for c in items if not c.custom and c.url not in previous]
 local=fair([c for c in others if c.kind=='地方台'])
 other=fair([c for c in others if c.kind!='地方台'])
 order=[]
 while local or other:
  order+=local[:2];local=local[2:];order+=other[:1];other=other[1:]
 selected=[];per_channel=Counter();seen=set()
 for c in focused+priority+regional+order:
  k=key(c.name);cap=128 if k in requested else (6 if c.region in priority_regions else 4)
  if c.url in seen or per_channel[k]>=cap:continue
  seen.add(c.url);per_channel[k]+=1;selected.append(c)
  if len(selected)>=limit:break
 return selected


def probe_many(selected,settings,ffmpeg,ocr=False):
 """Limit each host without occupying worker threads waiting on host locks."""
 pending=defaultdict(list)
 for c in selected:pending[urlsplit(c.url).hostname].append(c)
 active=Counter();results=[]
 def check(c):
  r=probe(c,settings,ffmpeg,ocr)
  if not r['ok'] and r['reason'] in ('timeout','media_timeout','decode_failed','media_errors','incomplete_sample','invalid_or_unreachable_hls','hls_recheck_failed','hls_not_updating') and settings.get('retry_failures',1):
   first=r['reason'];r=probe(c,settings,ffmpeg,ocr);r['retry_after']=first
  return r
 with concurrent.futures.ThreadPoolExecutor(max_workers=settings['workers']) as pool:
  futures={}
  while any(pending.values()) or futures:
   while len(futures)<settings['workers']:
    eligible=[h for h,q in pending.items() if q and active[h]<2]
    if not eligible:break
    host=min(eligible,key=lambda h:active[h]);c=pending[host].pop(0)
    futures[pool.submit(check,c)]=(host,c);active[host]+=1
   done,_=concurrent.futures.wait(futures,return_when=concurrent.futures.FIRST_COMPLETED)
   for future in done:
    host,c=futures.pop(future);active[host]-=1
    try:r=future.result()
    except Exception as e:r={**dataclasses.asdict(c),'ok':False,'reason':'unexpected_probe_error','error':str(e)[:200],'checked_at':utcnow()}
    results.append(r)
    if r['ok'] or len(results)%25==0:print(json.dumps({'progress':f'{len(results)}/{len(selected)}','name':r['name'],'ok':r['ok'],'reason':r['reason']},ensure_ascii=False),flush=True)
 return sorted(results,key=lambda r:(r['region'],key(r['name']),r['url']))


def analyze_decode(stderr,stdout,seconds,returncode):
 frames=[int(v) for v in re.findall(r'^frame=(\d+)',stdout,re.M)]
 times=[int(v)/1_000_000 for v in re.findall(r'^out_time_us=(\d+)',stdout,re.M)]
 peaks=[float(v) for v in re.findall(r'Peak level dB: ([-+\w.]+)',stderr)]
 rms=[float(v) for v in re.findall(r'RMS level dB: ([-+\w.]+)',stderr)]
 resolution=re.search(r'Video:.*?\b(\d{3,4})x(\d{3,4})\b',stderr)
 errors=[l.strip() for l in stderr.splitlines() if re.search(r'Protocol .*not on whitelist|HTTP error|Error (?:opening|while|during)|Invalid data|Packet corrupt|corrupt input|non.monoton|Failed to|Error applying|Error initializing',l,re.I)]
 black=[float(v) for v in re.findall(r'black_duration:([\d.]+)',stderr)]
 starts=[float(v) for v in re.findall(r'black_start:([-+]?[\d.]+)',stderr)]
 ends=[float(v) for v in re.findall(r'black_end:([-+]?[\d.]+)',stderr)]
 freeze=[float(v) for v in re.findall(r'freeze_duration: ([\d.]+)',stderr)]
 fs=[float(v) for v in re.findall(r'freeze_start: ([-+]?[\d.]+)',stderr)]
 fe=[float(v) for v in re.findall(r'freeze_end: ([-+]?[\d.]+)',stderr)]
 duration=max(times,default=0)
 if len(starts)>len(ends):black.append(max(0,duration-starts[-1]))
 if len(fs)>len(fe):freeze.append(max(0,duration-fs[-1]))
 reason=''
 if returncode!=0:reason='decode_failed'
 elif duration<seconds-0.5 or 'progress=end' not in stdout:reason='incomplete_sample'
 elif max(frames,default=0)<seconds*8:reason='too_few_video_frames'
 elif not resolution:reason='no_video'
 elif not rms or not any(math.isfinite(x) and x>-65 for x in rms):reason='silent_audio'
 elif errors:reason='media_errors'
 elif max(black,default=0)>=3:reason='black_screen'
 elif max(freeze,default=0)>=6:reason='frozen_picture'
 return {'ok':not reason,'reason':reason or 'passed','seconds':round(duration,2),'frames':max(frames,default=0),'resolution':f'{resolution[1]}x{resolution[2]}' if resolution else None,'audio_rms_db':next((v for v in reversed(rms) if math.isfinite(v)),None),'max_black_seconds':max(black,default=0),'max_freeze_seconds':max(freeze,default=0),'errors':errors[:3]}



def inspect_hls(url,depth=0):
 if depth>2:raise ValueError('nested HLS limit')
 text=fetch_text(url,timeout=8,max_bytes=1_000_000)
 if not text.lstrip().startswith('#EXTM3U'):raise ValueError('not an HLS playlist')
 lines=[line.strip() for line in text.splitlines() if line.strip()]
 if any(line.startswith('#EXT-X-STREAM-INF:') for line in lines):
  child=next((lines[i+1] for i,line in enumerate(lines[:-1]) if line.startswith('#EXT-X-STREAM-INF:') and not lines[i+1].startswith('#')),None)
  if not child:raise ValueError('empty HLS master')
  return inspect_hls(urljoin(url,child),depth+1)
 segments=[line for line in lines if not line.startswith('#')]
 if not segments:raise ValueError('empty HLS media playlist')
 if '#EXT-X-ENDLIST' in lines:raise ValueError('ended HLS playlist')
 if not all(safe_url(urljoin(url,line)) for line in segments):raise ValueError('unsupported HLS segment URL')
 sequence=next((line for line in lines if line.startswith('#EXT-X-MEDIA-SEQUENCE:')),'')
 return {'url':url,'signature':sequence+'|'+segments[-1]}



def check_notice(frame,env):
 started=time.monotonic()
 try:
  with OCR_SLOTS:
   p=subprocess.run(['tesseract',str(frame),'stdout','-l','chi_sim+eng','--psm','11'],capture_output=True,timeout=20,env={**env,'OMP_THREAD_LIMIT':'1','OMP_NUM_THREADS':'1'})
  text=re.sub(r'\s+','',p.stdout.decode(errors='replace')).lower()
  blocked=next((s for s in BLOCK_TEXT if s in text),None)
  result={'ocr_checked':p.returncode==0,'ocr_elapsed_seconds':round(time.monotonic()-started,2)}
  if p.returncode:result.update(ok=False,reason='ocr_failed')
  elif blocked:result.update(ok=False,reason='unavailable_notice',notice=blocked)
  return result
 except subprocess.TimeoutExpired:return {'ok':False,'reason':'ocr_timeout','ocr_elapsed_seconds':round(time.monotonic()-started,2)}


def probe(channel,settings,ffmpeg,ocr=False):
 started=time.monotonic();result=dataclasses.asdict(channel);result['checked_at']=utcnow()
 env=os.environ.copy()
 if 'HTTP_PROXY' in env:env.setdefault('http_proxy',env['HTTP_PROXY'])
 seconds=settings['sample_seconds'];timeout=settings['probe_timeout_seconds']
 hls=None
 if urlsplit(channel.url).path.lower().endswith(('.m3u8','.m3u')):
  try:hls=inspect_hls(channel.url)
  except Exception as e:
   result.update(ok=False,reason='invalid_or_unreachable_hls',error=str(e)[:160],elapsed_seconds=round(time.monotonic()-started,2))
   return result
 cmd=[ffmpeg,'-hide_banner','-nostdin','-rw_timeout','8000000','-protocol_whitelist','http,https,httpproxy,tcp,tls,crypto','-threads','1','-filter_threads','1','-user_agent',UA,'-i',channel.url,'-t',str(seconds),'-map','0:v:0','-map','0:a:0','-vf','scale=320:-2,blackdetect=d=3:pix_th=0.1,freezedetect=n=-50dB:d=6','-af','astats=metadata=0:reset=0','-progress','pipe:1','-f','null','-']
 try:
  with tempfile.TemporaryDirectory(prefix='iptv-probe-') as tmp:
   frame=Path(tmp)/'sample.png'
   if ocr:cmd += ['-map','0:v:0','-frames:v','1','-vf','scale=960:-2','-threads','1','-update','1',str(frame)]
   p=subprocess.run(cmd,capture_output=True,timeout=timeout,env=env)
   stderr=p.stderr.decode(errors='replace');stdout=p.stdout.decode(errors='replace')
   result.update(analyze_decode(stderr,stdout,seconds,p.returncode))
   if result['ok'] and hls:
    try:
     after=inspect_hls(hls['url'])
     if after['signature']==hls['signature']:
      time.sleep(2);after=inspect_hls(hls['url'])
     result['hls_progressed']=after['signature']!=hls['signature']
     if not result['hls_progressed']:result.update(ok=False,reason='hls_not_updating')
    except Exception as e:result.update(ok=False,reason='hls_recheck_failed',error=str(e)[:160])
   if result['ok'] and ocr:
    if not frame.exists():result.update(ok=False,reason='ocr_frame_missing')
    else:
     result.update(check_notice(frame,env))
 except subprocess.TimeoutExpired:result.update(ok=False,reason='media_timeout')
 except OSError as e:result.update(ok=False,reason='probe_error',error=str(e)[:200])
 result['elapsed_seconds']=round(time.monotonic()-started,2)
 return result


def best_channels(results):
 choices={}
 def score(r):
  w,h=map(int,(r.get('resolution') or '0x0').split('x'))
  return (w*h,-r.get('elapsed_seconds',999))
 for r in results:
  if not r['ok']:continue
  k=key(r['name'])
  if k not in choices or score(r)>score(choices[k]):choices[k]=r
 return sorted(choices.values(),key=lambda r:(r['kind']!='地方台',r['region']!='湖北',r['region'],key(r['name'])))


def m3u(rows,checked):
 lines=['#EXTM3U',f'# Verified at {checked}; short media samples, no uptime guarantee.']
 for r in rows:
  group=r['region']+'地方台' if r['kind']=='地方台' else r['kind']
  lines += [f'#EXTINF:-1 tvg-name="{r["name"]}" group-title="{group}",{r["name"]}',r['url']]
 return '\n'.join(lines)+'\n'


def txt(rows):
 groups=defaultdict(list)
 for r in rows:groups[r['region']+'地方台' if r['kind']=='地方台' else r['kind']].append(r)
 lines=[]
 for group,channels in groups.items():
  lines.append(group+',#genre#');lines.extend(r['name']+','+r['url'] for r in channels)
 return '\n'.join(lines)+'\n'


def atomic_write(path,text):
 path.parent.mkdir(parents=True,exist_ok=True)
 tmp=path.with_name(path.name+'.tmp');tmp.write_text(text,encoding='utf-8');tmp.replace(path)


def json_write(path,obj):atomic_write(path,json.dumps(obj,ensure_ascii=False,indent=2,allow_nan=False)+'\n')


def apply_content_reviews(results,reviews):
 held={r['url']:r for r in reviews if r.get('decision')=='hold'}
 return [{**r,'media_ok':r.get('media_ok',r['ok']),'media_reason':r.get('media_reason',r.get('reason')),'ok':False,'reason':held[r['url']]['reason'],'content_review':held[r['url']]} if r['url'] in held else r for r in results]


def publish(root,results,sources,total,selected,settings,started):
 review_file=root/'config/content-reviews.json'
 if review_file.exists():results=apply_content_reviews(results,json.loads(review_file.read_text()))
 checked=utcnow();rows=best_channels(results)
 reports=root/'reports';playlists=root/'playlists';old={}
 if (reports/'status.json').exists():old=json.loads((reports/'status.json').read_text())
 requested=[]
 for name in settings.get('priority_channels',[]):
  attempted=[r for r in results if key(r['name'])==key(name)]
  requested.append({'name':name,'tested_urls':len(attempted),'passed_urls':sum(r['ok'] for r in attempted),'failure_reasons':dict(Counter(r['reason'] for r in attempted if not r['ok']))})
 local=[r for r in rows if r['kind']=='地方台']
 hubei=[r for r in local if r['region']=='湖北']
 wuhan=[r for r in local if r['name'].startswith(('武汉','江夏'))]
 state='ok' if rows else 'failed_no_channels'
 status={'state':state,'last_attempt_at':checked,'last_success_at':checked if rows else old.get('last_success_at'),'sample_seconds':settings['sample_seconds'],'ocr_enabled':settings.get('ocr_enabled',False),'candidate_urls':total,'tested_urls':selected,'passed_urls':sum(r['ok'] for r in results),'unique_channels':len(rows),'regional_channels':len(local),'failed_sources':[s['name'] for s in sources if not s['ok']],'runner':os.getenv('GITHUB_ACTIONS') and 'GitHub Actions' or 'local','run_url':(os.getenv('GITHUB_SERVER_URL','https://github.com')+'/'+os.getenv('GITHUB_REPOSITORY','')+'/actions/runs/'+os.getenv('GITHUB_RUN_ID','')) if os.getenv('GITHUB_RUN_ID') else None,'duration_seconds':round(time.monotonic()-started,1),'publication_note':'Only URLs passing this run are published.' if rows else 'No playlist updated. Existing playlists are from the last successful run; see last_success_at.'}
 status['requested_channels']=requested
 status['hubei_channels']=len(hubei);status['wuhan_channels']=len(wuhan)
 status['upstream_count']=len(sources)
 if rows:
  for name,subset in [('all',rows),('regional',local),('hubei',hubei),('wuhan',wuhan)]:
   atomic_write(playlists/(name+'.m3u'),m3u(subset,checked));atomic_write(playlists/(name+'.txt'),txt(subset))
  json_write(reports/'channels.json',{'checked_at':checked,'channels':rows})
 json_write(reports/'status.json',status)
 json_write(reports/'latest.json',{'status':status,'sources':sources,'results':results})
 summary=['# 最近一次直播源检查','',f'- 检查时间（UTC）：{checked}',f'- 状态：{state}',f'- 收集 {total} 个去重URL，检测 {selected} 个，通过 {status["passed_urls"]} 个URL。',f'- 合并为 {len(rows)} 个频道，其中地方台 {len(local)} 个。',f'- 每路样本：{settings["sample_seconds"]} 秒；检测解码、音轨、黑屏、冻结及可用时的中文错误提示OCR。',f'- 执行环境：{status["runner"]}；结果不代表家庭网络连通性或长期稳定。']
 if not rows:summary+=['','**此次未发布任何新列表。现有播放列表保留上次成功结果，请检查最后成功时间；不能视为今天验证通过。**']
 if status['failed_sources']:summary+=['','部分上游读取失败：'+', '.join(status['failed_sources'])]
 summary+=['','## 重点频道','','| 频道 | 检测URL | 通过URL | 未通过原因 |','|---|---:|---:|---|']
 summary += [f'| {r["name"]} | {r["tested_urls"]} | {r["passed_urls"]} | {r["failure_reasons"]} |' for r in requested]
 summary+=['','## 上游读取情况','','| 上游 | 候选条目 | 状态 |','|---|---:|---|']
 summary += [f'| {s["name"]} | {s.get("candidates",0)} | {"成功" if s["ok"] else "失败"} |' for s in sources]
 summary+=['','## 通过的地方台','','| 地区 | 频道 | 分辨率 |','|---|---|---|']
 summary += [f'| {r["region"]} | {r["name"].replace("|", " ")} | {r["resolution"]} |' for r in local]
 atomic_write(reports/'summary.md','\n'.join(summary)+'\n')
 return status


def main(argv=None):
 ap=argparse.ArgumentParser(description=__doc__)
 ap.add_argument('--limit',type=int);ap.add_argument('--workers',type=int);ap.add_argument('--sample-seconds',type=int)
 ap.add_argument('--ffmpeg',default=os.getenv('FFMPEG','ffmpeg'));ap.add_argument('--root',type=Path,default=ROOT)
 ap.add_argument('--custom-only',action='store_true');ap.add_argument('--require-ocr',action='store_true')
 args=ap.parse_args(argv);root=args.root.resolve();started=time.monotonic()
 settings=json.loads((root/'config/settings.json').read_text());sources=json.loads((root/'config/sources.json').read_text())
 for attr,setting in [('limit','max_candidates'),('workers','workers'),('sample_seconds','sample_seconds')]:
  if getattr(args,attr) is not None:settings[setting]=getattr(args,attr)
 if not 1<=settings['workers']<=24 or not 1<=settings['max_candidates']<=5000 or not 8<=settings['sample_seconds']<=60:ap.error('settings out of bounds')
 ffmpeg=shutil.which(args.ffmpeg)
 if not ffmpeg:ap.error('ffmpeg is required')
 ocr=bool(shutil.which('tesseract'))
 if ocr:
  p=subprocess.run(['tesseract','--list-langs'],capture_output=True,text=True,timeout=10)
  ocr=p.returncode==0 and all(lang in p.stdout.split() for lang in ['chi_sim','eng'])
 if args.require_ocr and not ocr:ap.error('tesseract chi_sim and eng are required')
 settings['ocr_enabled']=ocr
 items,source_results=collect([] if args.custom_only else sources,root)
 previous=[]
 if (root/'reports/channels.json').exists():
  previous_rows=json.loads((root/'reports/channels.json').read_text())['channels']
  previous=[r['url'] for r in previous_rows]
  # A temporary feed outage must not prevent rechecking its last known good URLs.
  # Explicitly removed custom URLs / disabled feeds are not resurrected.
  active_sources={s['url'] for s in sources if s.get('enabled',True)} if not args.custom_only else set()
  items=restore_previous(items,previous_rows,active_sources)
 selected=select_channels([c for c in items if c.kind in settings.get('include_kinds',('地方台','卫视','央视/教育','其他'))],settings['max_candidates'],previous,priority_channels=settings.get('priority_channels',()),priority_regions=settings.get('priority_regions',()))
 print(json.dumps({'stage':'collected','candidates':len(items),'selected':len(selected),'sources':source_results,'ocr':ocr},ensure_ascii=False),flush=True)
 results=probe_many(selected,settings,ffmpeg,ocr)
 status=publish(root,results,source_results,len(items),len(selected),settings,started)
 print(json.dumps(status,ensure_ascii=False),flush=True)
 return 0 if status['state']=='ok' else 2

if __name__=='__main__':sys.exit(main())
