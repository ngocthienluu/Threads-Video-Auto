import unittest
from app.core.config import TimingSettings
from app.core.project_manager import ProjectManager
from app.core.timeline import build_timeline


def ready(item, duration):
    item.audio_path = "measured.wav"
    item.audio_duration = duration
    item.tts_status = "done"


class TimelineTests(unittest.TestCase):
    def test_empty(self):
        timeline = build_timeline(ProjectManager().project)
        self.assertEqual(timeline.total_duration, 0)
        self.assertEqual(timeline.segments, ())

    def test_single_with_padding(self):
        manager = ProjectManager()
        item = manager.add_single("s.png").items[0]
        ready(item, 4.2)
        timeline = build_timeline(manager.project)
        self.assertAlmostEqual(timeline.total_duration, 4.45)
        self.assertAlmostEqual(timeline.segments[0].voice_start, .1)
        self.assertAlmostEqual(timeline.segments[0].voice_end, 4.3)
        self.assertEqual(item.timeline_status, "pending")  # Pure builder.

    def test_progressive_thread(self):
        manager = ProjectManager()
        thread = manager.add_thread(["q.png", "qr1.png", "qr1r2.png"])
        manager.project.timing_settings = TimingSettings(0, 0, 0)
        for item, duration in zip(thread.items, (3.2, 1.0, 2.1)):
            ready(item, duration)
        timeline = build_timeline(manager.project)
        self.assertEqual([s.image_path for s in timeline.segments], ["q.png", "qr1.png", "qr1r2.png"])
        self.assertEqual([s.start_time for s in timeline.segments], [0, 3.2, 4.2])
        self.assertAlmostEqual(timeline.total_duration, 6.3)

    def test_multiple_scenes_gap_only_between_scenes(self):
        manager = ProjectManager()
        single = manager.add_single("s.png")
        thread = manager.add_thread(["q.png", "r.png"])
        for item in [*single.items, *thread.items]:
            ready(item, 1)
        timeline = build_timeline(manager.project)
        self.assertAlmostEqual(timeline.total_duration, 3.8)
        self.assertAlmostEqual(timeline.segments[1].start_time, 1.3)
        self.assertAlmostEqual(timeline.segments[2].start_time, 2.55)

    def test_missing_zero_nonfinite_or_stale_duration(self):
        manager = ProjectManager()
        item = manager.add_single("s.png").items[0]
        for duration in (0, -1, float("nan"), float("inf")):
            ready(item, duration)
            with self.subTest(duration=duration), self.assertRaises(ValueError):
                build_timeline(manager.project)
        ready(item, 1)
        item.tts_status = "pending"
        with self.assertRaises(ValueError):
            build_timeline(manager.project)
