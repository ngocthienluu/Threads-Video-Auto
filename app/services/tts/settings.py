"""Runtime-only TTS configuration; secrets never enter project JSON."""
from dataclasses import dataclass, field
import os
from pathlib import Path
from app.core.config import ROOT


@dataclass(frozen=True)
class TTSSettings:
    api_key: str = field(default="", repr=False)
    default_voice: str = ""
    model: str = "eleven_flash_v2_5"
    output_format: str = "mp3_44100_128"
    cache_dir: Path = ROOT / "cache/tts"
    ffprobe: str = "ffprobe"
    request_timeout: float = 20.0
    total_timeout: float = 120.0
    max_audio_bytes: int = 30_000_000
    min_speed: float = .7
    max_speed: float = 1.2

    @classmethod
    def from_environment(cls, env_file=ROOT / ".env"):
        values = {}
        if env_file.is_file():
            for line in env_file.read_text(encoding="utf-8-sig").splitlines():
                key, sep, value = line.strip().partition("=")
                if sep and key in {"ELEVENLABS_API_KEY", "ELEVENLABS_VOICE_ID", "ELEVENLABS_MODEL_ID", "FFPROBE_PATH"}:
                    values[key] = value.strip().strip("\"'")
        def get(name, default=""):
            return os.environ.get(name, values.get(name, default))
        return cls(api_key=get("ELEVENLABS_API_KEY"), default_voice=get("ELEVENLABS_VOICE_ID"),
                   model=get("ELEVENLABS_MODEL_ID", cls.model), ffprobe=get("FFPROBE_PATH", "ffprobe"))
