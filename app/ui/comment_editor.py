from PySide6.QtCore import Signal
from PySide6.QtWidgets import (QCheckBox, QComboBox, QFormLayout, QLabel,
                               QPlainTextEdit, QPushButton, QWidget, QDialog, QDialogButtonBox, QVBoxLayout, QDoubleSpinBox)
from app.core.config import ExtractionSettings
from app.core.spelling import suggest_spelling


class CommentEditor(QWidget):
    ocr_edited = Signal(str)
    body_edited = Signal(str)
    tts_edited = Signal(str)
    clean_requested = Signal(bool)
    cleaner_changed = Signal(bool)
    ocr_requested = Signal()
    rerun_requested = Signal()
    selection_requested = Signal(str, bool)
    voice_changed = Signal(str, float)
    voice_requested = Signal()
    voices_requested = Signal()
    audio_requested = Signal()

    def __init__(self):
        super().__init__()
        self.extraction_settings = ExtractionSettings()
        layout = QFormLayout(self)
        self.role = QLabel("Select a comment")
        self.read_image = QPushButton("READ IMAGE → Detect comment → TTS text")
        self.body = QPlainTextEdit()
        self.body.setPlaceholderText("Comment content will be detected automatically")
        self.body.setMaximumHeight(110)
        self.detection_status = QLabel("Detection pending")
        self.detection_status.setWordWrap(True)
        self.spelling = QPushButton("Sửa chính tả / Review spelling")
        self.spelling.clicked.connect(self.review_spelling)
        self.tts = QPlainTextEdit()
        self.tts.setMaximumHeight(100)
        self.tts.setPlaceholderText("Automatic narration text; replies include only new content")
        self.remove_emoticons = QCheckBox("Auto remove emoticons")
        self.remove_emoticons.setChecked(True)
        from app.ui.voice_panel import VoicePanel
        self.voice_panel = VoicePanel()
        self.voice = self.voice_panel.combo
        self.default_voice = ""
        self.load_voices = self.voice_panel.refresh
        self.speed = QDoubleSpinBox()
        from app.services.tts.settings import TTSSettings
        self.speed.setRange(TTSSettings.min_speed, TTSSettings.max_speed)
        self.speed.setSingleStep(.05)
        self.speed.setValue(1.0)
        self.regenerate = QPushButton("Generate Voice (ElevenLabs)")
        self.regenerate.setToolTip("Sends TTS Text to ElevenLabs; may use account credits. Identical cached audio is reused.")
        self.regenerate.setEnabled(False)
        self.open_audio = QPushButton("Open generated audio")
        self.open_audio.setEnabled(False)
        self.status = QLabel()
        self.status.setWordWrap(True)
        self.show_advanced = QCheckBox("Advanced / Show raw OCR")
        self.advanced = QWidget()
        advanced = QFormLayout(self.advanced)
        self.ocr = QPlainTextEdit()
        self.ocr.setReadOnly(True)
        self.ocr.setMaximumHeight(120)
        self.use_selection = QPushButton("Manual Selection → TTS")
        self.overwrite = QCheckBox("Allow Clean / Selection to replace my manual TTS text")
        self.clean = QPushButton("Clean detected content → TTS")
        self.rerun = QPushButton("Re-run extraction (replace detected comment; keep manual TTS)")
        self.details = QLabel()
        self.details.setWordWrap(True)
        for label, widget in [("Raw OCR", self.ocr), ("", self.overwrite), ("", self.use_selection),
                              ("", self.clean), ("", self.rerun), ("Details", self.details)]:
            advanced.addRow(label, widget)
        self.advanced.hide()
        for label, widget in [("Item", self.role), ("", self.read_image), ("Detected Comment", self.body),
                              ("Detection", self.detection_status), ("", self.spelling), ("TTS Text", self.tts),
                              ("", self.remove_emoticons), ("", self.voice_panel),
                              ("Speed", self.speed), ("", self.regenerate), ("", self.open_audio),
                              ("Status", self.status), ("", self.show_advanced), ("", self.advanced)]:
            layout.addRow(label, widget)
        self.body.textChanged.connect(lambda: self.body_edited.emit(self.body.toPlainText()))
        self.tts.textChanged.connect(lambda: self.tts_edited.emit(self.tts.toPlainText()))
        self.clean.clicked.connect(lambda: self.clean_requested.emit(self.overwrite.isChecked()))
        self.remove_emoticons.toggled.connect(self.cleaner_changed)
        self.read_image.clicked.connect(self.ocr_requested)
        self.rerun.clicked.connect(self.rerun_requested)
        self.use_selection.clicked.connect(lambda: self.selection_requested.emit(
            self.ocr.textCursor().selectedText().replace("\u2029", "\n"), self.overwrite.isChecked()))
        self.show_advanced.toggled.connect(self.advanced.setVisible)
        self.voice_panel.changed.connect(lambda: self.voice_changed.emit(self.selected_voice(), self.speed.value()))
        self.speed.valueChanged.connect(lambda: self.voice_changed.emit(self.selected_voice(), self.speed.value()))
        self.regenerate.clicked.connect(self.voice_requested)
        self.load_voices.clicked.connect(self.voices_requested)
        self.open_audio.clicked.connect(self.audio_requested)
        self.setEnabled(False)

    def selected_voice(self):
        return self.voice_panel.selected_voice()

    def set_voices(self, voices):
        self.voice_panel.set_voices(voices)

    def _select_voice(self, identity):
        self.voice_panel.select(identity)

    def review_spelling(self):
        original = self.body.toPlainText()
        suggested, changes = suggest_spelling(original)
        dialog = QDialog(self)
        dialog.setWindowTitle("Sửa chính tả — kiểm tra trước khi áp dụng")
        dialog.resize(700, 480)
        layout = QVBoxLayout(dialog)
        note = QLabel("Gợi ý cục bộ cho một số cụm từ; chưa sửa được mọi lỗi.\n"
                      "Bạn có thể sửa thêm bên dưới. Raw OCR và TTS đã sửa tay được giữ nguyên.\n" +
                      ("\n".join(changes) if changes else "Chưa có gợi ý chắc chắn cho đoạn này."))
        note.setWordWrap(True)
        layout.addWidget(note)
        preview = QPlainTextEdit(suggested)
        layout.addWidget(preview)
        buttons = QDialogButtonBox(QDialogButtonBox.Save | QDialogButtonBox.Cancel)
        buttons.accepted.connect(dialog.accept)
        buttons.rejected.connect(dialog.reject)
        layout.addWidget(buttons)
        if dialog.exec() == QDialog.Accepted and preview.toPlainText() != original:
            self.body.setPlainText(preview.toPlainText())

    def set_item(self, item, cleaner_settings):
        self.setEnabled(item is not None)
        self.overwrite.setChecked(False)
        for widget in (self.ocr, self.body, self.tts, self.remove_emoticons, self.voice, self.speed):
            widget.blockSignals(True)
        self.role.setText(item.role.value.title() + (" · cumulative body" if item.role.value == "reply" else "") if item else "Select a comment")
        self.ocr.setPlainText((item.raw_ocr_text or item.ocr_text) if item else "")
        self.body.setPlainText(item.body_text if item else "")
        self.tts.setPlainText(item.tts_text if item else "")
        self.remove_emoticons.setChecked(cleaner_settings.remove_emoticons)
        self._select_voice(item.voice_id if item else "")
        self.speed.setValue(item.voice_speed if item else 1.0)
        self.update_status(item)
        for widget in (self.ocr, self.body, self.tts, self.remove_emoticons, self.voice, self.speed):
            widget.blockSignals(False)

    def update_status(self, item):
        self.regenerate.setEnabled(bool(item and item.tts_text.strip() and self.selected_voice()))
        self.open_audio.setEnabled(bool(item and item.audio_path))
        if not item:
            self.status.setText("No item selected")
            self.detection_status.setText("Detection pending")
            self.details.clear()
            return
        confidence = min(item.extraction_confidence, item.thread_diff_confidence) if item.role.value == "reply" else item.extraction_confidence
        if item.body_text_is_manual:
            label = "Manual comment · protected" if not item.needs_review else "Manual comment · review reply overlap"
        elif item.extraction_method == "pending":
            label = "Detection pending"
        elif item.needs_review:
            label = f"Review detected text · {confidence:.0%} confidence"
        elif confidence < self.extraction_settings.threads_auto_accept_confidence:
            label = f"Comment detected · {confidence:.0%} · check warning in Advanced"
        else:
            label = f"Comment detected · {confidence:.0%} confidence"
        self.detection_status.setText(label)
        self.details.setText(f"Method: {item.extraction_method}\nHeuristic score, not a guarantee of OCR spelling.\n" +
                             "\n".join(item.extraction_warnings) +
                             (f"\nNew reply: {item.new_body_text}" if item.role.value == "reply" else ""))
        manual = "manual (protected)" if item.tts_text_is_manual else "automatic"
        self.status.setText(f"OCR {item.ocr_status} · TTS text: {manual}\nVoice {item.tts_status} · Timeline {item.timeline_status}" +
                            (f" · Audio {item.audio_duration:.2f}s" if item.tts_status == "done" else ""))
