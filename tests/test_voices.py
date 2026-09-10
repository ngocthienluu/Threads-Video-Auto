from pathlib import Path
import json
import tempfile
import unittest
from unittest.mock import Mock, patch
import httpx
from app.services.tts.voices import VoiceInfo, VoiceCatalog
from app.services.tts.elevenlabs import ElevenLabsTTS
from app.services.tts.errors import TTSError, api_error
from app.services.tts.settings import TTSSettings
from app.services.tts.service import TTSService
from app.core.models import Project
from app.core.project_manager import ProjectManager


class VoiceTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def test_metadata_does_not_infer_access(self):
        v = VoiceInfo.parse({"voice_id": "abc", "name": "Dũng", "labels": {"language": "vi", "accent": "southern"},
                             "category": "professional", "available_for_tiers": ["creator"], "permission_on_resource": "admin",
                             "preview_url": "https://example.com/audio.mp3"})
        self.assertEqual((v.language, v.accent, v.name), ("vi", "southern", "Dũng"))
        self.assertEqual(v.availability_status, "unknown")
        self.assertIsNone(v.is_available)
        self.assertIsNone(VoiceInfo.parse({"voice_id": "empty"}).description)
        for data in (None, {}, {"voice_id": 123}, {"voice_id": "a", "labels": []}, {"voice_id": "a", "name": 1}):
            with self.assertRaises(ValueError):
                VoiceInfo.parse(data)

    def test_cache_roundtrip_resets_access_and_omits_secrets(self):
        provider = Mock()
        provider.list_voices.return_value = [VoiceInfo("abc", "Voice", labels={"language": "vi"})]
        catalog = VoiceCatalog(provider, self.root)
        catalog.list_voices()
        catalog.observe("abc")
        catalog.list_voices()
        raw = catalog.path.read_text(encoding="utf-8")
        self.assertNotIn("is_available", raw)
        self.assertNotIn("api_key", raw)
        loaded = VoiceCatalog(provider, self.root)
        self.assertEqual(loaded.load_cache()[0].voice_id, "abc")
        self.assertEqual(loaded.voices[0].availability_status, "unknown")
        self.assertTrue(loaded.fetched_at)
        provider.list_voices.side_effect = api_error(401)
        with self.assertRaises(TTSError):
            loaded.list_voices()
        self.assertEqual(len(loaded.voices), 1)
        catalog.path.write_text("bad json")
        broken = VoiceCatalog(provider, self.root)
        self.assertEqual(broken.load_cache(), [])
        self.assertTrue(broken.warning)

    def test_cache_write_failure_keeps_fresh_list(self):
        provider = Mock()
        provider.list_voices.return_value = [VoiceInfo("abc")]
        catalog = VoiceCatalog(provider, self.root)
        with patch("app.services.tts.voices.os.replace", side_effect=PermissionError):
            self.assertEqual(catalog.list_voices()[0].voice_id, "abc")
        self.assertIn("could not be saved", catalog.warning)

    def test_details_and_status_mapping(self):
        def response(request):
            self.assertEqual(request.url.path, "/v1/voices/abc")
            return httpx.Response(200, json={"voice_id": "abc", "name": "One"})
        provider = ElevenLabsTTS(TTSSettings(api_key="test"), httpx.MockTransport(response))
        self.assertEqual(provider.get_voice_details("abc").name, "One")
        catalog = VoiceCatalog(provider, self.root)
        for code, status in ((401, "unauthorized"), (402, "payment_required"), (403, "restricted"), (429, "error")):
            self.assertEqual(catalog.observe("abc", api_error(code)).availability_status, status)
        self.assertTrue(catalog.observe("abc").is_available)

    def test_explicit_test_forces_short_sample_without_modifying_item(self):
        service = Mock()
        catalog = VoiceCatalog(Mock(), self.root)
        catalog.validate_voice_access("abc", service)
        sample = service.generate.call_args.args[0]
        self.assertEqual((sample.voice_id, sample.tts_text), ("abc", "Xin chào"))
        self.assertTrue(service.generate.call_args.kwargs["force"])

    def test_force_failure_preserves_cached_audio(self):
        provider = Mock()
        provider.synthesize.side_effect = lambda text, voice, path, speed, **kw: path.write_bytes(b"valid")
        service = TTSService(TTSSettings(cache_dir=self.root), provider)
        from app.core.models import SceneItem
        item = SceneItem(tts_text="Hello", voice_id="abc", tts_text_is_manual=True)
        with patch("app.services.tts.service.require_ffprobe"), patch("app.services.tts.service.audio_duration", return_value=1.0):
            first = service.generate(item)
            provider.synthesize.side_effect = api_error(402)
            with self.assertRaises(TTSError):
                service.generate(item, force=True)
        self.assertEqual(Path(first.path).read_bytes(), b"valid")

    def test_project_defaults_item_override_legacy_and_persistence(self):
        manager = ProjectManager()
        image = self.root / "img.png"; image.write_bytes(b"fixture")
        first = manager.add_single(str(image)).items[0]
        second = manager.add_single(str(image)).items[0]
        manager.set_default_voice("default", "Voice name")
        manager.set_voice(second, "override")
        manager.set_tts_model("eleven_flash_v2_5")
        path = self.root / "project.json"
        manager.save(path)
        loaded = ProjectManager(); loaded.load(path)
        self.assertEqual(loaded.project.default_voice_id, "default")
        self.assertEqual([s.items[0].voice_id for s in loaded.project.scenes], ["", "override"])
        self.assertEqual(loaded.project.tts_model_id, "eleven_flash_v2_5")
        self.assertNotIn("API_KEY", path.read_text())
        self.assertEqual(Project.from_dict({"schema_version": 1}).default_voice_id, "")
