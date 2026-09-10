"""Voice metadata and local cache. Cached metadata never proves account access."""
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
from app.services.tts.errors import TTSError


@dataclass
class VoiceInfo:
    voice_id: str
    name: str = ""
    category: str | None = None
    description: str | None = None
    labels: dict[str, str] = field(default_factory=dict)
    language: str | None = None
    accent: str | None = None
    preview_url: str | None = None
    is_available: bool | None = None
    availability_status: str = "unknown"
    availability_reason: str = "API access not confirmed"

    @classmethod
    def parse(cls, data):
        if not isinstance(data, dict) or not isinstance(data.get("voice_id"), str) or not data["voice_id"]:
            raise ValueError("Invalid voice metadata")
        def optional(key):
            value = data.get(key)
            if value is not None and not isinstance(value, str):
                raise ValueError("Invalid voice metadata")
            return value
        labels = data.get("labels")
        if labels is None:
            labels = {}
        if not isinstance(labels, dict) or any(not isinstance(k, str) or not isinstance(v, str) for k, v in labels.items()):
            raise ValueError("Invalid voice labels")
        return cls(data["voice_id"], optional("name") or "", optional("category"),
                   optional("description"), labels, labels.get("language"), labels.get("accent"), optional("preview_url"))


class VoiceCatalog:
    def __init__(self, provider, cache_dir):
        self.provider = provider
        self.path = Path(cache_dir) / "elevenlabs_voices.json"
        self.voices = []
        self.fetched_at = ""
        self.warning = ""

    def load_cache(self):
        try:
            if not self.path.exists():
                return []
            if self.path.stat().st_size > 5_000_000:
                raise ValueError()
            data = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(data["fetched_at"], str) or not isinstance(data["voices"], list):
                raise ValueError()
            voices = [VoiceInfo.parse(v) for v in data["voices"]]
            self.fetched_at, self.voices = data["fetched_at"], voices
        except (OSError, ValueError, KeyError, TypeError):
            self.warning = "Cannot read cached voice list. Use Refresh Voices."
        return self.voices

    def list_voices(self, cancel=None):
        voices = self.provider.list_voices(cancel)
        # Keep session observations across metadata refresh, never across app restarts.
        previous = {v.voice_id: v for v in self.voices}
        for voice in voices:
            if voice.voice_id in previous:
                old = previous[voice.voice_id]
                voice.is_available, voice.availability_status, voice.availability_reason = old.is_available, old.availability_status, old.availability_reason
        self.voices = voices
        self.fetched_at = datetime.now(timezone.utc).isoformat()
        self.warning = ""
        temporary = None
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.path.parent, delete=False) as stream:
                temporary = Path(stream.name)
                records = []
                for voice in voices:
                    record = asdict(voice)
                    for key in ("is_available", "availability_status", "availability_reason"):
                        record.pop(key)
                    records.append(record)
                json.dump({"fetched_at": self.fetched_at, "voices": records}, stream, ensure_ascii=False)
            os.replace(temporary, self.path)
        except OSError:
            self.warning = "Voices loaded, but metadata cache could not be saved."
        finally:
            if temporary and temporary.exists():
                try:
                    temporary.unlink()
                except OSError:
                    pass
        return voices

    def get_voice_details(self, voice_id, cancel=None):
        return self.provider.get_voice_details(voice_id, cancel)

    def find(self, voice_id):
        return next((v for v in self.voices if v.voice_id == voice_id), VoiceInfo(voice_id))

    def observe(self, voice_id, error=None):
        voice = self.find(voice_id)
        if not any(v.voice_id == voice_id for v in self.voices):
            self.voices.append(voice)
        voice.availability_status = error.availability_status if error else "available"
        voice.is_available = True if not error else False if voice.availability_status in {"payment_required", "restricted", "unauthorized"} else None
        voice.availability_reason = str(error) if error else "Available via API (confirmed this session)"
        return voice

    def validate_voice_access(self, voice_id, tts_service, cancel=None):
        # Only called by explicit Test Voice; force a fresh short request, no cache proof.
        from app.core.models import SceneItem
        sample = SceneItem(tts_text="Xin chào", tts_text_is_manual=True, voice_id=voice_id)
        return tts_service.generate(sample, cancel, force=True)
