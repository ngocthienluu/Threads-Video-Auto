from math import floor, ceil
from PySide6.QtCore import Qt, QRectF, Signal, QPointF
from PySide6.QtGui import QColor,QPen,QBrush
from PySide6.QtWidgets import QGraphicsScene,QGraphicsRectItem
from app.core.editor_timeline import TRACKS, TimelineScale

RULER_HEIGHT=28
TRACK_HEIGHT=29
COLORS=("#38526d","#456bc4","#2d8066","#785097","#66516b","#806239")

class ClipItem(QGraphicsRectItem):
    def __init__(self,clip,scale):
        self.clip=clip
        self.track_index=TRACKS.index(clip.track)
        super().__init__(QRectF(scale.time_to_x(clip.start_time),RULER_HEIGHT+self.track_index*TRACK_HEIGHT+3,
                               max(.5,scale.time_to_x(clip.duration)),TRACK_HEIGHT-6))
        self.setBrush(QBrush(QColor(COLORS[self.track_index])));self.setPen(QPen(QColor("#7293b8")))
        self.setToolTip(f"{clip.label}: {clip.start_time:.2f} - {clip.end_time:.2f}s (AUTO, timing follows voice)")
    def paint(self,painter,option,widget=None):
        super().paint(painter,option,widget)
        painter.save();painter.setClipRect(self.rect());painter.setPen(QColor("#f0f3fa"))
        painter.drawText(self.rect().adjusted(5,0,-3,0),Qt.AlignmentFlag.AlignVCenter,f"{self.clip.label}  {self.clip.duration:.2f}s")
        painter.restore()

class TimelineScene(QGraphicsScene):
    scrubbed=Signal(float)
    clip_selected=Signal(object)
    def __init__(self,parent=None):
        super().__init__(parent);self.scale=TimelineScale();self.duration=0.0;self.current_time=0.0;self.dragging=False;self.blocks=[]
        self.setBackgroundBrush(QColor("#141d29"))
    def rebuild(self,clips,duration):
        self.clear();self.blocks=[];self.duration=duration
        for clip in clips:
            block=ClipItem(clip,self.scale);self.addItem(block);self.blocks.append(block)
        self.setSceneRect(0,0,max(800,self.scale.time_to_x(duration)+60),RULER_HEIGHT+len(TRACKS)*TRACK_HEIGHT)
        self.update()
    def set_time(self,time,emit=False):
        self.current_time=max(0,min(self.duration,time));self.update()
        if emit:self.scrubbed.emit(self.current_time)
    def drawBackground(self,painter,rect):
        super().drawBackground(painter,rect)
        pen=QPen(QColor("#2e3c50"));pen.setCosmetic(True);painter.setPen(pen)
        step=1 if self.scale.pixels_per_second>=50 else 5
        first=max(0,floor(self.scale.x_to_time(rect.left())/step)*step)
        last=ceil(self.scale.x_to_time(rect.right()))
        for second in range(first,last+step,step):
            x=self.scale.time_to_x(second);painter.drawLine(QPointF(x,0),QPointF(x,self.sceneRect().height()))
            painter.setPen(QColor("#a7b7ce"));painter.drawText(QPointF(x+4,18),f"{second//60:02d}:{second%60:02d}");painter.setPen(pen)
        for n in range(len(TRACKS)+1):
            y=RULER_HEIGHT+n*TRACK_HEIGHT;painter.drawLine(QPointF(rect.left(),y),QPointF(rect.right(),y))
    def drawForeground(self,painter,rect):
        pen=QPen(QColor("#ff657d"),2);pen.setCosmetic(True);painter.setPen(pen)
        x=self.scale.time_to_x(self.current_time);painter.drawLine(QPointF(x,0),QPointF(x,self.sceneRect().height()))
    def mousePressEvent(self,event):
        if event.button()!=Qt.MouseButton.LeftButton:return super().mousePressEvent(event)
        self.dragging=True
        for item in self.items(event.scenePos()):
            if isinstance(item,ClipItem):self.clip_selected.emit(item.clip);break
        self.set_time(self.scale.x_to_time(event.scenePos().x()),True);event.accept()
    def mouseMoveEvent(self,event):
        if self.dragging:self.set_time(self.scale.x_to_time(event.scenePos().x()),True);event.accept()
        else:super().mouseMoveEvent(event)
    def mouseReleaseEvent(self,event):
        self.dragging=False;event.accept()
