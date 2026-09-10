import os
os.environ["QT_QPA_PLATFORM"] = "offscreen"

from pathlib import Path
import tempfile
import unittest
from threading import Event
from time import monotonic
from unittest.mock import patch
from app.core.ocr_models import OCRResult

try:
    from PySide6.QtGui import QImage
    from PySide6.QtWidgets import QApplication, QMessageBox
    from PySide6.QtTest import QTest
    from PySide6.QtCore import QThread
    from app.ui.main_window import MainWindow
    from app.ui import configure_fonts
except ImportError:
    QApplication = None


@unittest.skipIf(QApplication is None, "PySide6 is not installed")
class UITests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        configure_fonts(cls.app)

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.image = Path(self.temp.name) / "ảnh.png"
        image = QImage(240, 120, QImage.Format.Format_RGB32)
        image.fill(0xffffff)
        self.assertTrue(image.save(str(self.image)))
        from app.services.tts.settings import TTSSettings
        with patch.object(TTSSettings, "from_environment", return_value=TTSSettings(cache_dir=Path(self.temp.name) / "tts")):
            self.window = MainWindow()
        self.window.show()
        self.app.processEvents()

    def tearDown(self):
        self.window.manager.dirty = False
        self.window.close()
        self.app.processEvents()
        self.temp.cleanup()

    def test_authoring_and_manual_safety(self):
        self.window.import_paths([str(self.image)])
        item = self.window.item
        self.assertIsNotNone(item)
        self.window.editor.body.setPlainText("hôm nay vui =)))")
        self.window.editor.clean.click()
        self.assertEqual(item.tts_text, "hôm nay vui")
        self.window.editor.tts.setPlainText("hôm nay vui quá")
        self.window.editor.clean.click()
        self.assertEqual(item.tts_text, "hôm nay vui quá")
        self.window.editor.overwrite.setChecked(True)
        self.window.editor.clean.click()
        self.assertEqual(item.tts_text, "hôm nay vui")
        self.assertFalse(self.window.preview.pixmap.isNull())
        self.assertTrue(self.window.auto_button.isEnabled())
        self.assertFalse(self.window.export_button.isEnabled())

    def test_thread_add_reorder_delete_and_roundtrip(self):
        self.window.import_paths([str(self.image)], "thread")
        self.window.import_paths([str(self.image)], "reply")
        self.window.editor.tts.setPlainText("reply only")
        self.assertEqual(len(self.window.scene.items), 2)
        self.assertEqual(self.window.item.role.value, "reply")
        self.window.move_selected(-1)
        self.assertEqual(self.window.item.role.value, "question")
        target = Path(self.temp.name) / "project.json"
        self.window.manager.save(target)
        self.window.manager.load(target)
        self.window.refresh()
        scene = self.window.manager.project.scenes[0]
        self.window.refresh(scene.items[1].id)
        self.window.delete_selected()
        self.assertEqual(len(scene.items), 1)

    def test_bad_import_is_atomic_and_visible(self):
        bad = Path(self.temp.name) / "broken.png"
        bad.write_text("not an image")
        with patch.object(QMessageBox, "warning") as warning:
            self.window.import_paths([str(self.image), str(bad)])
        warning.assert_called_once()
        self.assertEqual(self.window.manager.project.scenes, [])

    def test_close_cancel_preserves_unsaved_changes(self):
        self.window.import_paths([str(self.image)])
        with patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Cancel):
            self.assertFalse(self.window.close())
        self.assertTrue(self.window.manager.dirty)

    def wait_ocr(self):
        deadline = monotonic() + 5
        while self.window.ocr_controller.busy and monotonic() < deadline:
            self.app.processEvents()
            QTest.qWait(10)
        self.assertFalse(self.window.ocr_controller.busy)

    def test_ocr_worker_result_and_manual_tts_preserved(self):
        self.window.import_paths([str(self.image)])
        item = self.window.item
        self.window.editor.tts.setPlainText("manual narration")
        gui_thread = QThread.currentThread()
        def recognize(path, cancel=None):
            self.assertNotEqual(QThread.currentThread(), gui_thread)
            return OCRResult(full_text="Xin chào =)))")
        with patch.object(self.window.ocr_controller.provider, "read_blocks", side_effect=recognize):
            self.window.editor.read_image.click()
            self.assertFalse(self.window.centralWidget().isEnabled())
            self.wait_ocr()
        self.assertTrue(self.window.centralWidget().isEnabled())
        self.assertEqual(item.ocr_text, "Xin chào =)))")
        self.assertEqual(item.tts_text, "manual narration")
        self.assertEqual(item.ocr_status, "done")

    def test_ocr_failure_restores_ui_and_keeps_text(self):
        from app.services.ocr.errors import OCRError
        self.window.import_paths([str(self.image)])
        self.window.manager.edit_ocr(self.window.item, "existing OCR")
        with patch.object(self.window.ocr_controller.provider, "read_blocks", side_effect=OCRError("Missing language data")), patch.object(QMessageBox, "warning") as warning:
            self.window.editor.read_image.click()
            self.wait_ocr()
        warning.assert_called_once()
        self.assertEqual(self.window.item.ocr_text, "existing OCR")
        self.assertEqual(self.window.item.ocr_status, "error")
        self.assertTrue(self.window.centralWidget().isEnabled())

    def test_ocr_cancel_keeps_text_and_window_responsive(self):
        from app.services.ocr.errors import OCRCancelled
        self.window.import_paths([str(self.image)])
        def recognize(path, cancel=None):
            cancel.wait(3)
            raise OCRCancelled("Cancelled")
        with patch.object(self.window.ocr_controller.provider, "read_blocks", side_effect=recognize):
            self.window.editor.read_image.click()
            self.app.processEvents()
            self.window.cancel_ocr_button.click()
            self.wait_ocr()
        self.assertEqual(self.window.item.ocr_text, "")
        self.assertEqual(self.window.item.ocr_status, "pending")
        self.assertTrue(self.window.centralWidget().isEnabled())

    def test_close_during_ocr_cancels_then_checks_unsaved(self):
        from app.services.ocr.errors import OCRCancelled
        self.window.import_paths([str(self.image)])
        def recognize(path, cancel=None):
            cancel.wait(3)
            raise OCRCancelled("Cancelled")
        with patch.object(self.window.ocr_controller.provider, "read_blocks", side_effect=recognize), patch.object(QMessageBox, "question", return_value=QMessageBox.StandardButton.Cancel):
            self.window.editor.read_image.click()
            self.assertFalse(self.window.close())
            self.wait_ocr()
            QTest.qWait(30)
        self.assertTrue(self.window.isVisible())

    def test_reply_selected_text_only(self):
        from PySide6.QtGui import QTextCursor
        self.window.import_paths([str(self.image)], "thread")
        self.window.import_paths([str(self.image)], "reply")
        self.window.editor.ocr.setPlainText("Question\nReply =)))")
        cursor = self.window.editor.ocr.textCursor()
        cursor.setPosition(len("Question\n"))
        cursor.movePosition(QTextCursor.MoveOperation.End, QTextCursor.MoveMode.KeepAnchor)
        self.window.editor.ocr.setTextCursor(cursor)
        self.window.editor.use_selection.click()
        self.assertEqual(self.window.item.tts_text, "Reply")
        self.assertTrue(self.window.item.tts_text_is_manual)

    def test_auto_generate_text_populates_single_and_progressive_replies(self):
        from tests.test_content_extractor import screenshot
        question = "Vậy làm cách nào để nhìn trước tương lai đi"
        self.window.import_paths([str(self.image)], "thread")
        self.window.import_paths([str(self.image)], "reply")
        self.assertTrue(self.window.editor.advanced.isHidden())
        self.assertTrue(self.window.editor.ocr.isReadOnly())
        with patch.object(self.window.ocr_controller.provider, "read_blocks",
                          side_effect=[screenshot([question]), screenshot([question, "Xem lịch"])]):
            self.window.auto_button.click()
            self.wait_ocr()
        items = self.window.manager.project.scenes[0].items
        self.assertEqual([item.tts_text for item in items], [question, "Xem lịch"])
        self.assertEqual(self.window.editor.body.toPlainText(), question + "\nXem lịch")
        self.assertFalse(self.window.item.needs_review)

    def test_rerun_extraction_replaces_manual_body_but_not_manual_tts(self):
        from tests.test_content_extractor import screenshot
        self.window.import_paths([str(self.image)])
        with patch.object(self.window.ocr_controller.provider, "read_blocks", return_value=screenshot(["Nội dung gốc được nhận diện"])):
            self.window.editor.read_image.click()
            self.wait_ocr()
        self.window.editor.body.setPlainText("Nội dung sửa tay")
        self.window.editor.tts.setPlainText("Lời đọc sửa tay")
        self.window.editor.show_advanced.setChecked(True)
        self.window.editor.rerun.click()
        self.wait_ocr()
        self.assertEqual(self.window.item.body_text, "Nội dung gốc được nhận diện")
        self.assertEqual(self.window.item.tts_text, "Lời đọc sửa tay")

    def test_switch_ocr_engine_routes_reads_and_preserves_manual_text(self):
        from unittest.mock import Mock
        from tests.test_content_extractor import screenshot
        self.window.import_paths([str(self.image)])
        service = self.window.ocr_controller.provider
        paddle, tesseract = Mock(), Mock()
        paddle.read_blocks.return_value = screenshot(["Paddle detected content"])
        tesseract.read_blocks.return_value = screenshot(["Tesseract detected content"])
        service.providers = {"paddle": paddle, "tesseract": tesseract}
        combo = self.window.settings.ocr_engine
        for name, engine in (("tesseract", tesseract), ("paddle", paddle)):
            combo.setCurrentIndex(combo.findData(name))
            self.assertEqual(service.settings.ocr_provider, name)
            self.window.editor.read_image.click()
            self.assertFalse(combo.isEnabled())
            self.wait_ocr()
            self.assertTrue(combo.isEnabled())
            engine.read_blocks.assert_called_once()
            self.assertEqual(self.window.item.body_text, engine.read_blocks.return_value.blocks[1].text)
        self.window.editor.body.setPlainText("Manual body")
        self.window.editor.tts.setPlainText("Manual narration")
        combo.setCurrentIndex(combo.findData("tesseract"))
        self.window.refresh(self.window.item.id)
        self.assertEqual(combo.currentData(), "tesseract")
        self.assertEqual(self.window.item.body_text, "Manual body")
        self.assertEqual(self.window.item.tts_text, "Manual narration")
        self.assertIs(service.providers["paddle"], paddle)

    def wait_voice(self):
        for _ in range(200):
            if not self.window.tts_controller.busy:
                return
            QTest.qWait(20)
        self.fail("Voice worker did not finish")

    def test_cleanup_preview_then_delete_keeps_current_audio(self):
        from app.ui.audio_cleanup_dialog import AudioCleanupDialog
        from app.services.tts.cleanup import AudioCleanup
        self.window.import_paths([str(self.image)])
        cache = Path(self.temp.name) / "cleanup"; cache.mkdir()
        saved = cache / ("a" * 64 + ".mp3"); saved.write_bytes(b"keep")
        unused = cache / ("b" * 64 + ".mp3"); unused.write_bytes(b"remove")
        self.window.item.audio_path = str(saved)
        service = AudioCleanup(cache, Path(self.temp.name) / "projects")
        dialog = AudioCleanupDialog(self.window, service, self.window.manager)
        dialog.show()
        self.app.processEvents()
        for _ in range(100):
            if not dialog.busy:
                break
            QTest.qWait(20)
        self.assertFalse(dialog.busy)
        self.assertTrue(dialog.remove.isEnabled())
        self.assertTrue(unused.exists())  # Opening the dialog never deletes.
        self.assertEqual(len(dialog.plan.candidates), 1)
        dialog.remove.click()
        for _ in range(100):
            if not dialog.busy:
                break
            QTest.qWait(20)
        self.assertFalse(dialog.busy)
        self.assertFalse(unused.exists())
        self.assertTrue(saved.exists())
        self.assertFalse(dialog.remove.isEnabled())
        dialog.close()

    def test_cleanup_is_blocked_during_voice_job(self):
        self.window.tts_controller.busy = True
        with patch("app.ui.main_window.AudioCleanupDialog") as dialog:
            self.window.clean_audio_cache()
            dialog.assert_not_called()
        self.window.tts_controller.busy = False

    def test_voice_generation_and_input_invalidation(self):
        from app.services.tts.service import Narration
        self.assertEqual(self.window.settings.ocr_engine.currentData(), "tesseract")
        self.window.import_paths([str(self.image)])
        self.window.editor.tts.setPlainText("Lời đọc đã kiểm tra")
        self.window.editor.voice_panel.manual.setText("voice123")
        self.window.editor.voice_panel.enter_manual()
        path = Path(self.temp.name) / "audio.mp3"
        path.write_bytes(b"fixture")
        with patch.object(self.window.tts_controller.service, "generate", return_value=Narration(str(path), 2.5, True)) as generate:
            self.window.editor.regenerate.click()
            self.assertFalse(self.window.settings.ocr_engine.isEnabled())
            self.wait_voice()
        self.assertEqual(generate.call_args.args[0].tts_text, "Lời đọc đã kiểm tra")
        self.assertTrue(self.window.item.tts_text_is_manual)
        self.assertEqual(self.window.item.tts_status, "done")
        self.assertEqual(self.window.item.timeline_status, "done")
        self.assertIn("2.75s", self.window.timeline_label.text())
        self.assertTrue(self.window.editor.open_audio.isEnabled())
        self.window.editor.speed.setValue(1.1)
        self.assertEqual(self.window.item.audio_path, str(path))
        self.assertEqual(self.window.item.tts_status, "pending")

    def test_voice_error_and_cancel_keep_manual_text(self):
        from app.services.tts.errors import TTSError, TTSCancelled
        self.window.import_paths([str(self.image)])
        self.window.editor.tts.setPlainText("Keep this narration")
        self.window.editor.voice_panel.manual.setText("voice123")
        self.window.editor.voice_panel.enter_manual()
        with patch.object(self.window.tts_controller.service, "generate", side_effect=TTSError("Missing API key")), patch.object(QMessageBox, "warning") as warning:
            self.window.editor.regenerate.click()
            self.wait_voice()
        self.assertTrue(warning.called)
        self.assertEqual(self.window.item.tts_status, "error")
        def cancel(item, event):
            event.wait(2)
            raise TTSCancelled("Cancelled")
        with patch.object(self.window.tts_controller.service, "generate", side_effect=cancel), patch.object(QMessageBox, "warning") as warning:
            self.window.editor.regenerate.click()
            self.window.cancel_tts_button.click()
            self.wait_voice()
        self.assertFalse(warning.called)
        self.assertEqual(self.window.item.tts_text, "Keep this narration")
        self.assertTrue(self.window.editor.isEnabled())

    def test_load_voices_preserves_selected_id(self):
        from app.services.tts.voices import VoiceInfo
        self.window.import_paths([str(self.image)])
        self.window.editor.voice_panel.manual.setText("voice123")
        self.window.editor.voice_panel.enter_manual()
        with patch.object(self.window.tts_controller.service.provider, "list_voices", return_value=[VoiceInfo("voice123", "Vietnamese Voice")]):
            self.window.editor.load_voices.click()
            self.wait_voice()
        self.assertEqual(self.window.editor.selected_voice(), "voice123")
        self.assertIn("Vietnamese Voice", self.window.editor.voice.currentText())

    def test_voice_restriction_preserves_old_audio_and_persistent_status(self):
        from app.services.tts.errors import api_error
        from app.services.tts.service import Narration
        self.window.import_paths([str(self.image)])
        editor = self.window.editor
        editor.tts.setPlainText("Reviewed narration")
        panel = editor.voice_panel
        panel.manual.setText("old"); panel.enter_manual()
        audio = Path(self.temp.name) / "old.mp3"; audio.write_bytes(b"previous")
        self.window.manager.apply_narration(self.window.item, Narration(str(audio), 2.0, False))
        panel.manual.setText("restricted"); panel.enter_manual()
        with patch.object(self.window.tts_controller.service, "generate", side_effect=api_error(402)), patch.object(QMessageBox, "warning") as warning:
            editor.regenerate.click()
            self.wait_voice()
        self.assertEqual(warning.call_args.args[1], "Voice unavailable via API")
        self.assertEqual(self.window.item.audio_path, str(audio))
        self.assertEqual(audio.read_bytes(), b"previous")
        self.assertEqual(self.window.item.timeline_status, "pending")
        self.assertTrue(editor.open_audio.isEnabled())
        self.assertIn("Payment/API access required", panel.status.text())
        self.window.refresh(self.window.item.id)
        self.assertIn("Payment/API access required", panel.status.text())
        self.assertEqual(editor.tts.toPlainText(), "Reviewed narration")

    def test_test_voice_does_not_replace_narration_and_cached_generate_is_not_access_proof(self):
        from app.services.tts.service import Narration
        self.window.import_paths([str(self.image)])
        editor = self.window.editor
        panel = editor.voice_panel
        panel.manual.setText("abc"); panel.enter_manual()
        editor.tts.setPlainText("Keep narration")
        audio = Path(self.temp.name) / "old.mp3"; audio.write_bytes(b"old")
        self.window.manager.apply_narration(self.window.item, Narration(str(audio), 2.0, True))
        with patch.object(self.window.tts_controller.service, "generate", return_value=Narration(str(audio), 2.0, True)):
            editor.regenerate.click(); self.wait_voice()
        self.assertIn("not confirmed", panel.status.text())
        with patch.object(self.window.tts_controller.catalog, "validate_voice_access", return_value=Narration("sample.mp3", .5, False)) as test:
            panel.test.click()
            self.assertFalse(panel.test.isEnabled())
            self.wait_voice()
        test.assert_called_once()
        self.assertIn("Available via API", panel.status.text())
        self.assertEqual(self.window.item.audio_path, str(audio))
        self.assertEqual(self.window.item.audio_duration, 2.0)
        self.assertEqual(editor.tts.toPlainText(), "Keep narration")

    def test_refresh_failure_keeps_cache_search_and_default(self):
        from app.services.tts.voices import VoiceInfo
        from app.services.tts.errors import api_error
        self.window.import_paths([str(self.image)])
        panel = self.window.editor.voice_panel
        catalog = self.window.tts_controller.catalog
        catalog.voices = [VoiceInfo("a", "Vietnamese voice", language="vi"), VoiceInfo("b", "English", language="en")]
        self.window.editor.set_voices(catalog.voices)
        panel.combo.setCurrentIndex(panel.combo.findData("a"))
        panel.set_default.click()
        panel.combo.setCurrentIndex(0)
        self.assertEqual(self.window.item.voice_id, "")
        self.assertEqual(panel.selected_voice(), "a")
        with patch.object(catalog.provider, "list_voices", side_effect=api_error(401)), patch.object(QMessageBox, "warning"):
            panel.refresh.click(); self.wait_voice()
        self.assertIn("Showing cached list", panel.notice.text())
        panel.search.setText("vi")
        self.assertGreaterEqual(panel.combo.findData("a"), 0)
        self.assertEqual(panel.combo.findData("b"), -1)
        self.assertEqual(self.window.manager.project.default_voice_id, "a")
        self.assertEqual(self.window.item.voice_id, "")

    def test_forced_regeneration_failure_keeps_valid_audio(self):
        from app.services.tts.service import Narration
        from app.services.tts.errors import api_error
        self.window.import_paths([str(self.image)])
        editor = self.window.editor
        editor.tts.setPlainText("Reviewed text")
        editor.voice_panel.manual.setText("a"); editor.voice_panel.enter_manual()
        self.window.manager.project.tts_model_id = self.window.tts_controller.service.settings.model
        path = Path(self.temp.name) / "previous.mp3"; path.write_bytes(b"audio")
        self.window.manager.apply_narration(self.window.item, Narration(str(path), 2.0, False))
        with patch.object(self.window.tts_controller.service, "generate", side_effect=api_error(403)) as generate, patch.object(QMessageBox, "warning"):
            editor.voice_panel.regenerate.click(); self.wait_voice()
        self.assertTrue(generate.call_args.kwargs["force"])
        self.assertEqual(self.window.item.tts_status, "done")
        self.assertEqual(self.window.item.audio_path, str(path))
        self.assertEqual(self.window.item.timeline_status, "done")
