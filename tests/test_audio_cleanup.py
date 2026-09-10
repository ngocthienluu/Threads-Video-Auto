import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from app.core.project_manager import ProjectManager
from app.services.tts.cleanup import AudioCleanup, CleanupError


class AudioCleanupTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve()
        self.cache = self.root / "cache/tts"; self.cache.mkdir(parents=True)
        self.projects = self.root / "projects"; self.projects.mkdir()
        self.service = AudioCleanup(self.cache, self.projects)
        self.manager = ProjectManager()

    def audio(self, char):
        path = self.cache / (char * 64 + ".mp3")
        path.write_bytes(b"audio")
        return path

    def saved(self, name, audio):
        manager = ProjectManager()
        item = manager.add_single(str(self.root / "image.png")).items[0]
        item.audio_path = str(audio)
        path = self.projects / name
        manager.save(path)
        return path

    def test_saved_shared_and_unsaved_audio_protected(self):
        saved, current, unused = self.audio("a"), self.audio("b"), self.audio("c")
        self.saved("one.json", saved); self.saved("two.json", saved)
        self.manager.add_single("image.png").items[0].audio_path = str(current)
        metadata = self.cache / "elevenlabs_voices.json"; metadata.write_text("{}")
        temp = self.cache / "tmp123.mp3"; temp.write_bytes(b"in progress")
        plan = self.service.scan(self.manager.project.to_dict())
        self.assertEqual([p.path for p in plan.candidates], [unused])
        self.assertEqual((plan.project_count, plan.protected_count, plan.bytes), (2, 2, 5))
        removed, freed, skipped = self.service.delete(plan, self.manager.project.to_dict())
        self.assertEqual((removed, freed, skipped), (1, 5, []))
        self.assertTrue(all(p.exists() for p in (saved, current, metadata, temp)))

    def test_malformed_or_missing_project_blocks_all_deletion(self):
        unused = self.audio("a")
        plan = self.service.scan({})
        broken = self.projects / "broken.json"; broken.write_text("invalid")
        with self.assertRaises(CleanupError):
            self.service.delete(plan, {})
        self.assertTrue(unused.exists())
        broken.unlink()
        self.service.remember(self.root / "external/missing.json")
        with self.assertRaises(CleanupError):
            self.service.scan({})

    def test_saved_project_added_after_preview_and_modified_audio_are_kept(self):
        saved, changed = self.audio("a"), self.audio("b")
        plan = self.service.scan({})
        self.saved("later.json", saved)
        changed.write_bytes(b"new audio content")
        result = self.service.delete(plan, {})
        self.assertEqual(result[0], 0)
        self.assertEqual(len(result[2]), 2)
        self.assertTrue(saved.exists() and changed.exists())

    def test_external_registered_and_extra_projects_are_protected(self):
        saved = self.audio("a")
        original = self.saved("external.json", saved)
        external = self.root / "external.json"
        manager = ProjectManager(); manager.load(original); manager.save(external)
        original.unlink()
        self.assertEqual(len(self.service.scan({}, extra_projects=[external]).candidates), 0)
        self.service.remember(external)
        self.assertIn(external, self.service.known_projects())
        self.assertEqual(len(self.service.scan({}).candidates), 0)

    def test_other_media_references_and_delete_permission_error(self):
        music, unused = self.audio("a"), self.audio("b")
        current = {"music_settings": {"file": str(music)}}
        plan = self.service.scan(current)
        self.assertEqual([entry.path for entry in plan.candidates], [unused])
        with patch.object(Path, "unlink", side_effect=PermissionError):
            result = self.service.delete(plan, current)
        self.assertEqual(result, (0, 0, [unused.name]))

    def test_corrupt_registry_blocks_and_outside_approved_path_not_deleted(self):
        self.service.registry.write_text("{}")
        with self.assertRaises(CleanupError):
            self.service.scan({})
        self.service.registry.unlink()
        from app.services.tts.cleanup import Candidate, CleanupPlan
        outside = self.root / ("c" * 64 + ".mp3"); outside.write_bytes(b"safe")
        info = outside.stat()
        plan = CleanupPlan([Candidate(outside, info.st_size, info.st_mtime_ns, info.st_ino)], 0, 0)
        self.assertEqual(self.service.delete(plan, {})[0], 0)
        self.assertTrue(outside.exists())

    def test_linked_cache_is_refused(self):
        with patch("app.services.tts.cleanup.linked", return_value=True):
            with self.assertRaises(CleanupError):
                self.service.scan({})
