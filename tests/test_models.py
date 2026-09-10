import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from app.core.models import ItemRole, MemeConfig, Project, SceneType, SfxConfig
from app.core.project_manager import ProjectManager


class ModelTests(unittest.TestCase):
    def test_single_thread_serialization(self):
        manager = ProjectManager()
        single = manager.add_single("one.png")
        thread = manager.add_thread(["q.png", "r1.png", "r2.png"])
        thread.items[1].meme = MemeConfig(file="meme.mp4")
        thread.items[2].sfx = SfxConfig(file="boom.mp3", offset=-.2)
        manager.edit_tts(thread.items[1], "reply only")
        clone = Project.from_dict(json.loads(json.dumps(manager.project.to_dict())))
        self.assertEqual(clone, manager.project)
        self.assertEqual(single.items[0].role, ItemRole.SINGLE)
        self.assertEqual(thread.scene_type, SceneType.THREAD)
        self.assertEqual([item.role for item in thread.items], [ItemRole.QUESTION, ItemRole.REPLY, ItemRole.REPLY])

    def test_independent_defaults(self):
        first, second = Project(), Project()
        first.video_settings.fps = 60
        self.assertEqual(second.video_settings.fps, 30)
        self.assertNotEqual(first.id, second.id)

    def test_save_load_paths_manual_and_missing(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            image = base / "ảnh câu hỏi.png"
            image.write_bytes(b"reference only")
            manager = ProjectManager()
            scene = manager.add_thread([str(image), str(base / "missing.png")])
            manager.edit_tts(scene.items[1], "trả lời thủ công")
            folder = base / "projects"
            folder.mkdir()
            target = folder / "dự án.json"
            manager.save(target)
            stored = json.loads(target.read_text(encoding="utf-8"))
            self.assertEqual(stored["scenes"][0]["items"][0]["original_image_path"], "../ảnh câu hỏi.png")
            fresh = ProjectManager()
            missing = fresh.load(target)
            self.assertEqual(fresh.project, manager.project)
            self.assertEqual(missing, [str(base / "missing.png")])
            self.assertFalse(fresh.dirty)

    def test_invalid_load_keeps_current_project(self):
        with tempfile.TemporaryDirectory() as tmp:
            manager = ProjectManager()
            manager.add_single("keep.png")
            original = manager.project
            target = Path(tmp) / "bad.json"
            for data in ("{", "[]", '{}', '{"schema_version":2}', '{"schema_version":1,"scenes":"bad"}'):
                target.write_text(data)
                with self.subTest(data=data), self.assertRaises(ValueError):
                    manager.load(target)
                self.assertIs(manager.project, original)

    def test_strict_validation(self):
        manager = ProjectManager()
        manager.add_thread(["q.png", "r.png"])
        invalid = [
            lambda d: d.update(schema_version=True),
            lambda d: d.update(unknown="ignored?"),
            lambda d: d["scenes"][0]["items"][0].update(role="reply"),
            lambda d: d["scenes"][0]["items"][0].update(audio_duration=float("nan")),
            lambda d: d["scenes"][0]["items"][0].update(tts_text_is_manual="false"),
            lambda d: d["scenes"][0]["items"][1].update(id=d["scenes"][0]["items"][0]["id"]),
            lambda d: d["timing_settings"].update(scene_gap=-1),
            lambda d: d["video_settings"].update(width=0),
        ]
        for mutate in invalid:
            data = manager.project.to_dict()
            mutate(data)
            with self.assertRaises(ValueError):
                Project.from_dict(data)

    def test_atomic_save_preserves_previous_on_failure(self):
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project.json"
            manager = ProjectManager()
            manager.save(target)
            previous = target.read_bytes()
            manager.add_single("new.png")
            with patch("app.core.project_manager.os.replace", side_effect=PermissionError("locked")):
                with self.assertRaises(PermissionError):
                    manager.save(target)
            self.assertEqual(target.read_bytes(), previous)
            self.assertTrue(manager.dirty)
            self.assertEqual(list(Path(tmp).glob("*.tmp")), [])

    def test_manual_tts_protected_even_when_empty(self):
        manager = ProjectManager()
        item = manager.add_single("one.png").items[0]
        manager.edit_ocr(item, "hôm nay vui =)))")
        self.assertTrue(manager.prepare_tts(item))
        self.assertEqual(item.tts_text, "hôm nay vui")
        for manual in ("hôm nay vui quá", ""):
            manager.edit_tts(item, manual)
            self.assertFalse(manager.prepare_tts(item))
            self.assertEqual(item.tts_text, manual)
        self.assertTrue(manager.prepare_tts(item, overwrite_manual=True))
        self.assertFalse(item.tts_text_is_manual)

    def test_audio_invalidation_after_text_and_voice(self):
        manager = ProjectManager()
        item = manager.add_single("one.png").items[0]
        for index, edit in enumerate((lambda: manager.edit_tts(item, "new words"), lambda: manager.set_voice(item, "new-voice"))):
            item.audio_path, item.audio_duration, item.tts_status = "voice.mp3", 4.2, "done"
            item.start_time, item.end_time, item.timeline_status = 1, 5.2, "done"
            edit()
            self.assertEqual((item.audio_path, item.audio_duration, item.tts_status),
                             ("", 0, "pending") if index == 0 else ("voice.mp3", 4.2, "pending"))
            self.assertEqual((item.start_time, item.end_time, item.timeline_status), (0, 0, "pending"))

    def test_reply_cleaning_never_repeats_cumulative_question(self):
        manager = ProjectManager()
        reply = manager.add_thread(["q.png", "q_r.png"]).items[1]
        manager.edit_ocr(reply, "question plus reply")
        with self.assertRaises(ValueError):
            manager.prepare_tts(reply)
        manager.edit_tts(reply, "reply only")
        self.assertFalse(manager.prepare_tts(reply))

    def test_scene_mutations(self):
        manager = ProjectManager()
        single = manager.add_single("s.png")
        thread = manager.add_thread(["q.png"])
        reply = manager.add_thread_item(thread, "r.png")
        with self.assertRaises(ValueError):
            manager.add_thread_item(single, "bad.png")
        manager.move(thread, None, -1)
        self.assertIs(manager.project.scenes[0], thread)
        manager.move(thread, reply, -1)
        self.assertEqual(reply.role, ItemRole.QUESTION)
        manager.delete(thread, reply)
        self.assertEqual(thread.items[0].role, ItemRole.QUESTION)
        manager.project.validate()
        manager.delete(thread, thread.items[0])
        self.assertEqual(manager.project.scenes, [single])
