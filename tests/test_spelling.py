import os
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
import unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtWidgets import QApplication, QDialog
from tests.test_ocr import READY
from app.core.spelling import suggest_spelling
from app.ui.comment_editor import CommentEditor
from app.services.ocr.local_ocr import LocalOCR
from app.services.content_extractor.threads_extractor import ThreadsExtractor


class SpellingTests(unittest.TestCase):
    def test_contextual_suggestions_keep_names_and_slang(self):
        text = "Minh mở sap buôn nồi a\nHam nhớ meme ai vẽ\nMinh và Ham, tui, ny, @xin.lổi, 20k"
        result, changes = suggest_spelling(text)
        self.assertIn("Mình mở sạp", result)
        self.assertIn("Hăm nhớ", result)
        self.assertIn("Minh và Ham, tui, ny, @xin.lổi, 20k", result)
        self.assertEqual(len(changes), 2)
        self.assertEqual(suggest_spelling(result)[1], [])

    def test_dialog_cancel_and_save(self):
        app = QApplication.instance() or QApplication([])
        editor = CommentEditor()
        editor.body.setPlainText("xin lổi")
        with patch.object(QDialog, "exec", return_value=QDialog.Rejected):
            editor.review_spelling()
        self.assertEqual(editor.body.toPlainText(), "xin lổi")
        with patch.object(QDialog, "exec", return_value=QDialog.Accepted):
            editor.review_spelling()
        self.assertEqual(editor.body.toPlainText(), "xin lỗi")
        editor.close()

    @unittest.skipUnless(READY, "Local OCR dependencies/models unavailable")
    def test_supplied_media_screenshots(self):
        import hashlib
        for name, expected in (("cmt4.png", "tui vẽ meme cho"), ("cmt5.png", "mượn buôn ít nồi nha")):
            path = Path("input/comments") / name
            if not path.exists():
                self.skipTest("User screenshots are not distributed with the repository")
            before = hashlib.sha256(path.read_bytes()).hexdigest()
            result = ThreadsExtractor().extract(LocalOCR().read_blocks(path))
            self.assertIn(expected, result.body_text)
            self.assertEqual(len(result.body_text.splitlines()), 2)
            self.assertNotIn("1/2", result.body_text)
            self.assertNotIn("syh.27.7", result.body_text)
            self.assertGreater(result.confidence, .8)
            self.assertEqual(before, hashlib.sha256(path.read_bytes()).hexdigest())
