import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
import tempfile
import unittest
from pathlib import Path
from PIL import Image
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPointF
from app.core.models import Project, Scene, SceneItem
from app.core.editor_scene import ensure_objects
from app.core.editor_objects import ObjectType
from app.ui.preview_widget import PreviewWidget

class EditorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.app=QApplication.instance() or QApplication([])
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.path=Path(self.temp.name)/"comment.png"
        Image.new("RGB",(300,100),"red").save(self.path)
        self.project=Project(scenes=[Scene(items=[SceneItem(original_image_path=str(self.path))])])
        ensure_objects(self.project)
        self.obj=next(o for o in self.project.editor_objects if o.type==ObjectType.COMMENT_IMAGE)
        self.canvas=PreviewWidget();self.canvas.resize(500,700);self.canvas.set_project(self.project);self.canvas.show();self.app.processEvents()
    def tearDown(self): self.canvas.close();self.temp.cleanup()
    def test_logical_coordinates_and_move(self):
        self.assertEqual(self.canvas.sceneRect().width(),1080)
        changed=[];self.canvas.object_changed.connect(changed.append)
        item=self.canvas.objects[self.obj.id];item.setPos(120,410)
        self.assertEqual((self.obj.x,self.obj.y),(120,410));self.assertEqual(changed,[self.obj.id])
        point=QPointF(300,500);mapped=self.canvas.mapToScene(self.canvas.mapFromScene(point))
        self.assertLess(abs(mapped.x()-point.x()),5)
        self.canvas.resize(800,900);self.app.processEvents()
        self.assertEqual((self.obj.x,self.obj.y),(120,410))
    def test_serialization_and_legacy_defaults(self):
        self.obj.x=123;self.obj.rotation=12;self.obj.opacity=.4
        result=Project.from_dict(self.project.to_dict())
        self.assertEqual(result.editor_objects,self.project.editor_objects)
        legacy=self.project.to_dict();legacy.pop("editor_objects")
        loaded=Project.from_dict(legacy);ensure_objects(loaded)
        self.assertEqual(len(loaded.editor_objects),3)
        ensure_objects(loaded);self.assertEqual(len(loaded.editor_objects),3)
    def test_watermark_and_locked_background(self):
        mark=next(o for o in self.project.editor_objects if o.type==ObjectType.WATERMARK)
        self.canvas.objects[mark.id].setPos(50,120)
        self.assertEqual((mark.x,mark.y),(50,120))
        bg=next(o for o in self.project.editor_objects if o.type==ObjectType.BACKGROUND)
        self.assertTrue(bg.locked)
    def test_invalid_geometry(self):
        self.obj.width=-1
        with self.assertRaises(ValueError):self.project.validate()
