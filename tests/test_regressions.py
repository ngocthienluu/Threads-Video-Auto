import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
import unittest
from pathlib import Path
from unittest.mock import patch
from PySide6.QtWidgets import QApplication,QDialog,QPlainTextEdit
from app.ui import configure_fonts
from app.ui.main_window import MainWindow
from app.core.models import Project

class ReportedRegressionTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app=QApplication.instance() or QApplication([]);configure_fonts(cls.app)
    def setUp(self):self.window=MainWindow()
    def tearDown(self):self.window.manager.dirty=False;self.window.close()
    def test_reply_only_spelling_updates_tts_and_preserves_manual(self):
        manager=self.window.manager
        scene=manager.add_thread(["question.png","reply.png"])
        question,reply=scene.items
        manager.edit_body(question,"A previous question about something else")
        manager.edit_body(reply,"A standalone reply")
        self.window.refresh(reply.id)
        self.assertEqual(reply.tts_text,"")
        self.window.editor.reply_only.setChecked(True)
        self.assertEqual(reply.tts_text,"A standalone reply")
        def review(dialog):
            dialog.findChild(QPlainTextEdit).setPlainText("A corrected standalone reply")
            return QDialog.Accepted
        with patch.object(QDialog,"exec",review):self.window.editor.review_spelling()
        self.assertEqual(reply.tts_text,"A corrected standalone reply")
        manager.edit_tts(reply,"Keep my manual narration")
        with patch.object(QDialog,"exec",review):self.window.editor.review_spelling()
        self.assertEqual(reply.tts_text,"Keep my manual narration")
        loaded=Project.from_dict(manager.project.to_dict())
        self.assertTrue(loaded.scenes[0].items[1].reply_body_only)
    def test_project_sections_use_readable_selector_and_pages(self):
        self.window.resize(1280,900);self.window.show();self.window.right_tabs.setCurrentIndex(1)
        self.app.processEvents()
        panel=self.window.settings
        for index in range(panel.sections.count()):
            panel.sections.setCurrentIndex(index);self.app.processEvents()
            self.assertEqual(panel.pages.currentIndex(),index)
            self.assertGreaterEqual(panel.sections.height(),panel.sections.fontMetrics().height()+8)
        Path("cache/preview").mkdir(parents=True,exist_ok=True)
        self.window.grab().save("cache/preview/project-settings-regression.png")
