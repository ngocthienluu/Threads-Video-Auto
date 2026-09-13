import os
os.environ.setdefault("QT_QPA_PLATFORM","offscreen")
import unittest
from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QPoint,Qt
from PySide6.QtTest import QTest
from app.core.editor_timeline import TimelineScale, TimelineClip, clips_from_project
from app.core.models import Project,Scene,SceneItem
from app.core.editor_scene import ensure_objects,sync_timings
from app.core.timeline import build_timeline
from app.ui.timeline.timeline_widget import TimelineWidget

class EditorTimelineTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):cls.app=QApplication.instance() or QApplication([])
    def test_time_conversion(self):
        scale=TimelineScale(80)
        self.assertEqual(scale.time_to_x(2.5),200)
        self.assertEqual(scale.x_to_time(200),2.5)
    def test_real_clips_and_pending(self):
        item=SceneItem(original_image_path="missing.png",audio_path="voice.mp3",audio_duration=2.0,tts_status="done")
        project=Project(scenes=[Scene(items=[item])]);ensure_objects(project)
        self.assertEqual(clips_from_project(project,None),[])
        timeline=build_timeline(project);sync_timings(project,timeline)
        clips=clips_from_project(project,timeline)
        voice=next(c for c in clips if c.track=="Voice")
        comment=next(c for c in clips if c.track=="Comments")
        self.assertEqual(voice.duration,2.0)
        self.assertEqual(voice.start_time,project.timing_settings.voice_pre_padding)
        self.assertEqual(comment.end_time,timeline.total_duration)
        self.assertFalse(any(c.track=="Music" for c in clips))
    def test_blocks_zoom_and_mouse_scrub(self):
        widget=TimelineWidget();widget.resize(1000,280);widget.show();self.app.processEvents()
        try:
            clip=TimelineClip("comment","Comments",2,4,"Comment")
            widget.set_data([clip],10)
            block=widget.scene.blocks[0];self.assertEqual(block.rect().x(),160);self.assertEqual(block.rect().width(),160)
            widget.zoom.setValue(100);block=widget.scene.blocks[0]
            self.assertEqual(block.rect().x(),200)
            selected=[];scrubbed=[];widget.clip_selected.connect(selected.append);widget.scrubbed.connect(scrubbed.append)
            point=widget.view.mapFromScene(block.rect().center())
            QTest.mouseClick(widget.view.viewport(),Qt.MouseButton.LeftButton,Qt.KeyboardModifier.NoModifier,point)
            self.assertEqual(selected,[clip]);self.assertAlmostEqual(scrubbed[-1],3,delta=.02)
            self.assertEqual((clip.start_time,clip.end_time),(2,4))
        finally:widget.close()
