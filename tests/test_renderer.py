import io
import math
from pathlib import Path
import subprocess
import tempfile
from threading import Event
import unittest
from unittest.mock import patch
from PIL import Image
from app.core.project_manager import ProjectManager
from app.core.config import VideoSettings
from app.renderer.ffmpeg_renderer import FFmpegRenderer
from app.renderer.media import executable, probe, RenderError, RenderCancelled

class RendererTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        try:cls.ffmpeg=executable("ffmpeg");cls.ffprobe=executable("ffprobe")
        except RenderError as exc:raise unittest.SkipTest(str(exc))

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix="render test ")
        self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name)
        self.bg=self.root / "game play.mp4"
        self.audio=self.root / "voice.wav"
        self.run_ffmpeg(["-f","lavfi","-i","testsrc2=s=320x180:r=30:d=1","-f","lavfi","-i","sine=frequency=2000:duration=1","-c:v","libx264","-pix_fmt","yuv420p","-c:a","aac","-shortest",str(self.bg)])
        self.run_ffmpeg(["-f","lavfi","-i","sine=frequency=440:duration=0.5","-ar","48000",str(self.audio)])
        self.manager=ProjectManager()
        for n,color in enumerate(("red","lime")):
            image=self.root / f"comment {n}.png";Image.new("RGB",(120,40),color).save(image)
            item=self.manager.add_single(str(image)).items[0]
            item.audio_path=str(self.audio);item.audio_duration=99;item.tts_status="done"
        self.project=self.manager.project
        self.project.video_settings=VideoSettings(width=180,height=320,comment_y_ratio=.5)
        self.project.background_settings.file=str(self.bg)
        self.project.background_settings.random_start=False
        self.project.watermark_settings.enabled=False
        self.renderer=FFmpegRenderer(temp_root=self.root / "temp",timeout=30)

    def run_ffmpeg(self,args):
        result=subprocess.run([self.ffmpeg,"-hide_banner","-loglevel","error","-y",*args],capture_output=True)
        self.assertEqual(result.returncode,0,result.stderr.decode(errors="replace"))
        return result.stdout

    def frame(self,path,time):
        data=self.run_ffmpeg(["-ss",str(time),"-i",str(path),"-frames:v","1","-f","image2pipe","-vcodec","png","pipe:1"])
        return Image.open(io.BytesIO(data)).convert("RGB")

    def test_real_export_loops_switches_images_reprobes_and_preserves_sources(self):
        before=[Path(i.original_image_path).read_bytes() for s in self.project.scenes for i in s.items]
        output=self.root / "result.mp4";progress=[]
        self.renderer.render(self.project,output,progress.append)
        data=probe(output)
        video=next(s for s in data["streams"] if s["codec_type"]=="video")
        audio=next(s for s in data["streams"] if s["codec_type"]=="audio")
        self.assertEqual((video["width"],video["height"],video["codec_name"],audio["codec_name"]),(180,320,"h264","aac"))
        self.assertAlmostEqual(float(data["format"]["duration"]),1.55,delta=.1)
        red=self.frame(output,.3).getpixel((90,160));green=self.frame(output,1.1).getpixel((90,160))
        self.assertGreater(red[0],200);self.assertLess(red[1],30)
        self.assertGreater(green[1],200);self.assertLess(green[0],30)
        self.assertEqual(progress[-1],100)
        self.assertEqual(before,[Path(i.original_image_path).read_bytes() for s in self.project.scenes for i in s.items])
        self.assertEqual(self.project.scenes[0].items[0].audio_duration,99) # renderer snapshot only
        self.assertEqual(list((self.root / "temp").iterdir()),[])
        # Muted gameplay: initial pre-padding should contain no audible gameplay tone.
        samples=self.run_ffmpeg(["-i",str(output),"-t","0.06","-vn","-f","f32le","-ac","1","pipe:1"])
        import array
        values=array.array("f");values.frombytes(samples)
        self.assertLess(max(abs(x) for x in values),.002)

    def test_music_watermark_and_failed_overwrite(self):
        self.project.music_settings.enabled=True;self.project.music_settings.file=str(self.audio)
        self.project.music_settings.random_start=False
        self.project.watermark_settings.enabled=True;self.project.watermark_settings.text="Test watermark"
        self.project.watermark_settings.size=12;self.project.watermark_settings.y=5
        output=self.root / "music.mp4"
        self.renderer.render(self.project,output)
        self.assertTrue(output.exists())
        original=output.read_bytes()
        with patch.object(self.renderer,"encode",side_effect=RenderError("encode failure")):
            with self.assertRaises(RenderError):self.renderer.render(self.project,output,overwrite=True)
        self.assertEqual(output.read_bytes(),original)
        self.assertEqual(list(self.root.glob(".render-*.mp4")),[])

    def test_preflight_and_cancel(self):
        cancel=Event();cancel.set()
        with self.assertRaises(RenderCancelled):self.renderer.render(self.project,self.root/"cancel.mp4",cancel=cancel)
        self.project.background_settings.loop=False
        with self.assertRaisesRegex(RenderError,"shorter"):self.renderer.render(self.project,self.root/"short.mp4")
        self.project.background_settings.loop=True
        self.project.scenes[0].items[0].tts_status="pending"
        with self.assertRaisesRegex(RenderError,"current audio"):self.renderer.render(self.project,self.root/"stale.mp4")

    def test_running_process_cancellation_keeps_existing_output(self):
        cancel=Event()
        work=self.root / "work";work.mkdir()
        output=self.root / "old.mp4";output.write_bytes(b"keep old")
        args=[self.ffmpeg,"-hide_banner","-loglevel","error","-re","-f","lavfi","-i","testsrc2=s=180x320:r=30","-t","10","-f","null","-"]
        import threading
        timer=threading.Timer(.2,cancel.set);timer.start()
        try:
            with self.assertRaises(RenderCancelled):self.renderer.encode(args,work,10,None,cancel)
        finally:timer.cancel()
        self.assertEqual(output.read_bytes(),b"keep old")

    def test_thread_progressive_and_background_does_not_restart(self):
        from app.core.models import SceneType, ItemRole
        from PIL import ImageChops, ImageStat
        first,second=self.project.scenes
        first.scene_type=SceneType.THREAD
        first.items[0].role=ItemRole.QUESTION
        second.items[0].role=ItemRole.REPLY
        first.items.extend(second.items)
        self.project.scenes=[first]
        output=self.root/"thread.mp4"
        self.renderer.render(self.project,output)
        self.assertAlmostEqual(float(probe(output)["format"]["duration"]),1.5,delta=.1)
        actual=self.frame(output,.9)
        self.assertGreater(actual.getpixel((90,160))[1],200)
        # Compare background outside screenshot to continuous source at .9, not reset at reply .75.
        expected=self.run_ffmpeg(["-i",str(self.bg),"-vf","scale=180:320:force_original_aspect_ratio=increase,crop=180:320,select=eq(n\\,27)","-frames:v","1","-f","image2pipe","-vcodec","png","pipe:1"])
        reference=Image.open(io.BytesIO(expected)).convert("RGB")
        diff=ImageStat.Stat(ImageChops.difference(actual.crop((0,230,180,320)),reference.crop((0,230,180,320))))
        self.assertLess(sum(diff.mean)/3,12)
