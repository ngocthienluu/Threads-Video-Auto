"""Voice selection widgets only; requests and availability belong to services."""
from PySide6.QtCore import Signal, Qt
from PySide6.QtWidgets import QWidget, QFormLayout, QHBoxLayout, QLabel, QComboBox, QLineEdit, QPushButton, QCheckBox
from app.services.tts.voices import VoiceInfo


class VoicePanel(QWidget):
    changed = Signal()
    refresh_requested = Signal()
    test_requested = Signal()
    default_requested = Signal()
    model_changed = Signal(str)
    regenerate_requested = Signal()

    def __init__(self):
        super().__init__()
        self.voices = []
        self.default_id = ""
        self.selection = ""
        layout = QFormLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.account = QLabel("Not configured")
        self.default_label = QLabel("Not selected")
        self.default_label.setTextFormat(Qt.TextFormat.PlainText)
        self.search = QLineEdit()
        self.search.setPlaceholderText("Search Voice… name / language / accent")
        self.combo = QComboBox()
        self.combo.setMinimumContentsLength(18)
        self.combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        self.status = QLabel("API access not confirmed")
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        self.notice = QLabel()
        self.notice.setWordWrap(True)
        self.refresh = QPushButton("Refresh Voices")
        self.test = QPushButton("Test Voice")
        self.test.setToolTip('Sends "Xin chào" to ElevenLabs. Each click may use credits; no automatic testing.')
        self.set_default = QPushButton("Set selected as project default")
        buttons = QWidget()
        row = QHBoxLayout(buttons)
        row.setContentsMargins(0, 0, 0, 0)
        row.addWidget(self.refresh)
        row.addWidget(self.test)
        self.show_advanced = QCheckBox("Advanced voice settings")
        self.advanced = QWidget()
        advanced = QFormLayout(self.advanced)
        self.manual = QLineEdit()
        self.effective_id = QLabel()
        self.effective_id.setTextFormat(Qt.TextFormat.PlainText)
        self.manual.setPlaceholderText("Manual Voice ID; empty = Use Default")
        self.model = QLineEdit()
        self.model.setPlaceholderText("Model from .env")
        advanced.addRow("Voice ID", self.manual)
        advanced.addRow("Effective Voice ID", self.effective_id)
        advanced.addRow("Model", self.model)
        self.regenerate = QPushButton("Regenerate Voice (new API request)")
        self.regenerate.setToolTip("Bypasses audio cache and may use credits. Existing recording is kept if this request fails.")
        advanced.addRow("", self.regenerate)
        self.regenerate.clicked.connect(self.regenerate_requested)
        self.advanced.hide()
        for title, widget in [("Voice Provider", QLabel("ElevenLabs")), ("API Key", self.account),
                              ("Project Default", self.default_label), ("", self.search), ("Voice", self.combo),
                              ("Voice status", self.status), ("", buttons), ("", self.notice),
                              ("", self.set_default), ("", self.show_advanced), ("", self.advanced)]:
            layout.addRow(title, widget)
        self.search.textChanged.connect(self.populate)
        self.combo.currentIndexChanged.connect(self.choose)
        self.manual.editingFinished.connect(self.enter_manual)
        self.model.editingFinished.connect(lambda: self.model_changed.emit(self.model.text().strip()))
        self.refresh.clicked.connect(self.refresh_requested)
        self.test.clicked.connect(self.test_requested)
        self.set_default.clicked.connect(self.default_requested)
        self.show_advanced.toggled.connect(self.advanced.setVisible)
        self.populate()

    def selected_voice(self):
        return self.selection or self.default_id

    def set_voices(self, voices):
        self.voices = list(voices)
        self.populate()

    def select(self, identity):
        self.selection = identity
        self.manual.setText(identity)
        self.populate()

    def populate(self, *_):
        query = self.search.text().casefold().strip()
        self.combo.blockSignals(True)
        self.combo.clear()
        self.combo.addItem("Use Default", "")
        for voice in self.voices:
            haystack = " ".join([voice.name, voice.language or "", voice.accent or ""]).casefold()
            if not query or query in haystack or voice.voice_id == self.selection:
                self.combo.addItem(voice.name or "Unnamed voice", voice.voice_id)
        index = self.combo.findData(self.selection)
        if index < 0:
            self.combo.addItem("Manual voice (see Advanced)", self.selection)
            index = self.combo.count() - 1
        self.combo.setCurrentIndex(index)
        self.combo.blockSignals(False)
        self.update_status()

    def choose(self, *_):
        self.selection = self.combo.currentData() or ""
        self.manual.setText(self.selection)
        self.update_status()
        self.changed.emit()

    def enter_manual(self):
        self.select(self.manual.text().strip())
        self.changed.emit()

    def update_status(self):
        identity = self.selected_voice()
        voice = next((v for v in self.voices if v.voice_id == identity), VoiceInfo(identity))
        labels = {"unknown": "? API access not confirmed", "available": "✓ Available via API (this session)",
                  "payment_required": "🔒 Payment/API access required", "restricted": "🔒 Permission denied",
                  "unauthorized": "✕ API key invalid or unauthorized", "error": "⚠ Voice check failed"}
        label = labels.get(voice.availability_status, labels["unknown"])
        self.status.setText(label + ("\n" + voice.availability_reason if voice.availability_reason not in label else ""))
        self.effective_id.setText(identity or "Not selected")
        self.test.setEnabled(bool(identity))
        self.set_default.setEnabled(bool(identity))
