"""Discovery only; media probing/encoding is deliberately deferred."""
from shutil import which


def ffmpeg_available() -> bool:
    return which("ffmpeg") is not None


def ffprobe_available() -> bool:
    return which("ffprobe") is not None
