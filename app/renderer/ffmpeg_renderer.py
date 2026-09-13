"""Single continuous FFmpeg composition, measured audio and atomic publication."""
from copy import deepcopy
from pathlib import Path
import logging
import os
import random
import subprocess
import tempfile
import time
from PIL import Image, ImageOps, ImageDraw, ImageFont
from app.core.config import ROOT
from app.core.timeline import build_timeline
from app.renderer.media import RenderError, check_cancel, executable, probe
from app.renderer.filter_builder import build_filter_graph

log = logging.getLogger(__name__)

class FFmpegRenderer:
    def __init__(self, temp_root=ROOT / "cache/temp", ffmpeg=None, ffprobe=None, timeout=3600):
        self.temp_root = Path(temp_root)
        self.ffmpeg, self.ffprobe, self.timeout = ffmpeg, ffprobe, timeout

    def render(self, project, output, progress=None, cancel=None, overwrite=False):
        project = deepcopy(project)
        project.validate()
        check_cancel(cancel)
        items = [item for scene in project.scenes for item in scene.items]
        if not items:
            raise RenderError("Import comments and generate their audio before exporting.")
        if any(item.tts_status != "done" for item in items):
            raise RenderError("Generate current audio for every comment before exporting (pending/old audio cannot be used).")
        if any((item.meme and item.meme.enabled) or (item.sfx and item.sfx.enabled) for item in items) or any(s.transition for s in project.scenes):
            raise RenderError("Meme, SFX and transitions are not supported by this renderer yet.")
        v = project.video_settings
        if v.width * 16 != v.height * 9:
            raise RenderError("This export requires a 9:16 video size.")
        ffmpeg, ffprobe = self.ffmpeg or executable("ffmpeg"), self.ffprobe or executable("ffprobe")
        output = Path(output).resolve()
        if output.suffix.lower() != ".mp4":
            raise RenderError("Choose an .mp4 output file.")
        if output.exists() and not overwrite:
            raise RenderError("Output already exists. Choose a different filename.")
        def choose(settings, folder, extensions):
            if settings.random_file:
                files = [p for p in (ROOT / folder).glob("*") if p.suffix.lower() in extensions and p.is_file()]
                if not files:
                    raise RenderError(f"No usable media in {folder}.")
                return random.choice(files)
            if not settings.file:
                raise RenderError("Choose a gameplay video (and music if enabled).")
            return Path(settings.file).resolve()
        background = choose(project.background_settings, "assets/backgrounds", {".mp4", ".mov", ".mkv", ".webm"})
        music = choose(project.music_settings, "assets/music", {".mp3", ".wav", ".m4a", ".ogg"}) if project.music_settings.enabled else None
        sources = [background, *([music] if music else []), *(Path(i.audio_path).resolve() for i in items), *(Path(i.original_image_path).resolve() for i in items)]
        if output in sources:
            raise RenderError("Output must not replace a source media file.")
        if progress: progress(2)
        for item in items:
            data = probe(item.audio_path, cancel, ffprobe)
            if not any(s.get("codec_type") == "audio" for s in data["streams"]):
                raise RenderError("Narration file has no audio stream.")
            item.audio_duration = float(data["format"]["duration"])
        timeline = build_timeline(project)
        bg = probe(background, cancel, ffprobe)
        if not any(s.get("codec_type") == "video" for s in bg["streams"]):
            raise RenderError("Gameplay file has no video stream.")
        bg_audio = project.background_settings.volume > 0
        if bg_audio and not any(s.get("codec_type") == "audio" for s in bg["streams"]):
            raise RenderError("Gameplay has no sound. Set gameplay volume to zero.")
        music_data = probe(music, cancel, ffprobe) if music else None
        if music_data and not any(s.get("codec_type") == "audio" for s in music_data["streams"]):
            raise RenderError("Music file has no audio stream.")
        total = timeline.total_duration
        duration = float(bg["format"]["duration"])
        if not project.background_settings.loop and duration < total:
            raise RenderError("Gameplay is shorter than narration. Enable Loop or choose a longer video.")
        self.temp_root.mkdir(parents=True, exist_ok=True)
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary_output = None
        try:
            with tempfile.TemporaryDirectory(prefix="render-", dir=self.temp_root) as directory:
                work = Path(directory)
                args = [ffmpeg, "-hide_banner", "-loglevel", "error", "-nostdin", "-y", "-filter_complex_threads", "2"]
                def input_media(path, settings, duration, is_background=False):
                    if settings.loop: args.extend(["-stream_loop", "-1"])
                    available = duration if settings.loop else max(0, duration-total) if is_background else duration
                    offset = random.uniform(0, max(0, available-.05)) if settings.random_start else 0
                    args.extend(["-ss", f"{offset:.6f}", "-i", str(path)])
                input_media(background, project.background_settings, duration, True)
                for n, item in enumerate(items):
                    check_cancel(cancel)
                    try:
                        with Image.open(item.original_image_path) as source:
                            im = ImageOps.exif_transpose(source).convert("RGBA")
                            scale = min(v.width*v.comment_max_width_ratio/im.width, v.height*.9/im.height)
                            im = im.resize((max(1, round(im.width*scale)), max(1, round(im.height*scale))), Image.Resampling.LANCZOS)
                            image_path = work / f"image{n}.png"; im.save(image_path)
                    except (OSError, ValueError):
                        raise RenderError(f"Cannot prepare screenshot {n+1}.") from None
                    args.extend(["-loop", "1", "-framerate", str(v.fps), "-i", str(image_path), "-i", str(Path(item.audio_path).resolve())])
                index = 1 + 2*len(items)
                music_index = index if music else None
                if music:
                    input_media(music, project.music_settings, float(music_data["format"]["duration"]))
                    index += 1
                mark_index = None
                if project.watermark_settings.enabled and project.watermark_settings.text:
                    mark = work / "watermark.png"
                    self.watermark(project, mark)
                    args.extend(["-loop", "1", "-framerate", str(v.fps), "-i", str(mark)])
                    mark_index = index
                graph = work / "filters.txt"
                graph.write_text(build_filter_graph(project, timeline, music_index, mark_index, bg_audio), encoding="utf-8")
                with tempfile.NamedTemporaryFile(dir=output.parent, prefix=".render-", suffix=".mp4", delete=False) as stream:
                    temporary_output = Path(stream.name)
                args.extend(["-/filter_complex", str(graph), "-map", "[vout]", "-map", "[aout]", "-t", f"{total:.6f}",
                             "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-threads", "2", "-pix_fmt", "yuv420p", "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart",
                             "-progress", str(work / "progress.txt"), str(temporary_output)])
                self.encode(args, work, total, progress, cancel)
                result = probe(temporary_output, cancel, ffprobe)
                if not all(any(s.get("codec_type") == kind for s in result["streams"]) for kind in ("audio", "video")) or abs(float(result["format"]["duration"])-total) > max(.25, 2/v.fps):
                    raise RenderError("Encoded output failed stream/duration validation.")
                video = next(s for s in result["streams"] if s.get("codec_type") == "video")
                if (video.get("width"), video.get("height"), video.get("codec_name")) != (v.width, v.height, "h264"):
                    raise RenderError("Encoded output has incorrect video dimensions/codec.")
                check_cancel(cancel)
                if output.exists() and not overwrite:
                    raise RenderError("Output appeared during export; choose another filename.")
                os.replace(temporary_output, output)
                if progress: progress(100)
                return output
        except OSError:
            raise RenderError("Cannot read/write export files. Check disk space and permissions.") from None
        finally:
            if temporary_output and temporary_output.exists():
                temporary_output.unlink()

    def encode(self, args, work, total, progress, cancel):
        log.debug("FFmpeg export: libx264/aac, 2 threads, numbered inputs, temporary output (paths omitted)")
        with (work / "stderr.txt").open("wb") as errors:
            process = subprocess.Popen(args, stdout=subprocess.DEVNULL, stderr=errors, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            start = time.monotonic()
            try:
                while process.poll() is None:
                    check_cancel(cancel)
                    if time.monotonic()-start > self.timeout:
                        raise RenderError("Export timed out. Try a shorter project.")
                    if progress and (work / "progress.txt").exists():
                        text = (work / "progress.txt").read_text(errors="replace")
                        values = [line.split("=",1)[1] for line in text.splitlines() if line.startswith("out_time_us=")]
                        if values and values[-1].isdigit():
                            progress(min(98, 5+int(int(values[-1])/1e6/total*93)))
                    time.sleep(.1)
            finally:
                if process.poll() is None:
                    process.kill(); process.wait()
        if process.returncode:
            detail = (work / "stderr.txt").read_text(errors="replace")[-3000:]
            log.error("FFmpeg exited %s: %s", process.returncode, detail)
            raise RenderError("FFmpeg export failed. " + detail)

    @staticmethod
    def watermark(project, path):
        cfg, v = project.watermark_settings, project.video_settings
        font_path = cfg.font or (str(Path(os.environ["WINDIR"]) / "Fonts/segoeui.ttf") if os.environ.get("WINDIR") else "DejaVuSans.ttf")
        try:
            font = ImageFont.truetype(font_path, cfg.size)
        except OSError:
            raise RenderError("Watermark font unavailable. Select a .ttf font or disable watermark.") from None
        image = Image.new("RGBA", (v.width, v.height))
        draw = ImageDraw.Draw(image)
        box = draw.textbbox((0,0), cfg.text, font=font)
        width, height = box[2]-box[0], box[3]-box[1]
        if cfg.position == "top-center": x,y=(v.width-width)/2,cfg.y
        elif cfg.position == "bottom-center": x,y=(v.width-width)/2,v.height-height-cfg.y
        elif cfg.position == "custom": x,y=cfg.x,cfg.y
        else: raise RenderError("Unsupported watermark position.")
        draw.text((max(0,min(v.width-width,x))-box[0],max(0,min(v.height-height,y))-box[1]),cfg.text,font=font,fill=(255,255,255,round(255*cfg.opacity)))
        image.save(path)
