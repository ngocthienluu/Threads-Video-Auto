"""Functional object fields; advanced animation/audio editing remains explicit."""
from PySide6.QtCore import Signal
from PySide6.QtWidgets import QWidget,QVBoxLayout,QTabWidget,QFormLayout,QDoubleSpinBox,QPushButton,QLabel
from app.core.editor_objects import ObjectType

class ObjectInspector(QWidget):
    edited=Signal(str,float)
    reset_requested=Signal()
    def __init__(self):
        super().__init__();layout=QVBoxLayout(self);tabs=QTabWidget();layout.addWidget(tabs)
        transform=QWidget();form=QFormLayout(transform);self.fields={}
        for key,label,minimum,maximum in (("x","X",-8192,8192),("y","Y",-8192,8192),("width","Width",1,8192),("height","Height",1,8192),("scale_x","Scale",.01,20),("rotation","Rotation",-360,360)):
            spin=QDoubleSpinBox();spin.setRange(minimum,maximum);spin.setDecimals(2);spin.setKeyboardTracking(False)
            spin.valueChanged.connect(lambda value,k=key:self.edited.emit(k,value));self.fields[key]=spin;form.addRow(label,spin)
        form.addRow(QLabel("Top-left position; rotation around center.\nImages resize proportionally."))
        reset=QPushButton("Reset Transform");reset.clicked.connect(self.reset_requested);form.addRow(reset);self.reset_button=reset
        tabs.addTab(transform,"Transform")
        style=QWidget();form=QFormLayout(style)
        for key,label,minimum,maximum in (("opacity","Opacity",0,1),("font_size","Font size",1,500)):
            spin=QDoubleSpinBox();spin.setRange(minimum,maximum);spin.setSingleStep(.05 if key=="opacity" else 1);spin.setDecimals(2 if key=="opacity" else 0);spin.setKeyboardTracking(False)
            spin.valueChanged.connect(lambda value,k=key:self.edited.emit(k,value));self.fields[key]=spin;form.addRow(label,spin)
        tabs.addTab(style,"Style")
        tabs.addTab(QLabel("Animation/keyframes: planned for V2."),"Animation")
        self.audio_label=QLabel("Narration: select a comment, then Comment / Voice.\nGameplay/music volume: Project tab.");self.audio_label.setWordWrap(True);tabs.addTab(self.audio_label,"Audio")
        self.bind(None)
    def bind(self,obj):
        editable=obj is not None and not obj.locked and obj.type!=ObjectType.BACKGROUND and not obj.deleted
        for key,spin in self.fields.items():
            spin.blockSignals(True);spin.setValue(getattr(obj,key) if obj else 0);spin.blockSignals(False)
            spin.setEnabled(editable and (key!="font_size" or obj.type==ObjectType.WATERMARK))
        self.reset_button.setEnabled(editable)
