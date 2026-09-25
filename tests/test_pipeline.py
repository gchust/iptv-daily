import dataclasses,json,tempfile,threading,time,unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch
from scripts import pipeline as p, update as u

class ExpandedInputTests(unittest.TestCase):
 def test_nonstandard_extinf_comma(self):
  text='#EXTINF:-1,tvg-id="湖北经视" group-title="湖北,武汉",湖北经视\nhttps://example.com/live.m3u8'
  c=u.parse_playlist(text,'feed')[0]
  self.assertEqual(c.name,'湖北经视');self.assertEqual(c.region,'湖北')
 def test_direct_vod_not_live(self):
  self.assertEqual(u.parse_playlist('湖北,#genre#\n湖北经视,https://example.com/program.mp4','feed'),[])
 def test_hubei_county_classification(self):
  self.assertEqual(u.classify('鄂州新闻综合',''),('湖北','地方台'))
 def test_prefixed_jingshi_name(self):
  self.assertEqual(u.clean_name('[BD]湖北经视'),'湖北经视')
 def test_economy_alias(self):self.assertEqual(u.clean_name('湖北经济'),'湖北经视')
 def test_all_requested_alternatives_get_a_chance(self):
  focused=[u.Channel('湖北经视',f'https://tv{i}.example.com/a.m3u8',region='湖北',kind='地方台') for i in range(20)]
  rest=[u.Channel(f'其他{i}',f'https://other.example.com/{i}') for i in range(200)]
  got=u.select_channels(rest+focused,100,priority_channels=['湖北经视'])
  self.assertEqual(sum(c.name=='湖北经视' for c in got),20)
 def test_priority_region_reserved(self):
  h=u.Channel('荆门综合','https://jmtv.example.com/live',region='湖北',kind='地方台')
  other=[u.Channel(f'浙江频道{i}',f'https://zj.example.com/{i}',region='浙江',kind='地方台') for i in range(100)]
  self.assertIn(h,u.select_channels(other+[h],10,priority_regions=['湖北']))
 def test_source_deduplication_remains_unique(self):
  c=u.Channel('湖北经视','https://tv.example.com/a',region='湖北',kind='地方台',custom=True)
  got=u.select_channels([c],100,[c.url],priority_channels=['湖北经视'],priority_regions=['湖北'])
  self.assertEqual(got,[c])

class ContentReviewTests(unittest.TestCase):
 def test_uncertain_identity_does_not_publish_even_when_media_passes(self):
  results=[{'url':'https://example.com/hbjs','ok':True,'name':'湖北经视','reason':'passed'}]
  got=u.apply_content_reviews(results,[{'url':results[0]['url'],'decision':'hold','reason':'identity_unconfirmed'}])
  self.assertFalse(got[0]['ok']);self.assertTrue(got[0]['media_ok'])
  self.assertEqual(u.best_channels(got),[])
  self.assertTrue(results[0]['ok'])
 def test_unrelated_channel_not_changed(self):
  row={'url':'https://example.com/another','ok':True}
  self.assertEqual(u.apply_content_reviews([row],[{'url':'https://example.com/held','decision':'hold','reason':'identity_unconfirmed'}]),[row])


class SchedulerTests(unittest.TestCase):
 def test_host_limit_does_not_starve_unrelated_hosts(self):
  lock=threading.Lock();counts=Counter();peak=Counter();order=[]
  cs=[u.Channel(str(i),f'https://slow.example.com/{i}') for i in range(8)]+[u.Channel('other','https://other.example.com/a')]
  def fake(c,*args):
   host=u.urlsplit(c.url).hostname
   with lock:counts[host]+=1;peak[host]=max(peak[host],counts[host]);order.append(host)
   time.sleep(.01)
   with lock:counts[host]-=1
   return {**dataclasses.asdict(c),'ok':True,'reason':'passed'}
  with patch.object(u,'probe',side_effect=fake):got=u.probe_many(cs,{'workers':3},'fake')
  self.assertEqual(len(got),9);self.assertLessEqual(peak['slow.example.com'],2)
  self.assertLess(order.index('other.example.com'),3)

class PipelineTests(unittest.TestCase):
 def fixture(self):
  channels=[u.Channel(f'湖北频道{i}',f'https://h{i//2}.example.com/{i}') for i in range(6)]
  plan={'created_at':u.utcnow(),'settings':{'sample_seconds':20},'selected':[dataclasses.asdict(c) for c in channels],'batches':p.split_hosts(channels,4),'sources':[],'candidate_urls':6}
  plan['id']=p.plan_digest(plan)
  parts=[{'plan_id':plan['id'],'shard_index':i,'ocr_enabled':True,'results':[{'url':url,'ok':True,'checked_at':u.utcnow(),'seconds':20,'ocr_checked':True} for url in urls]} for i,urls in enumerate(plan['batches'])]
  return plan,parts
 def test_complete_results_merge(self):
  plan,parts=self.fixture();rows=p.validate_results(plan,parts)
  self.assertEqual(len(rows),6);self.assertTrue(all(r['name'].startswith('湖北') for r in rows))
 def test_each_host_stays_in_one_shard(self):
  plan,_=self.fixture();hosts={}
  for i,b in enumerate(plan['batches']):
   for url in b:
    host=u.urlsplit(url).hostname;self.assertEqual(hosts.setdefault(host,i),i)
 def test_missing_shard_rejected(self):
  plan,parts=self.fixture()
  with self.assertRaisesRegex(ValueError,'missing'):p.validate_results(plan,parts[:-1])
 def test_duplicate_shard_rejected(self):
  plan,parts=self.fixture();parts[-1]=parts[0]
  with self.assertRaisesRegex(ValueError,'duplicate'):p.validate_results(plan,parts)
 def test_stale_shard_rejected(self):
  plan,parts=self.fixture();parts[0]['plan_id']='old'
  with self.assertRaisesRegex(ValueError,'stale'):p.validate_results(plan,parts)
 def test_missing_probe_rejected(self):
  plan,parts=self.fixture();parts[0]['results'].pop()
  with self.assertRaisesRegex(ValueError,'missing'):p.validate_results(plan,parts)
 def test_no_ocr_pass_rejected(self):
  plan,parts=self.fixture();parts[0]['results'][0]['ocr_checked']=False
  with self.assertRaisesRegex(ValueError,'evidence'):p.validate_results(plan,parts)
 def test_failed_probes_do_not_require_media_evidence(self):
  plan,parts=self.fixture();parts[0]['results'][0]={'url':parts[0]['results'][0]['url'],'ok':False,'checked_at':u.utcnow(),'reason':'timeout'}
  self.assertEqual(len(p.validate_results(plan,parts)),6)
 def test_tampered_plan_rejected(self):
  plan,_=self.fixture();plan['settings']['sample_seconds']=1
  with tempfile.TemporaryDirectory() as d:
   path=Path(d)/'plan.json';path.write_text(json.dumps(plan))
   with self.assertRaisesRegex(ValueError,'fingerprint'):p.read_plan(path)
