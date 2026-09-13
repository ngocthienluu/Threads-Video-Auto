from PySide6.QtCore import Qt,Signal
from PySide6.QtWidgets import QWidget,QVBoxLayout,QHBoxLayout,QLabel,QSlider,QGraphicsView
from app.core.editor_timeline import TRACKS
from app.ui.timeline.timeline_scene import TimelineScene,RULER_HEIGHT,TRACK_HEIGHT

class TimelineWidget(QWidget):
    scrubbed=Signal(float)
    clip_selected=Signal(object)
    def __init__(self):
        super().__init__();layout=QVBoxLayout(self);layout.setContentsMargins(0,0,0,0)
        bar=QHBoxLayout();self.clock=QLabel("00:00.00");bar.addWidget(QLabel("AUTO"));bar.addWidget(self.clock)
        bar.addWidget(QLabel("Clip move / trim: V2"));bar.addStretch();bar.addWidget(QLabel("Zoom"))
        self.zoom=QSlider(Qt.Orientation.Horizontal);self.zoom.setRange(10,300);self.zoom.setValue(80);self.zoom.setMaximumWidth(160);bar.addWidget(self.zoom);layout.addLayout(bar)
        body=QHBoxLayout();labels=QVBoxLayout();labels.setSpacing(0);labels.setContentsMargins(0,0,0,0)
        ruler=QLabel("Tracks");ruler.setFixedHeight(RULER_HEIGHT);labels.addWidget(ruler)
        for track in TRACKS:
            label=QLabel(track);label.setFixedHeight(TRACK_HEIGHT);label.setMinimumWidth(85);labels.addWidget(label)
        labels.addStretch();body.addLayout(labels)
        self.scene=TimelineScene(self);self.view=QGraphicsView(self.scene);self.view.setAlignment(Qt.AlignmentFlag.AlignTop|Qt.AlignmentFlag.AlignLeft)
        self.view.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff);self.view.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOn)
        self.view.setMinimumHeight(RULER_HEIGHT+len(TRACKS)*TRACK_HEIGHT+22);body.addWidget(self.view,1);layout.addLayout(body)
        self.clips=[];self.duration=0.0;self.signature=None
        self.zoom.valueChanged.connect(self.set_zoom);self.scene.scrubbed.connect(self._scrub)
        self.scene.clip_selected.connect(self.clip_selected)
        self.set_data([],0)
    @property
    def pixels_per_second(self):return self.scene.scale.pixels_per_second
    def set_zoom(self,value):
        self.scene.scale.pixels_per_second=float(value);self.scene.rebuild(self.clips,self.duration)
        self.scene.set_time(self.scene.current_time)
    def set_data(self,clips,duration):
        signature=(tuple(clips),duration)
        if signature==self.signature:return
        self.signature=signature;self.clips=clips;self.duration=duration;self.scene.rebuild(clips,duration)
        self.set_time(min(self.scene.current_time,duration))
    def set_time(self,time):
        self.scene.set_time(time);time=self.scene.current_time
        self.clock.setText(f"{int(time)//60:02d}:{time%60:05.2f}")
    def _scrub(self,time):self.set_time(time);self.scrubbed.emit(time)
