from pathlib import Path
from app.core.config import ROOT
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QComboBox, QGroupBox, QLabel, QVBoxLayout, QWidget, QFormLayout, QLineEdit, QPushButton, QFileDialog, QCheckBox, QDoubleSpinBox, QSpinBox, QToolBox
from app.core.models import Project


class SettingsPanel(QWidget):
    ocr_engine_changed = Signal(str)
    settings_changed = Signal(str, str, object)

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
        self.sections = QToolBox()
        layout.addWidget(self.sections)
        self.sections.addItem(ocr_box,"OCR")
        self.controls = {}
        self.labels = {}
        def section(title):
            box = QGroupBox(title)
            form = QFormLayout(box)
            self.sections.addItem(box,title)
            return form
        def field(form, group, key, title, kind, minimum=0, maximum=1):
            if kind == "file":
                control = QLineEdit()
                control.setPlaceholderText("Choose a local file")
                button = QPushButton("Browse...")
                button.clicked.connect(lambda: self.pick(group, key))
                form.addRow(title, control); form.addRow("", button)
                control.editingFinished.connect(lambda: self.settings_changed.emit(group,key,control.text().strip()))
            elif kind == "bool":
                control = QCheckBox(title)
                form.addRow("",control)
                control.toggled.connect(lambda value: self.settings_changed.emit(group,key,value))
            elif kind == "text":
                control = QLineEdit()
                form.addRow(title,control)
                control.editingFinished.connect(lambda: self.settings_changed.emit(group,key,control.text()))
            else:
                control = QSpinBox() if kind == "int" else QDoubleSpinBox()
                control.setRange(minimum,maximum)
                if kind != "int":control.setSingleStep(.05)
                form.addRow(title,control)
                control.valueChanged.connect(lambda value: self.settings_changed.emit(group,key,value))
            self.controls[group,key] = control
        bg = section("Gameplay")
        field(bg,"background_settings","file","Video","file")
        field(bg,"background_settings","loop","Loop gameplay","bool")
        field(bg,"background_settings","random_start","Random starting point","bool")
        field(bg,"background_settings","volume","Volume (0 = muted)","float")
        music = section("Music (optional)")
        field(music,"music_settings","enabled","Enable music","bool")
        field(music,"music_settings","file","Audio","file")
        field(music,"music_settings","volume","Volume","float")
        field(music,"music_settings","loop","Loop music","bool")
        field(music,"music_settings","random_start","Random starting point","bool")
        field(music,"music_settings","fade_in","Fade in (seconds)","float",0,10)
        field(music,"music_settings","fade_out","Fade out (seconds)","float",0,10)
        mark = section("Watermark")
        field(mark,"watermark_settings","enabled","Enable watermark","bool")
        field(mark,"watermark_settings","text","Text","text")
        field(mark,"watermark_settings","size","Size","int",8,200)
        field(mark,"watermark_settings","opacity","Opacity","float")
        field(mark,"watermark_settings","y","Top margin (px)","int",0,1920)
        field(mark,"watermark_settings","font","Font (optional)","file")
        video = section("Video / screenshot")
        self.video_info = QLabel()
        video.addRow(self.video_info)
        field(video,"video_settings","comment_max_width_ratio","Image width ratio","float",.1,1)
        field(video,"video_settings","comment_y_ratio","Image center Y","float",0,1)
        timing = section("Narration timing")
        field(timing,"timing_settings","voice_pre_padding","Before voice (s)","float",0,5)
        field(timing,"timing_settings","voice_post_padding","After voice (s)","float",0,5)
        field(timing,"timing_settings","scene_gap","Scene gap (s)","float",0,5)
        layout.addStretch()

    def set_ocr_engine(self, name):
        self.ocr_engine.blockSignals(True)
        self.ocr_engine.setCurrentIndex(self.ocr_engine.findData(name))
        self.ocr_engine.blockSignals(False)

    def pick(self, group, key):
        filter_text = "Video (*.mp4 *.mov *.mkv *.webm *.avi)" if group == "background_settings" else "Fonts (*.ttf *.otf)" if key == "font" else "Audio (*.mp3 *.wav *.m4a *.ogg *.flac)"
        folder = "backgrounds" if group == "background_settings" else "fonts" if key == "font" else "music"
        initial = ROOT / "assets" / folder
        current = self.controls[group, key].text().strip()
        if current:
            candidate = Path(current).expanduser()
            if candidate.is_absolute() and candidate.parent.is_dir():
                initial = candidate.parent
        path, _ = QFileDialog.getOpenFileName(self, "Choose media", str(initial), filter_text)
        if path:
            self.controls[group,key].setText(path)
            self.settings_changed.emit(group,key,path)

    def set_project(self, project: Project):
        v = project.video_settings
        self.video_info.setText(f"{v.width} x {v.height} / {v.fps} fps / MP4 H.264 + AAC")
        for (group,key), control in self.controls.items():
            control.blockSignals(True)
            value = getattr(getattr(project,group),key)
            if isinstance(control,QCheckBox):control.setChecked(value)
            elif isinstance(control,QLineEdit):control.setText(value)
            else:control.setValue(value)
            control.blockSignals(False)
