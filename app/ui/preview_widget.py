"""Graphics canvas. Project objects, never widget pixels, own all geometry."""
from dataclasses import asdict
from PySide6.QtCore import QRectF, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPixmap, QImage, QPen
from PySide6.QtWidgets import QGraphicsView, QGraphicsScene, QGraphicsObject, QGraphicsItem
from app.core.config import VideoSettings
from app.core.editor_objects import ObjectType
from app.core.editor_scene import object_image

class CanvasObject(QGraphicsObject):
    def __init__(self, canvas, model, pixmap):
        super().__init__()
        self.canvas,self.model,self.pixmap = canvas,model,pixmap
        self.loading = False
        self.before = None
        self.setFlags(QGraphicsItem.GraphicsItemFlag.ItemIsSelectable | QGraphicsItem.GraphicsItemFlag.ItemSendsGeometryChanges)
        self.refresh()

    def boundingRect(self):
        return QRectF(0,0,self.model.width*self.model.scale_x,self.model.height*self.model.scale_y)

    def refresh(self):
        self.loading = True
        self.prepareGeometryChange()
        self.setPos(self.model.x,self.model.y)
        self.setTransformOriginPoint(self.boundingRect().center())
        self.setRotation(self.model.rotation)
        self.setOpacity(self.model.opacity)
        self.setZValue(self.model.z_index)
        self.setFlag(QGraphicsItem.GraphicsItemFlag.ItemIsMovable,not self.model.locked)
        self.loading = False
        self.update()

    def paint(self,painter,option,widget=None):
        rect = self.boundingRect()
        if self.model.type == ObjectType.BACKGROUND:
            painter.fillRect(rect,QColor("#202832"))
            painter.setPen(QColor("#8493a7"))
            painter.drawText(rect,Qt.AlignmentFlag.AlignCenter,"Gameplay shown on export")
        elif self.pixmap.isNull():
            painter.fillRect(rect,QColor("#512f3c"))
            painter.drawText(rect,Qt.AlignmentFlag.AlignCenter,"Media unavailable")
        else: painter.drawPixmap(rect,self.pixmap,QRectF(self.pixmap.rect()))
        if self.isSelected():
            pen=QPen(QColor("#579cff"),2);pen.setCosmetic(True)
            painter.setPen(pen);painter.setBrush(Qt.BrushStyle.NoBrush);painter.drawRect(rect)

    def itemChange(self,change,value):
        if change == QGraphicsItem.GraphicsItemChange.ItemPositionHasChanged and not self.loading:
            self.model.x,self.model.y = value.x(),value.y()
            self.canvas.object_changed.emit(self.model.id)
        return super().itemChange(change,value)

    def mousePressEvent(self,event):
        self.before = asdict(self.model)
        super().mousePressEvent(event)

    def mouseReleaseEvent(self,event):
        super().mouseReleaseEvent(event)
        if self.before and self.before != asdict(self.model):
            self.canvas.gesture_finished.emit(self.model.id,self.before,asdict(self.model))
        self.before = None

class PreviewWidget(QGraphicsView):
    selected = Signal(str)
    object_changed = Signal(str)
    gesture_finished = Signal(str,object,object)
    def __init__(self):
        super().__init__()
        self.setScene(QGraphicsScene(self))
        self.setSceneRect(0,0,1080,1920)
        self.setMinimumSize(180,230)
        self.setRenderHints(QPainter.RenderHint.Antialiasing | QPainter.RenderHint.SmoothPixmapTransform)
        self.setBackgroundBrush(QColor("#10151d"))
        self.settings = VideoSettings()
        self.pixmap = QPixmap()
        self.project = None
        self.objects = {}
        self.cache = {}
        self.scene().selectionChanged.connect(self._selected)

    def _selected(self):
        selected = self.scene().selectedItems()
        self.selected.emit(selected[0].model.id if selected else "")

    def set_image(self,path=""):
        # Compatibility for existing authoring selection; object assets are cached.
        key = ("image",path)
        if key not in self.cache: self.cache[key] = QPixmap(path) if path else QPixmap()
        self.pixmap = self.cache[key]

    def set_project(self,project):
        self.project = project
        wanted = {o.id:o for o in project.editor_objects}
        for key in list(self.objects):
            if key not in wanted:
                self.scene().removeItem(self.objects.pop(key))
        for obj in wanted.values():
            key = (obj.id,obj.font_size,project.watermark_settings.text,project.watermark_settings.font) if obj.type == ObjectType.WATERMARK else (obj.id,)
            if key not in self.cache:
                try:
                    im = object_image(project,obj)
                    qim = QImage(im.tobytes(),im.width,im.height,QImage.Format.Format_RGBA8888).copy()
                    self.cache[key] = QPixmap.fromImage(qim)
                except (OSError,ValueError,StopIteration): self.cache[key] = QPixmap()
            if obj.id not in self.objects:
                item=CanvasObject(self,obj,self.cache[key]);self.objects[obj.id]=item;self.scene().addItem(item)
            item=self.objects[obj.id];item.model=obj;item.pixmap=self.cache[key];item.refresh()

    def select_object(self,identity):
        self.scene().blockSignals(True)
        self.scene().clearSelection()
        if identity in self.objects: self.objects[identity].setSelected(True)
        self.scene().blockSignals(False)

    def show_state(self,time=0,authoring_item=None,ready=False):
        if not self.project:return
        for item in self.objects.values():
            obj=item.model
            active = obj.active_at(time) if ready else obj.visible and (not obj.source_item_id or obj.source_item_id == authoring_item)
            if obj.type == ObjectType.WATERMARK: active = active and self.project.watermark_settings.enabled
            item.setVisible(active)

    def fit(self):
        self.fitInView(self.sceneRect(),Qt.AspectRatioMode.KeepAspectRatio)

    def resizeEvent(self,event):
        super().resizeEvent(event);self.fit()
