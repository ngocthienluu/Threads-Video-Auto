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
        self.project.snap_enabled=False
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

    def test_corner_resize_preserves_aspect_and_opposite_anchor(self):
        from dataclasses import asdict
        from app.core.editor_geometry import resize_corner
        self.obj.x=100;self.obj.y=200;self.obj.width=300;self.obj.height=100
        before=asdict(self.obj)
        result=resize_corner(before,3,700,400)
        self.assertEqual((result["x"],result["y"]),(100,200))
        self.assertAlmostEqual(result["width"]/result["height"],3)
        self.assertEqual(result["width"],600)
        result=resize_corner(before,0,-200,100)
        self.assertAlmostEqual(result["x"]+result["width"],400)
        self.assertAlmostEqual(result["y"]+result["height"],300)
        result=resize_corner(before,3,-1000,-1000)
        self.assertGreaterEqual(result["height"],16)
    def test_snap_center_and_edges(self):
        from app.core.editor_geometry import snap_position
        x,y,guides=snap_position(395,7,300,100,12)
        self.assertEqual((x,y),(390,0));self.assertIn(("x",540),guides)
    def test_inspector_layers_and_undo(self):
        from app.ui.main_window import MainWindow
        window=MainWindow()
        try:
            window.manager.project=self.project;window.refresh(self.project.scenes[0].items[0].id)
            controller=window.visual_editor;controller.select_object(self.obj.id)
            original=self.obj.x
            controller.inspector.fields["x"].setValue(321)
            self.assertEqual(self.obj.x,321)
            self.assertEqual(window.preview.objects[self.obj.id].pos().x(),321)
            controller.undo.undo();self.assertEqual(self.obj.x,original)
            controller.undo.redo();self.assertEqual(self.obj.x,321)
            self.project.snap_enabled=False
            window.preview.objects[self.obj.id].setPos(246,380)
            self.assertEqual(controller.inspector.fields["x"].value(),246)
            self.assertTrue(window.manager.dirty)
            row=next(window.layers.topLevelItem(n) for n in range(window.layers.topLevelItemCount()) if window.layers.topLevelItem(n).data(0,256)==self.obj.id)
            from PySide6.QtCore import Qt
            row.setCheckState(2,Qt.CheckState.Checked)
            self.assertTrue(self.obj.locked)
            controller.edit_field("x",999);self.assertEqual(self.obj.x,246)
            controller.undo.undo();self.assertFalse(self.obj.locked)
            controller.delete_object();self.assertTrue(self.obj.deleted)
            self.assertFalse(window.preview.objects[self.obj.id].isVisible())
            controller.undo.undo();self.assertFalse(self.obj.deleted)
        finally:
            window.manager.dirty=False;window.close()

    def test_scrub_visibility_and_saved_transforms(self):
        from app.ui.main_window import MainWindow
        window=MainWindow()
        try:
            window.manager.project=self.project
            second=window.manager.add_single(str(self.path)).items[0]
            audio=Path(self.temp.name)/"voice.wav";audio.write_bytes(b"measured elsewhere")
            for scene in self.project.scenes:
                for item in scene.items:item.audio_path=str(audio);item.audio_duration=1.0;item.tts_status="done"
            first=self.project.scenes[0].items[0];window.refresh(first.id)
            controller=window.visual_editor;timeline=controller.timeline
            self.assertIsNotNone(timeline)
            controller.edit_field("x",222)
            controller.scrub(timeline.segments[0].end_time)
            self.assertFalse(window.preview.objects[self.obj.id].isVisible())
            second_obj=next(o for o in self.project.editor_objects if o.source_item_id==second.id)
            controller.scrub(timeline.segments[1].start_time)
            self.assertTrue(window.preview.objects[second_obj.id].isVisible())
            self.assertFalse(window.preview.objects[self.obj.id].isVisible())
            self.assertEqual(window.item.id,second.id)
            controller.scrub(timeline.total_duration)
            self.assertFalse(any(i.isVisible() for i in window.preview.objects.values()))
            path=Path(self.temp.name)/"project.json";window.manager.save(path)
            window.manager.load(path);window.refresh(first.id)
            loaded=next(o for o in window.manager.project.editor_objects if o.id==self.obj.id)
            self.assertEqual(loaded.x,222);self.assertEqual(controller.undo.count(),0)
            self.assertEqual(window.preview.objects[loaded.id].pos().x(),222)
        finally:window.manager.dirty=False;window.close()
    def test_real_handle_mouse_gesture(self):
        from PySide6.QtCore import Qt,QPoint
        from PySide6.QtTest import QTest
        self.canvas.show_state(authoring_item=self.obj.source_item_id)
        self.canvas.select_object(self.obj.id);self.app.processEvents()
        item=self.canvas.objects[self.obj.id];handle=item.handles[3]
        start=self.canvas.mapFromScene(handle.scenePos());end=start+QPoint(30,10)
        original=self.obj.width;gestures=[];self.canvas.gesture_finished.connect(lambda *args:gestures.append(args))
        QTest.mousePress(self.canvas.viewport(),Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,start)
        QTest.mouseMove(self.canvas.viewport(),end)
        QTest.mouseRelease(self.canvas.viewport(),Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,end)
        self.assertGreater(self.obj.width,original)
        self.assertAlmostEqual(self.obj.width/self.obj.height,3)
        self.assertEqual(len(gestures),1)
