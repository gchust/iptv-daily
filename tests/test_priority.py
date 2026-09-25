import dataclasses,json,tempfile,unittest
from pathlib import Path
from scripts import update as u, priority as priority, pipeline as pipeline


class PriorityTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.root=Path(self.tmp.name)
  (self.root/'config').mkdir();(self.root/'data').mkdir()
  self.settings={'priority_channels':['湖北经视'],'sample_seconds':20,'workers':2,'probe_timeout_seconds':45,'retry_failures':0}
  u.json_write(self.root/'config/settings.json',self.settings)
  self.row={**dataclasses.asdict(u.Channel('湖北经视','https://example.com/live.m3u8','湖北','湖北','地方台',['test'],True)),'ok':True,'reason':'passed','resolution':'720x576','elapsed_seconds':20,'checked_at':'2026-09-25T15:00:00+00:00'}

 def test_priority_plan_selects_only_requested_custom_candidates(self):
  (self.root/'data/custom.m3u').write_text('#EXTM3U\n#EXTINF:-1,湖北经视频道\nhttps://example.com/live.m3u8\n#EXTINF:-1,武汉新闻综合\nhttps://example.com/other.m3u8\n#EXTINF:-1,湖北经视\nhttps://example.com/live.m3u8\n')
  plan=priority.create_priority_plan(self.root)
  self.assertEqual(len(plan['selected']),1)
  self.assertEqual(plan['settings']['sample_seconds'],60)
  self.assertEqual(plan['id'],pipeline.plan_digest(plan))

 def test_priority_publication_preserves_aggregate_files(self):
  (self.root/'playlists').mkdir();(self.root/'reports').mkdir()
  for name in ['playlists/all.m3u','reports/status.json','reports/channels.json']:(self.root/name).write_text('original')
  report=u.publish_priority(self.root,[self.row],self.settings)
  self.assertEqual(report['state'],'ok')
  self.assertIn(self.row['url'],(self.root/'playlists/priority.m3u').read_text())
  for name in ['playlists/all.m3u','reports/status.json','reports/channels.json']:self.assertEqual((self.root/name).read_text(),'original')

 def test_hold_removes_previous_priority_success(self):
  u.publish_priority(self.root,[self.row],self.settings)
  u.json_write(self.root/'config/content-reviews.json',[{'url':self.row['url'],'channel':'湖北经视','decision':'hold','reason':'identity_unconfirmed'}])
  report=u.publish_priority(self.root,[self.row],self.settings)
  self.assertEqual(report['state'],'failed_no_channels')
  self.assertEqual(report['results'][0]['reason'],'identity_unconfirmed')
  self.assertNotIn(self.row['url'],(self.root/'playlists/priority.m3u').read_text())
  self.assertEqual((self.root/'playlists/priority.txt').read_text(),'')

 def test_identity_allow_does_not_override_media_failure(self):
  u.json_write(self.root/'config/content-reviews.json',[{'url':self.row['url'],'channel':'湖北经视','decision':'allow'}])
  report=u.publish_priority(self.root,[{**self.row,'ok':False,'reason':'decode_failed'}],self.settings)
  self.assertEqual(report['passed_urls'],0)
  self.assertEqual(report['state'],'failed_no_channels')
