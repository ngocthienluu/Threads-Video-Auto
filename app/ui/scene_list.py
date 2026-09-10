from pathlib import Path
from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import QTreeWidget, QTreeWidgetItem
from app.core.models import Project


class SceneList(QTreeWidget):
    selected = Signal(object, object)

    def __init__(self):
        super().__init__()
        self.setHeaderLabels(["Scenes / comments"])
        self.setMinimumWidth(235)
        self.currentItemChanged.connect(self._selected)

    def populate(self, project: Project, select_id: str | None = None):
        self.blockSignals(True)
        self.clear()
        chosen = None
        for index, scene in enumerate(project.scenes, 1):
            row = QTreeWidgetItem([f"Scene {index:02d} · {scene.scene_type.value.title()} ({len(scene.items)})"])
            row.setData(0, Qt.ItemDataRole.UserRole, (scene, None))
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
        self.blockSignals(False)
        if chosen:
            self.setCurrentItem(chosen)
        else:
            self.selected.emit(None, None)

    def _selected(self, current, previous):
        self.selected.emit(*(current.data(0, Qt.ItemDataRole.UserRole) if current else (None, None)))
