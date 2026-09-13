"""Local media discovery and cancellable probe; no UI dependencies."""
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import time
from app.core.config import ROOT

class RenderError(RuntimeError):
    pass

class RenderCancelled(RenderError):
    pass

def check_cancel(cancel):
    if cancel is not None and cancel.is_set():
        raise RenderCancelled("Export cancelled. Previous output was kept.")

def executable(name):
    configured = os.environ.get(name.upper() + "_PATH", name)
    path = shutil.which(configured)
    if not path and configured == name:
        local = ROOT / "tools/ffmpeg/bin" / (name + ".exe" if os.name == "nt" else name)
        if local.is_file():
            path = str(local)
    if not path:
        raise RenderError(f"{name} is missing. Install FFmpeg or set {name.upper()}_PATH.")
    return path

def probe(path, cancel=None, ffprobe=None):
    path = Path(path)
    if not path.is_file():
        raise RenderError(f"Media file missing: {path.name}")
    check_cancel(cancel)
    try:
        process = subprocess.Popen([ffprobe or executable("ffprobe"), "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path.resolve())],
                                   stdout=subprocess.PIPE, stderr=subprocess.PIPE, creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
        started = time.monotonic()
        try:
            while True:
                check_cancel(cancel)
                if time.monotonic() - started > 20:
                    raise RenderError("Media probe timed out.")
                try:
                    output, _ = process.communicate(timeout=.1)
                    break
                except subprocess.TimeoutExpired:
                    pass
        finally:
            if process.poll() is None:
                process.kill(); process.communicate()
        result = json.loads(output)
        if process.returncode or not result.get("streams"):
            raise ValueError()
        duration = float(result.get("format", {}).get("duration", 0))
        if not math.isfinite(duration) or duration <= 0:
            raise ValueError()
        return result
    except (OSError, ValueError, TypeError):
        raise RenderError(f"Cannot read valid media: {path.name}") from None
