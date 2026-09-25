import dataclasses,json,tempfile,time,unittest,subprocess
from types import SimpleNamespace
from pathlib import Path
from unittest.mock import patch
from scripts import update as u

URL='https://tv.example.com/live.m3u8?auth=abc%2Fxyz&time=123'
class ParsingTests(unittest.TestCase):
 def test_signed_url_preserved(self):
  r=u.parse_playlist('#EXTM3U\n#EXTINF:-1 group-title="湖北",武汉新闻综合\n'+URL,'test')[0]
  self.assertEqual(r.url,URL);self.assertEqual((r.region,r.kind),('湖北','地方台'))
 def test_comma_inside_attribute(self):
  r=u.parse_playlist('#EXTINF:-1 group-title="湖北,武汉",武汉新闻综合\n'+URL,'test')[0]
  self.assertEqual(r.name,'武汉新闻综合')
 def test_txt_group_multiple_sources(self):
  r=u.parse_playlist('浙江,#genre#\n湖州新闻综合,'+URL+'#https://other.example.com/live.m3u8$备用','test')
  self.assertEqual(len(r),2);self.assertEqual(r[0].region,'浙江');self.assertNotIn('$',r[1].url)
 def test_bom_and_comments(self):
  r=u.parse_playlist('\ufeff#EXTM3U\n#EXTINF:-1,宜昌综合\n#comment\n'+URL,'test')
  self.assertEqual(len(r),1)
 def test_header_injection_rejected(self):
  self.assertFalse(u.safe_url(URL+'|User-Agent=x'));self.assertFalse(u.safe_url('http://name:pass@tv.example.com/a'))
 def test_private_and_file_rejected(self):
  for url in ['file:///etc/passwd','http://127.0.0.1/a','http://192.168.1.1/a','http://169.254.169.254/a','http://localhost/a','http://[::1]/a','rtsp://example.com/a']:
   with self.subTest(url=url):self.assertFalse(u.safe_url(url))
 def test_broadcast_categories(self):
  self.assertEqual(u.classify('CCTV-1','湖北'),('全国','央视/教育'))
  self.assertEqual(u.classify('湖北卫视',''),('湖北','卫视'))
  self.assertEqual(u.classify('南宁影视娱乐',''),('广西','地方台'))
 def test_scenic_camera_not_regional_tv(self):
  self.assertEqual(u.classify('四川峨眉山云海日出','四川')[1],'慢直播')
  self.assertFalse(u.parse_playlist('四川峨眉山云海日出,'+URL,'test'))
 def test_actor_loop_not_regional_tv(self):
  self.assertFalse(u.parse_playlist('湖南,#genre#\n强森电影,'+URL,'test'))
 def test_landmark_camera_excluded(self):
  self.assertFalse(u.parse_playlist('山东,#genre#\n泰山十八盘,'+URL,'test'))
 def test_camera_group_excluded(self):
  self.assertFalse(u.parse_playlist('慢直播,#genre#\n安徽综合,'+URL,'test'))
 def test_radio_skipped(self):
  self.assertFalse(u.parse_playlist('武汉广播,'+URL,'test'))
 def test_feed_quality_label_deduplicates(self):
  self.assertEqual(u.clean_name('浙江 I 绍兴综合 (576p)'), '绍兴新闻综合')
 def test_negative_freeze_timestamp(self):
  self.assertEqual(u.analyze_decode(GOOD_ERR+'freeze_start: -0.04',GOOD_OUT,20,0)['reason'],'frozen_picture')
 def test_normalization(self):self.assertEqual(u.key('武汉新闻综合（高清）'),u.key('武汉新闻综合 HD'))
 def test_hls_endlist_rejected(self):
  with patch.object(u,'fetch_text',return_value='#EXTM3U\n#EXTINF:10,\na.ts\n#EXT-X-ENDLIST'):
   with self.assertRaisesRegex(ValueError,'ended'):u.inspect_hls(URL)
 def test_hls_relative_variant(self):
  data=['#EXTM3U\n#EXT-X-STREAM-INF:BANDWIDTH=100\nchild/live.m3u8','#EXTM3U\n#EXT-X-MEDIA-SEQUENCE:5\n#EXTINF:10,\nsegment.ts']
  with patch.object(u,'fetch_text',side_effect=data):
   r=u.inspect_hls(URL);self.assertEqual(r['url'],'https://tv.example.com/child/live.m3u8');self.assertIn('5|segment.ts',r['signature'])
 def test_private_hls_segment_rejected(self):
  with patch.object(u,'fetch_text',return_value='#EXTM3U\n#EXTINF:10,\nhttp://127.0.0.1/private.ts'):
   with self.assertRaisesRegex(ValueError,'unsupported'):u.inspect_hls(URL)

