from pathlib import Path
from PySide6.QtCore import Qt, Signal, QSize
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem
from app.core.models import Project


class SceneList(QTreeWidget):
    selected = Signal(object, object)

    def __init__(self):
        super().__init__()
        self.setHeaderLabels(["Scenes / comments"])
        self.setMinimumWidth(190)
        self.setIconSize(QSize(64,48))
        self.filter_value = "All"
        self.thumbnails = {}
        self.currentItemChanged.connect(self._selected)

    def populate(self, project: Project, select_id: str | None = None):
        self.blockSignals(True)
        self.clear()
        chosen = None
        for index, scene in enumerate(project.scenes, 1):
            row = QTreeWidgetItem([f"Scene {index:02d} · {scene.scene_type.value.title()} ({len(scene.items)})"])
            row.setData(0, Qt.ItemDataRole.UserRole, (scene, None))
            if scene.items:
                path = scene.items[0].original_image_path
                if path not in self.thumbnails:
                    pixmap = QPixmap(path)
                    self.thumbnails[path] = QIcon(pixmap.scaled(64,48,Qt.AspectRatioMode.KeepAspectRatio,Qt.TransformationMode.SmoothTransformation))
                row.setIcon(0,self.thumbnails[path])
            ready = all(i.tts_status == "done" for i in scene.items)
            duration = sum(i.audio_duration for i in scene.items)
            row.setText(0,row.text(0) + f"\n{duration:.1f}s - " + ("Ready" if ready else "Needs audio"))
            row.setSizeHint(0,QSize(180,72))
            self.addTopLevelItem(row)
            if scene.id == select_id:
                chosen = row
            for item in scene.items:
                child = QTreeWidgetItem([f"{item.role.value.title()} · {Path(item.original_image_path).name}"])
                child.setData(0, Qt.ItemDataRole.UserRole, (scene, item))
                child.setToolTip(0, f"OCR: {item.ocr_status} | TTS: {item.tts_status}")
                row.addChild(child)
                if item.id == select_id:
                    chosen = child
            row.setExpanded(True)
        self.update_status(project)
        self.filter_scenes(self.filter_value)
        self.blockSignals(False)
        if chosen:
            self.setCurrentItem(chosen)
        else:
            self.selected.emit(None, None)

    def _selected(self, current, previous):
        self.selected.emit(*(current.data(0, Qt.ItemDataRole.UserRole) if current else (None, None)))

    def filter_scenes(self, value):
        self.filter_value = value
        for index in range(self.topLevelItemCount()):
            row = self.topLevelItem(index)
            scene,_ = row.data(0,Qt.ItemDataRole.UserRole)
            row.setHidden(value != "All" and scene.scene_type.value != value.lower())

    def update_status(self,project):
        timing=project.timing_settings
        for index in range(self.topLevelItemCount()):
            row=self.topLevelItem(index);scene,_=row.data(0,Qt.ItemDataRole.UserRole)
            ready=all(i.tts_status=="done" and i.audio_duration>0 and Path(i.audio_path).is_file() for i in scene.items)
            duration=sum(i.audio_duration+timing.voice_pre_padding+timing.voice_post_padding for i in scene.items)
            status=f"{duration:.1f}s - Ready" if ready else "Timing pending - Needs audio"
            row.setText(0,f"Scene {index+1:02d} - {scene.scene_type.value.title()} ({len(scene.items)})\n{status}")
