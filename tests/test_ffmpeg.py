"""Exercise the actual FFmpeg filters with moving, frozen, black and silent media."""
import os,shutil,subprocess,unittest
from scripts.update import analyze_decode

FFMPEG=shutil.which(os.getenv('FFMPEG','ffmpeg'))
@unittest.skipUnless(FFMPEG,'ffmpeg not installed')
class FFmpegIntegrationTests(unittest.TestCase):
 def run_media(self,video,audio):
  cmd=[FFMPEG,'-hide_banner','-nostdin','-filter_threads','1','-f','lavfi','-i',video,'-f','lavfi','-i',audio,'-t','8','-map','0:v:0','-map','1:a:0','-vf','blackdetect=d=3:pix_th=0.1,freezedetect=n=-50dB:d=6','-af','astats=metadata=0:reset=0','-progress','pipe:1','-f','null','-']
  p=subprocess.run(cmd,capture_output=True,text=True,timeout=20)
  return analyze_decode(p.stderr,p.stdout,8,p.returncode)
 def test_moving_picture_and_sound_pass(self):
  r=self.run_media('testsrc2=size=320x180:rate=25','sine=frequency=440:sample_rate=48000');self.assertTrue(r['ok'],r)
 def test_frozen_picture_fails(self):
  r=self.run_media('color=c=blue:size=320x180:rate=25','sine=frequency=440:sample_rate=48000');self.assertEqual(r['reason'],'frozen_picture',r)
 def test_black_picture_fails(self):
  r=self.run_media('color=c=black:size=320x180:rate=25','sine=frequency=440:sample_rate=48000');self.assertEqual(r['reason'],'black_screen',r)
 def test_silent_picture_fails(self):
  r=self.run_media('testsrc2=size=320x180:rate=25','anullsrc=r=48000:cl=stereo');self.assertEqual(r['reason'],'silent_audio',r)

if __name__=='__main__':unittest.main()
