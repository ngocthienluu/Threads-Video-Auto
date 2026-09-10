from pathlib import Path
import time
import re
import httpx
from app.services.tts.base import TTSProvider
from app.services.tts.voices import VoiceInfo
from app.services.tts.settings import TTSSettings
from app.services.tts.errors import TTSError, check_cancel, api_error, connection_error


class ElevenLabsTTS(TTSProvider):
    def __init__(self, settings=None, transport=None):
        self.settings = settings or TTSSettings.from_environment()
        self.transport = transport

    def _client(self):
        if not self.settings.api_key:
            raise TTSError("Set ELEVENLABS_API_KEY in .env or environment, then restart the app.", "ElevenLabs authentication failed", "unauthorized")
        return httpx.Client(base_url="https://api.elevenlabs.io", timeout=self.settings.request_timeout,
                            headers={"xi-api-key": self.settings.api_key}, transport=self.transport,
                            follow_redirects=False)

    @staticmethod
    def _check_response(response):
        if response.status_code != 200:
            raise api_error(response.status_code)

    def synthesize(self, text: str, voice_id: str, output: Path, speed: float = 1.0, cancel=None) -> Path:
        check_cancel(cancel)
        if not text.strip() or not re.fullmatch(r"[A-Za-z0-9_-]+", voice_id):
            raise TTSError("Enter nonempty TTS Text and a valid ElevenLabs voice ID.")
        if not self.settings.min_speed <= speed <= self.settings.max_speed:
            raise TTSError("Voice speed must be between 0.7 and 1.2.")
        started = time.monotonic()
        try:
            with self._client() as client, client.stream("POST", f"/v1/text-to-speech/{voice_id}",
                    params={"output_format": self.settings.output_format},
                    json={"text": text, "model_id": self.settings.model, "voice_settings": {"speed": speed}}) as response:
                self._check_response(response)
                if "audio/" not in response.headers.get("content-type", ""):
                    raise TTSError("ElevenLabs returned a non-audio response.")
                count = 0
                with output.open("wb") as stream:
                    for chunk in response.iter_bytes():
                        check_cancel(cancel)
                        if time.monotonic() - started > self.settings.total_timeout:
                            raise TTSError("Voice download exceeded the time limit.")
                        count += len(chunk)
                        if count > self.settings.max_audio_bytes:
                            raise TTSError("Voice response is too large.")
                        stream.write(chunk)
                check_cancel(cancel)
                if not count:
                    raise TTSError("ElevenLabs returned empty audio.")
            return output
        except httpx.HTTPError:
            raise connection_error() from None
        except OSError:
            raise TTSError("Cannot write narration cache. Check folder permissions.") from None

    def list_voices(self, cancel=None):
        voices = []
        token = None
        try:
            with self._client() as client:
                for _ in range(100):
                    check_cancel(cancel)
                    params = {"page_size": 100}
                    if token:
                        params["next_page_token"] = token
                    response = client.get("/v2/voices", params=params)
                    self._check_response(response)
                    data = response.json()
                    if not isinstance(data["voices"], list):
                        raise ValueError()
                    voices.extend(VoiceInfo.parse(v) for v in data["voices"])
                    if not data.get("has_more"):
                        check_cancel(cancel)
                        return voices
                    token = data.get("next_page_token")
                    if not token:
                        break
            raise TTSError("Voice list is incomplete. Enter a voice ID manually.")
        except httpx.HTTPError:
            raise connection_error() from None
        except (ValueError, KeyError, TypeError, AttributeError):
            raise TTSError("ElevenLabs returned an invalid voice list.") from None

    def get_voice_details(self, voice_id, cancel=None):
        check_cancel(cancel)
        if not re.fullmatch(r"[A-Za-z0-9_-]+", voice_id):
            raise TTSError("Enter a valid ElevenLabs voice ID.")
        try:
            with self._client() as client:
                response = client.get(f"/v1/voices/{voice_id}")
                self._check_response(response)
                voice = VoiceInfo.parse(response.json())
                check_cancel(cancel)
                return voice
        except httpx.HTTPError:
            raise connection_error() from None
        except (ValueError, TypeError):
            raise TTSError("ElevenLabs returned invalid voice metadata.") from None
