"""Narration safeguards, content-addressed cache and measured durations."""
from dataclasses import dataclass
import hashlib
import json
import os
from pathlib import Path
import tempfile
from app.services.tts.settings import TTSSettings
from app.services.tts.elevenlabs import ElevenLabsTTS
from app.services.tts.errors import TTSError, check_cancel
from app.utils.audio import audio_duration, require_ffprobe


@dataclass(frozen=True)
class Narration:
    path: str
    duration: float
    cached: bool


def validate_narration(item):
    if not item.tts_text.strip():
        raise TTSError("TTS Text is empty. Read the image or enter narration first.")
    if item.needs_review and not item.tts_text_is_manual:
        raise TTSError("Review and edit TTS Text before generating voice for uncertain OCR/reply overlap.")
    if not item.voice_id.strip():
        raise TTSError("Select a voice or enter an ElevenLabs voice ID.")


class TTSService:
    def __init__(self, settings=None, provider=None):
        self.settings = settings or TTSSettings.from_environment()
        self.provider = provider or ElevenLabsTTS(self.settings)

    def generate(self, item, cancel=None, force=False):
        validate_narration(item)
        check_cancel(cancel)
        require_ffprobe(self.settings.ffprobe)  # Do not charge for audio we cannot measure.
        signature = json.dumps(["elevenlabs-v1", self.settings.model, self.settings.output_format,
                                item.tts_text, item.voice_id, item.voice_speed], ensure_ascii=False)
        key = hashlib.sha256(signature.encode("utf-8")).hexdigest()
        path = self.settings.cache_dir / f"{key}.mp3"
        temporary = None
        try:
            self.settings.cache_dir.mkdir(parents=True, exist_ok=True)
            if path.is_file() and not force:
                duration = audio_duration(path, self.settings.ffprobe, cancel)
                check_cancel(cancel)
                return Narration(str(path.resolve()), duration, True)
            with tempfile.NamedTemporaryFile(dir=self.settings.cache_dir, suffix=".mp3", delete=False) as stream:
                temporary = Path(stream.name)
            self.provider.synthesize(item.tts_text, item.voice_id, temporary, item.voice_speed, cancel=cancel)
            duration = audio_duration(temporary, self.settings.ffprobe, cancel)
            check_cancel(cancel)
            os.replace(temporary, path)
            return Narration(str(path.resolve()), duration, False)
        except OSError:
            raise TTSError("Cannot access narration cache. Check folder permissions.") from None
        finally:
            if temporary and temporary.exists():
                temporary.unlink()