GOOD_ERR='Stream #0:0: Video: h264, yuv420p, 1280x720, 25 fps\nRMS level dB: -20.5\nPeak level dB: -5\n'
GOOD_OUT='frame=500\nout_time_us=20000000\nprogress=end\n'
class MediaTests(unittest.TestCase):
 def test_good_stream(self):self.assertTrue(u.analyze_decode(GOOD_ERR,GOOD_OUT,20,0)['ok'])
 def test_http_200_not_enough(self):self.assertFalse(u.analyze_decode('HTTP 200 OK','',20,0)['ok'])
 def test_silent_card(self):
  r=u.analyze_decode(GOOD_ERR.replace('-20.5','-inf'),GOOD_OUT,20,0)
  self.assertEqual(r['reason'],'silent_audio');self.assertIsNone(r['audio_rms_db'])
 def test_incomplete(self):self.assertEqual(u.analyze_decode(GOOD_ERR,GOOD_OUT.replace('20000000','3000000'),20,0)['reason'],'incomplete_sample')
 def test_black(self):self.assertEqual(u.analyze_decode(GOOD_ERR+'black_start:2 black_end:12 black_duration:10',GOOD_OUT,20,0)['reason'],'black_screen')
 def test_open_black(self):self.assertEqual(u.analyze_decode(GOOD_ERR+'black_start:5',GOOD_OUT,20,0)['reason'],'black_screen')
 def test_open_freeze(self):self.assertEqual(u.analyze_decode(GOOD_ERR+'freeze_start: 1',GOOD_OUT,20,0)['reason'],'frozen_picture')
 def test_corruption(self):self.assertEqual(u.analyze_decode(GOOD_ERR+'Packet corrupt',GOOD_OUT,20,0)['reason'],'media_errors')
 def test_process_failure(self):self.assertFalse(u.analyze_decode(GOOD_ERR,GOOD_OUT,20,1)['ok'])
 def test_missing_audio(self):self.assertEqual(u.analyze_decode('Video: h264, 1920x1080',GOOD_OUT,20,0)['reason'],'silent_audio')

class OCRTests(unittest.TestCase):
 def test_chinese_unavailable_notice(self):
  with patch.object(u.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout='暂 不 支 持 播 放'.encode())):
   self.assertEqual(u.check_notice(Path('frame.png'),{})['reason'],'unavailable_notice')
 def test_ocr_timeout_distinct_from_media_timeout(self):
  with patch.object(u.subprocess,'run',side_effect=subprocess.TimeoutExpired('tesseract',20)):
   self.assertEqual(u.check_notice(Path('frame.png'),{})['reason'],'ocr_timeout')
 def test_normal_program_caption(self):
  with patch.object(u.subprocess,'run',return_value=SimpleNamespace(returncode=0,stdout='武汉新闻综合'.encode())):
   self.assertTrue(u.check_notice(Path('frame.png'),{})['ocr_checked'])

class SelectionPublishingTests(unittest.TestCase):
 def channel(self,i,custom=False):return u.Channel(f'武汉频道{i}',f'https://tv.example.com/{i}.m3u8',region='湖北',kind='地方台',custom=custom)
 def test_priority(self):
  items=[self.channel(i) for i in range(20)]+[self.channel(99,True)]
  got=u.select_channels(items,2,[items[3].url],'2026-09-25')
  self.assertEqual({x.url for x in got},{items[3].url,items[-1].url})
 def test_feed_outage_rechecks_old_tv_only(self):
  tv=dataclasses.asdict(self.channel(1));tv['sources']=['feed']
  camera={**tv,'name':'四川峨眉山云海日出','url':'https://tv.example.com/camera.m3u8','group':'四川'}
  got=u.restore_previous([], [tv,camera],{'feed'})
  self.assertEqual([c.url for c in got],[tv['url']])
  self.assertFalse(hasattr(got[0],'ok'))
 def test_disabled_source_not_restored(self):
  tv=dataclasses.asdict(self.channel(1));tv['sources']=['disabled']
  self.assertEqual(u.restore_previous([], [tv],{'active'}),[])
 def test_rotation(self):
  items=[self.channel(i) for i in range(40)]
  self.assertNotEqual([c.url for c in u.select_channels(items,5,day='A')],[c.url for c in u.select_channels(items,5,day='B')])
 def test_unique_names_get_chance(self):
  items=[u.Channel('武汉一台',f'https://tv.example.com/a{i}.m3u8',kind='地方台') for i in range(50)]+[self.channel(i) for i in range(20)]
  picked=u.select_channels(items,10,day='today');self.assertEqual(len({u.key(c.name) for c in picked}),10)
 def passing(self,i=1):return {**dataclasses.asdict(self.channel(i)),'ok':True,'resolution':'1280x720','elapsed_seconds':2,'reason':'passed','checked_at':u.utcnow()}
 def test_best_quality_deduplicates(self):
  a=self.passing();b={**a,'resolution':'1920x1080','url':'https://other.example.com/a'}
  self.assertEqual(u.best_channels([a,b])[0]['url'],b['url'])
 def test_failures_never_in_playlist(self):
  a=self.passing();bad={**self.passing(2),'ok':False}
  self.assertNotIn(bad['url'],u.m3u(u.best_channels([a,bad]),'today'))
 def test_zero_does_not_label_old_as_current(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);settings={'sample_seconds':20}
   first=u.publish(root,[self.passing()],[],1,1,settings,time.monotonic())
   before=(root/'playlists/all.m3u').read_text()
   second=u.publish(root,[],[],0,0,settings,time.monotonic())
   self.assertEqual(before,(root/'playlists/all.m3u').read_text());self.assertEqual(second['state'],'failed_no_channels')
   self.assertEqual(first['last_success_at'],second['last_success_at'])
 def test_previous_failed_source_not_carried_forward(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);settings={'sample_seconds':20}
   u.publish(root,[self.passing(1),self.passing(2)],[],2,2,settings,time.monotonic())
   u.publish(root,[self.passing(2)],[],2,2,settings,time.monotonic())
   text=(root/'playlists/all.m3u').read_text();self.assertNotIn(self.passing(1)['url'],text);self.assertIn(self.passing(2)['url'],text)
 def test_empty_regional_overwrites_previous(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);settings={'sample_seconds':20}
   u.publish(root,[self.passing()],[],1,1,settings,time.monotonic())
   u.publish(root,[{**self.passing(2),'kind':'卫视'}],[],1,1,settings,time.monotonic())
   self.assertNotIn('#EXTINF', (root/'playlists/regional.m3u').read_text())

if __name__=='__main__':unittest.main()
