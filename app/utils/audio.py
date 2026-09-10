from pathlib import Path
import json
import logging
import math
import os
import shutil
import subprocess
from time import monotonic
from app.services.tts.errors import TTSError, check_cancel
from app.core.config import ROOT


def require_ffprobe(executable="ffprobe"):
    resolved = shutil.which(executable)
    if not resolved and executable == "ffprobe":
        local = ROOT / "tools/ffmpeg/bin" / ("ffprobe.exe" if os.name == "nt" else "ffprobe")
        if local.is_file():
            resolved = str(local)
    if not resolved:
        raise TTSError("ffprobe is missing. Install FFmpeg and set FFPROBE_PATH in .env or add its bin folder to PATH.")
    return resolved


def audio_duration(path: Path, executable="ffprobe", cancel=None) -> float:
    command = [require_ffprobe(executable), "-v", "error", "-select_streams", "a:0",
               "-show_entries", "stream=codec_type:format=duration", "-of", "json", str(path.resolve())]
    check_cancel(cancel)
    logging.getLogger(__name__).debug("ffprobe -v error -select_streams a:0 -show_entries stream=codec_type:format=duration -of json <audio>")
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, shell=False,
                                   creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        started = monotonic()
        try:
            while True:
                check_cancel(cancel)
                if monotonic() - started > 20:
                    raise TTSError("ffprobe timed out.")
                try:
                    output, _ = process.communicate(timeout=.1)
                    break
                except subprocess.TimeoutExpired:
                    pass
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()
        data = json.loads(output)
        check_cancel(cancel)
        duration = float(data["format"]["duration"])
        if process.returncode or not data.get("streams") or not math.isfinite(duration) or duration <= 0:
            raise ValueError()
        return duration
    except (OSError, ValueError, KeyError, TypeError):
        raise TTSError("Cannot measure valid audio with ffprobe. Check the audio file and FFmpeg installation.") from None
