from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QGroupBox, QLabel, QVBoxLayout, QWidget
from app.core.models import Project


class SettingsPanel(QWidget):
    ocr_engine_changed = Signal(str)

    def __init__(self):
        super().__init__()
        self.setMinimumWidth(210)
        layout = QVBoxLayout(self)
        ocr_box = QGroupBox("OCR Engine")
        ocr_layout = QVBoxLayout(ocr_box)
        self.ocr_engine = QComboBox()
        self.ocr_engine.addItem("PaddleOCR", "paddle")
        self.ocr_engine.addItem("Tesseract", "tesseract")
        self.ocr_engine.setToolTip("Choose an engine, then press READ IMAGE or AUTO GENERATE TEXT. Selection lasts for this app session.")
        self.ocr_engine.currentIndexChanged.connect(
            lambda: self.ocr_engine_changed.emit(self.ocr_engine.currentData()))
        ocr_layout.addWidget(self.ocr_engine)
        hint = QLabel("Chọn engine rồi bấm READ IMAGE để đọc lại ảnh.")
        hint.setWordWrap(True)
        ocr_layout.addWidget(hint)
        layout.addWidget(ocr_box)
        self.labels = {}
        for title in ("Background", "Music", "Watermark", "Video settings", "Presets"):
            box = QGroupBox(title)
            content = QVBoxLayout(box)
            self.labels[title] = QLabel()
            self.labels[title].setWordWrap(True)
            content.addWidget(self.labels[title])
            layout.addWidget(box)
        layout.addStretch()

    def set_ocr_engine(self, name):
        self.ocr_engine.blockSignals(True)
        self.ocr_engine.setCurrentIndex(self.ocr_engine.findData(name))
        self.ocr_engine.blockSignals(False)

    def set_project(self, project: Project):
        self.labels["Background"].setText("Continuous gameplay\nSelection / loop: coming in V1")
        self.labels["Music"].setText(f"Default volume: {project.music_settings.volume:.0%}\nMixing: not implemented")
        self.labels["Watermark"].setText(f"{project.watermark_settings.text}\nComposition: not implemented")
        v = project.video_settings
        self.labels["Video settings"].setText(f"{v.width} × {v.height} · {v.fps} fps\nMP4 / H.264 / AAC (target)\nSettings read-only this iteration")
        self.labels["Presets"].setText("Reserved for V2")
