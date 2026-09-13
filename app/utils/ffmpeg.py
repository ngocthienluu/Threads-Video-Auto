"""Discover PATH or project-local FFmpeg tools."""
from app.renderer.media import executable, RenderError

def ffmpeg_available():
    try:executable("ffmpeg");return True
    except RenderError:return False

def ffprobe_available():
    try:executable("ffprobe");return True
    except RenderError:return False
