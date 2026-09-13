import logging
from pathlib import Path
from PySide6.QtCore import Qt
from PySide6.QtWidgets import (QFileDialog, QHBoxLayout, QLabel, QMainWindow, QMessageBox,
                               QProgressBar, QPushButton, QScrollArea, QSplitter, QVBoxLayout, QWidget)
from app.core.config import ROOT
from app.core.project_manager import ProjectManager
from app.core.models import SceneType
from app.ui.comment_editor import CommentEditor
from app.ui.preview_widget import PreviewWidget
from app.ui.scene_list import SceneList
from app.ui.settings_panel import SettingsPanel
from app.ui.ocr_controller import OCRController
from app.ui.tts_controller import TTSController
from app.ui.render_controller import RenderController
from app.services.tts.cleanup import AudioCleanup, CleanupError
from app.ui.audio_cleanup_dialog import AudioCleanupDialog
from app.utils.files import IMAGE_FILTER, validate_image

log = logging.getLogger(__name__)


class MainWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.manager = ProjectManager()
        self.scene = self.item = None
        self.resize(1200, 850)
        central = QWidget()
        layout = QVBoxLayout(central)
        self.setCentralWidget(central)
        toolbar = QHBoxLayout()
        self.import_button = self._button("IMPORT", self.import_images, toolbar)
        self._button("Open", self.open_project, toolbar)
        self._button("Save", self.save_project, toolbar)
        self._button("Save As", lambda: self.save_project(save_as=True), toolbar)
        toolbar.addStretch()
        self.auto_button = self._button("AUTO GENERATE TEXT", lambda: self.ocr_controller.start(all_items=True), toolbar)
        self.auto_button.setToolTip("OCR → detect comments → prepare TTS text for all items. Generate narration separately, then export MP4.")
        self._button("PREVIEW", self.preview_selected, toolbar)
        self.export_button = self._button("EXPORT", lambda: self.render_controller.start(), toolbar)
        self.export_button.setToolTip("Export gameplay, screenshots and existing narration to MP4")
        layout.addLayout(toolbar)
        banner = QLabel("Threads OCR · ElevenLabs narration (API key + ffprobe required) · MP4 export with gameplay, music and watermark.")
        banner.setWordWrap(True)
        layout.addWidget(banner)
        splitter = QSplitter(Qt.Orientation.Horizontal)
        left = QWidget()
        left_layout = QVBoxLayout(left)
        self.scenes = SceneList()
        left_layout.addWidget(self.scenes)
        self._button("Add Single / Image", self.import_images, left_layout)
        self._button("Add Thread (question image)", self.add_thread, left_layout)
        self.add_reply_button = self._button("Add Thread Item", self.add_reply, left_layout)
        self._button("Delete selected", self.delete_selected, left_layout)
        moves = QHBoxLayout()
        self._button("Move Up", lambda: self.move_selected(-1), moves)
        self._button("Move Down", lambda: self.move_selected(1), moves)
        left_layout.addLayout(moves)
        center = QWidget()
        center_layout = QVBoxLayout(center)
        center_layout.addWidget(QLabel("Static screenshot preview · 9:16 · no gameplay or audio"))
        self.preview = PreviewWidget()
        center_layout.addWidget(self.preview, 1)
        self.editor = CommentEditor()
        editor_scroll = QScrollArea()
        editor_scroll.setWidgetResizable(True)
        editor_scroll.setWidget(self.editor)
        center_layout.addWidget(editor_scroll, 2)
        self.settings = SettingsPanel()
        settings_scroll = QScrollArea()
        settings_scroll.setWidgetResizable(True)
        settings_scroll.setWidget(self.settings)
        splitter.addWidget(left)
        splitter.addWidget(center)
        splitter.addWidget(settings_scroll)
        splitter.setSizes([270, 650, 250])
        layout.addWidget(splitter, 1)
        self.timeline_label = QLabel("Timeline pending — measured narration audio is required")
        layout.addWidget(self.timeline_label)
        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setMaximumWidth(150)
        self.statusBar().addPermanentWidget(self.progress)
        self.cancel_ocr_button = QPushButton("Cancel OCR")
        self.cancel_ocr_button.setEnabled(False)
        self.statusBar().addPermanentWidget(self.cancel_ocr_button)
        self.ocr_controller = OCRController(self)
        self.cancel_tts_button = QPushButton("Cancel Voice")
        self.cancel_tts_button.setEnabled(False)
        self.statusBar().addPermanentWidget(self.cancel_tts_button)
        self.tts_controller = TTSController(self)
        self.cancel_render_button = QPushButton("Cancel Export")
        self.cancel_render_button.setEnabled(False)
        self.statusBar().addPermanentWidget(self.cancel_render_button)
        self.render_controller = RenderController(self)
        self.cancel_render_button.clicked.connect(self.render_controller.cancel)
        self.settings.settings_changed.connect(self.edit_media_setting)
        self.audio_cleanup = AudioCleanup(self.tts_controller.service.settings.cache_dir, ROOT / "projects")
        self.menuBar().addMenu("Tools").addAction("Dọn audio thừa", self.clean_audio_cache)
        self.cancel_tts_button.clicked.connect(self.tts_controller.cancel)
        self.editor.ocr_requested.connect(self.ocr_controller.start)
        self.editor.rerun_requested.connect(lambda: self.ocr_controller.start(force=True))
        self.cancel_ocr_button.clicked.connect(self.ocr_controller.cancel)
        self.editor.selection_requested.connect(self.use_selection)
        self.scenes.selected.connect(self.select)
        self.editor.ocr_edited.connect(self.edit_ocr)
        self.editor.body_edited.connect(self.edit_body)
        self.editor.tts_edited.connect(self.edit_tts)
        self.editor.clean_requested.connect(self.clean_text)
        self.editor.cleaner_changed.connect(self.set_cleaner)
        self.refresh()

    @staticmethod
    def _button(text, callback, layout):
        button = QPushButton(text)
        if callback:
            button.clicked.connect(callback)
        else:
            button.setEnabled(False)
        layout.addWidget(button)
        return button

    def error(self, message):
        log.warning("User operation failed")
        self.statusBar().showMessage(str(message))
        QMessageBox.warning(self, "Unable to complete action", str(message))

    def refresh(self, select_id=None):
        self.scenes.populate(self.manager.project, select_id)
        self.settings.set_project(self.manager.project)
        self.preview.settings = self.manager.project.video_settings
        self.update_title()

    def update_title(self):
        timeline = self.manager.refresh_timeline()
        self.timeline_label.setText(f"Timeline: {len(timeline.segments)} items · {timeline.total_duration:.2f}s" if timeline else
                                    "Timeline pending — generate measured audio for every item")
        name = self.manager.path.stem if self.manager.path else self.manager.project.name
        self.setWindowTitle(f"{'* ' if self.manager.dirty else ''}{name} — Threads Video Studio")
        current = self.scenes.currentItem()
        if current and self.item:
            current.setToolTip(0, f"OCR: {self.item.ocr_status} | TTS: {self.item.tts_status}")

    def select(self, scene, item):
        self.scene, self.item = scene, item
        if self.editor.extraction_settings is not self.manager.project.extraction_settings:
            self.editor.show_advanced.setChecked(self.manager.project.extraction_settings.raw_ocr_visible_by_default)
        self.editor.extraction_settings = self.manager.project.extraction_settings
        self.tts_controller.sync_project()
        self.editor.set_item(item, self.manager.project.cleaner_settings)
        self.preview.set_image(item.original_image_path if item else "")
        self.add_reply_button.setEnabled(scene is not None and scene.scene_type == SceneType.THREAD)

    def edit_body(self, text):
        if self.item:
            self.manager.edit_body(self.item, text)
            self.editor.tts.blockSignals(True)
            self.editor.tts.setPlainText(self.item.tts_text)
            self.editor.tts.blockSignals(False)
            self.editor.update_status(self.item)
            self.update_title()

    def import_paths(self, paths, mode="single"):
        """UI import boundary; decode before making any project mutation."""
        if not paths:
            return
        try:
            validated = [validate_image(path) for path in paths]
            if mode == "thread":
                scene = self.manager.add_thread(validated)
                selected = scene.items[0].id
            elif mode == "reply":
                if self.scene is None or self.scene.scene_type != SceneType.THREAD:
                    raise ValueError("Select a Thread scene first.")
                for path in validated:
                    selected = self.manager.add_thread_item(self.scene, path).id
            else:
                for path in validated:
                    selected = self.manager.add_single(path).items[0].id
            self.refresh(selected)
            self.statusBar().showMessage(f"Imported {len(validated)} image(s)")
        except (OSError, ValueError) as exc:
            self.error(exc)

    def import_images(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Import Single screenshots", str(ROOT / "input/comments"), IMAGE_FILTER)
        self.import_paths(paths)

    def add_thread(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose question screenshot first", str(ROOT / "input/comments"), IMAGE_FILTER)
        self.import_paths([path] if path else [], "thread")

    def add_reply(self):
        path, _ = QFileDialog.getOpenFileName(self, "Choose next cumulative reply screenshot", str(ROOT / "input/comments"), IMAGE_FILTER)
        self.import_paths([path] if path else [], "reply")

    def delete_selected(self):
        if self.scene:
            self.manager.delete(self.scene, self.item)
            self.refresh()

    def move_selected(self, delta):
        if self.scene:
            identity = self.item.id if self.item else self.scene.id
            self.manager.move(self.scene, self.item, delta)
            self.refresh(identity)

    def edit_ocr(self, text):
        if self.item:
            self.manager.edit_ocr(self.item, text)
            self.editor.update_status(self.item)
            self.update_title()

    def edit_tts(self, text):
        if self.item:
            self.manager.edit_tts(self.item, text)
            self.editor.update_status(self.item)
            self.update_title()

    def set_cleaner(self, enabled):
        self.manager.project.cleaner_settings.remove_emoticons = enabled
        self.manager.changed()
        if self.item:
            self.manager.refresh_content(self.item)
            self.editor.set_item(self.item, self.manager.project.cleaner_settings)
        self.update_title()

    def clean_text(self, overwrite):
        if not self.item:
            return
        try:
            changed = self.manager.prepare_tts(self.item, overwrite)
            self.editor.set_item(self.item, self.manager.project.cleaner_settings)
            self.update_title()
            self.statusBar().showMessage("TTS text cleaned" if changed else "Manual TTS preserved. Enable replacement explicitly to clean again.")
        except ValueError as exc:
            self.error(exc)

    def preview_selected(self):
        self.preview.set_image(self.item.original_image_path if self.item else "")
        self.statusBar().showMessage("Static image only. Gameplay, audio and final composition are not implemented.")

    def use_selection(self, text, overwrite):
        if self.item:
            try:
                changed = self.manager.use_ocr_selection(self.item, text, overwrite)
                self.editor.set_item(self.item, self.manager.project.cleaner_settings)
                self.update_title()
                self.statusBar().showMessage("Selected text copied to TTS; review before narration." if changed else "Manual TTS kept. Enable replacement explicitly to use the selected text.")
            except ValueError as exc:
                self.error(exc)

    def save_project(self, checked=False, save_as=False):
        path = None if save_as else self.manager.path
        if path is None:
            filename, _ = QFileDialog.getSaveFileName(self, "Save project", str(ROOT / "projects/project.json"), "Project (*.json)")
            if not filename:
                return False
            path = Path(filename)
            if not path.suffix:
                path = path.with_suffix(".json")
        try:
            self.manager.save(path)
            self.update_title()
            self.statusBar().showMessage("Project saved")
            self.remember_project_audio()
            return True
        except (OSError, ValueError) as exc:
            self.error(exc)
            return False

    def confirm_unsaved(self):
        if not self.manager.dirty:
            return True
        choice = QMessageBox.question(self, "Unsaved changes", "Save changes before continuing?",
                                      QMessageBox.StandardButton.Save | QMessageBox.StandardButton.Discard | QMessageBox.StandardButton.Cancel,
                                      QMessageBox.StandardButton.Save)
        if choice == QMessageBox.StandardButton.Save:
            return self.save_project()
        return choice == QMessageBox.StandardButton.Discard

    def open_project(self):
        if not self.confirm_unsaved():
            return
        filename, _ = QFileDialog.getOpenFileName(self, "Open project", str(ROOT / "projects"), "Project (*.json)")
        if filename:
            try:
                missing = self.manager.load(Path(filename))
                self.refresh()
                self.statusBar().showMessage("Project loaded")
                self.remember_project_audio()
                if missing:
                    self.error("Project opened, but these media files are missing:\n" + "\n".join(missing))
            except (OSError, ValueError) as exc:
                self.error(exc)

    def edit_media_setting(self, group, key, value):
        settings = getattr(self.manager.project,group)
        old = getattr(settings,key)
        setattr(settings,key,value)
        try:self.manager.project.validate()
        except ValueError as exc:
            setattr(settings,key,old)
            self.settings.set_project(self.manager.project)
            self.error(exc)
            return
        self.manager.changed()
        self.preview.update()
        self.update_title()

    def remember_project_audio(self):
        try:
            self.audio_cleanup.remember(self.manager.path)
        except (CleanupError, OSError) as exc:
            self.error(exc)

    def clean_audio_cache(self):
        if self.tts_controller.busy or self.ocr_controller.busy or self.render_controller.busy:
            self.statusBar().showMessage("Đợi OCR/tạo giọng hoàn tất rồi dọn audio.")
            return
        AudioCleanupDialog(self, self.audio_cleanup, self.manager).exec()

    def closeEvent(self, event):
        if self.render_controller.busy:
            self.render_controller.close_when_finished = True
            self.render_controller.cancel()
            event.ignore()
            return
        if self.tts_controller.busy:
            self.tts_controller.close_when_finished = True
            self.tts_controller.cancel()
            event.ignore()
            return
        if self.ocr_controller.busy:
            self.ocr_controller.close_when_finished = True
            self.ocr_controller.cancel()
            event.ignore()
            return
        if self.confirm_unsaved():
            event.accept()
        else:
            event.ignore()
