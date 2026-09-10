from dataclasses import replace
import json
import os
from pathlib import Path
import tempfile
from threading import Event
import unittest
from unittest.mock import Mock, patch
import httpx

from app.core.models import SceneItem
from app.core.project_manager import ProjectManager
from app.services.tts.elevenlabs import ElevenLabsTTS
from app.services.tts.settings import TTSSettings
from app.services.tts.service import TTSService, Narration, validate_narration
from app.services.tts.errors import TTSError, TTSCancelled
from app.utils.audio import audio_duration


class TTSTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.settings = TTSSettings(api_key="test-key", cache_dir=self.root)
        self.item = SceneItem(tts_text="Xin chào Việt Nam", voice_id="voice123", tts_text_is_manual=True)

    def test_request_mapping_and_audio(self):
        def handle(request):
            self.assertEqual(request.url.path, "/v1/text-to-speech/voice123")
            self.assertEqual(request.headers["xi-api-key"], "test-key")
            data = json.loads(request.content)
            self.assertEqual(data["text"], self.item.tts_text)
            self.assertEqual(data["voice_settings"]["speed"], 1.1)
            self.assertEqual(data["model_id"], "eleven_flash_v2_5")
            return httpx.Response(200, headers={"content-type": "audio/mpeg"}, content=b"audio-fixture")
        provider = ElevenLabsTTS(self.settings, httpx.MockTransport(handle))
        out = self.root / "audio.mp3"
        self.assertEqual(provider.synthesize(self.item.tts_text, "voice123", out, 1.1), out)
        self.assertEqual(out.read_bytes(), b"audio-fixture")

    def test_api_errors_redacted_no_retry_and_missing_key(self):
        for code in (401, 402, 403, 404, 422, 429, 500):
            handler = Mock(return_value=httpx.Response(code, text="secret response with test-key"))
            provider = ElevenLabsTTS(self.settings, httpx.MockTransport(handler))
            with self.assertRaises(TTSError) as caught:
                provider.synthesize("hello", "voice", self.root / "out.mp3")
            self.assertNotIn("test-key", str(caught.exception))
            self.assertNotIn("secret response", str(caught.exception))
            self.assertEqual(handler.call_count, 1)
            if code == 402:
                self.assertEqual(caught.exception.availability_status, "payment_required")
                self.assertEqual(caught.exception.title, "Voice unavailable via API")
        with self.assertRaisesRegex(TTSError, "API_KEY"):
            ElevenLabsTTS(TTSSettings()).list_voices()

    def test_paginated_voice_list(self):
        def handle(request):
            if "next_page_token" not in request.url.params:
                return httpx.Response(200, json={"voices": [{"voice_id": "a", "name": "One"}], "has_more": True, "next_page_token": "next"})
            return httpx.Response(200, json={"voices": [{"voice_id": "b", "name": "Two"}], "has_more": False})
        self.assertEqual([(v.voice_id, v.name) for v in ElevenLabsTTS(self.settings, httpx.MockTransport(handle)).list_voices()], [("a", "One"), ("b", "Two")])

    def test_non_audio_empty_and_timeout(self):
        for response in (httpx.Response(200, json={}), httpx.Response(200, headers={"content-type":"audio/mpeg"}, content=b"")):
            provider = ElevenLabsTTS(self.settings, httpx.MockTransport(lambda request: response))
            with self.assertRaises(TTSError):
                provider.synthesize("hello", "voice", self.root / "out.mp3")
        def fail(request):
            raise httpx.ReadTimeout("secret")
        with self.assertRaises(TTSError):
            ElevenLabsTTS(self.settings, httpx.MockTransport(fail)).synthesize("hello", "voice", self.root / "out.mp3")

    def test_cache_and_changed_inputs(self):
        provider = Mock()
        provider.synthesize.side_effect = lambda text, voice, out, speed, **kwargs: out.write_bytes(b"audio")
        service = TTSService(self.settings, provider)
        with patch("app.services.tts.service.require_ffprobe"), patch("app.services.tts.service.audio_duration", return_value=2.5):
            first = service.generate(self.item)
            second = service.generate(self.item)
            self.assertFalse(first.cached)
            self.assertTrue(second.cached)
            self.assertEqual(provider.synthesize.call_count, 1)
            for key, value in (("voice_speed", 1.1), ("voice_id", "different"), ("tts_text", "other")):
                setattr(self.item, key, value)
                result = service.generate(self.item)
                self.assertFalse(result.cached)
                self.assertNotEqual(result.path, first.path)

    def test_guard_probe_cancel_and_partial_cleanup(self):
        provider = Mock()
        service = TTSService(self.settings, provider)
        with patch("app.services.tts.service.require_ffprobe", side_effect=TTSError("missing")):
            with self.assertRaises(TTSError):
                service.generate(self.item)
        provider.synthesize.assert_not_called()
        cancel = Event(); cancel.set()
        with self.assertRaises(TTSCancelled):
            service.generate(self.item, cancel)
        self.item.tts_text_is_manual = False
        with self.assertRaises(TTSError):
            validate_narration(self.item)
        self.item.tts_text_is_manual = True
        def partial(text, voice, out, speed, **kwargs):
            out.write_bytes(b"partial")
            raise TTSError("failed")
        provider.synthesize.side_effect = partial
        with patch("app.services.tts.service.require_ffprobe"):
            with self.assertRaises(TTSError):
                service.generate(self.item)
        self.assertEqual(list(self.root.iterdir()), [])

    def test_probe_mapping_and_bad_values(self):
        process = Mock()
        process.returncode = 0
        process.poll.return_value = 0
        with patch("app.utils.audio.require_ffprobe", return_value="ffprobe"), patch("app.utils.audio.subprocess.Popen", return_value=process) as popen:
            process.communicate.return_value = (b'{"format":{"duration":"1.25"},"streams":[{"codec_type":"audio"}]}', b"")
            self.assertEqual(audio_duration(self.root / "spaced name.mp3"), 1.25)
            self.assertIsInstance(popen.call_args.args[0], list)
            for duration in ("nan", "-1", "0"):
                process.communicate.return_value = (json.dumps({"format":{"duration":duration},"streams":[{}]}).encode(), b"")
                with self.assertRaises(TTSError):
                    audio_duration(self.root / "bad.mp3")

    def test_timeline_and_voice_invalidation(self):
        manager = ProjectManager()
        scene = manager.add_single("image.png")
        item = scene.items[0]
        path = self.root / "sound.mp3"; path.write_bytes(b"fixture")
        manager.apply_narration(item, Narration(str(path), 2.0, False))
        self.assertAlmostEqual(manager.refresh_timeline().total_duration, 2.25)
        self.assertEqual(item.timeline_status, "done")
        manager.set_voice(item, "new-voice")
        self.assertEqual(item.audio_path, str(path))
        self.assertIsNone(manager.refresh_timeline())

    def test_environment_precedence_and_secret_repr(self):
        env = self.root / ".env"
        env.write_text('ELEVENLABS_API_KEY="file-key"\nELEVENLABS_VOICE_ID=abc\n', encoding="utf-8")
        with patch.dict(os.environ, {"ELEVENLABS_API_KEY": "env-key"}, clear=True):
            settings = TTSSettings.from_environment(env)
        self.assertEqual(settings.api_key, "env-key")
        self.assertEqual(settings.default_voice, "abc")
        self.assertNotIn("env-key", repr(settings))

    def test_real_ffprobe_wav_and_mp3_service_pipeline(self):
        import subprocess
        import wave
        from app.core.config import ROOT
        from app.utils.audio import require_ffprobe
        ffmpeg = ROOT / "tools/ffmpeg/bin/ffmpeg.exe"
        try:
            require_ffprobe()
        except TTSError:
            self.skipTest("ffprobe unavailable")
        if not ffmpeg.is_file():
            self.skipTest("Local ffmpeg unavailable for MP3 fixture")
        wav = self.root / "voice fixture.wav"
        with wave.open(str(wav), "wb") as stream:
            stream.setnchannels(1); stream.setsampwidth(2); stream.setframerate(24000)
            stream.writeframes(b"\0\0" * 48000)
        self.assertAlmostEqual(audio_duration(wav), 2.0, places=3)
        mp3 = self.root / "fixture.mp3"
        subprocess.run([str(ffmpeg), "-v", "error", "-i", str(wav), "-codec:a", "libmp3lame", str(mp3)],
                       check=True, capture_output=True, timeout=20)
        provider = ElevenLabsTTS(self.settings, httpx.MockTransport(
            lambda request: httpx.Response(200, headers={"content-type": "audio/mpeg"}, content=mp3.read_bytes())))
        service = TTSService(self.settings, provider)
        result = service.generate(self.item)
        self.assertTrue(1.9 < result.duration < 2.2)
        self.assertFalse(result.cached)
        self.assertTrue(service.generate(self.item).cached)
        Path(result.path).write_bytes(b"corrupt audio")
        with self.assertRaises(TTSError):
            service.generate(self.item)
