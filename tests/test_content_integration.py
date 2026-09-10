"""Real local OCR → positioned extraction → progressive narration, no network."""
from dataclasses import replace
import os
from pathlib import Path
import tempfile
from threading import Event
import unittest

from tests.test_ocr import READY
from app.core.project_manager import ProjectManager
from app.services.ocr.jobs import OCRJob
from app.services.ocr.local_ocr import LocalOCR
from app.services.ocr.settings import OCRSettings


@unittest.skipUnless(READY, "Local OCR dependencies/models unavailable")
class ContentIntegrationTests(unittest.TestCase):
    def test_real_progressive_screenshots_and_source_coordinates(self):
        from PIL import Image, ImageDraw, ImageFont
        font_path = Path(os.environ.get("WINDIR", "")) / "Fonts/segoeui.ttf"
        if not font_path.is_file():
            self.skipTest("Windows fixture font unavailable")
        with tempfile.TemporaryDirectory() as temp:
            base = Path(temp)
            font = ImageFont.truetype(str(font_path), 27)
            body = ["Vậy làm cách nào để nhìn trước tương lai đi", "Xem lịch", "Lịch của năm sau nhé"]
            paths = []
            for stage in range(1, 4):
                image = Image.new("RGB", (950, stage * 190), "white")
                draw = ImageDraw.Draw(image)
                for index, line in enumerate(body[:stage]):
                    y = index * 190
                    draw.text((90, y + 12), f"user_{index} 4 giờ", font=font, fill="black")
                    draw.text((100, y + 60), line, font=font, fill="black")
                    draw.text((100, y + 135), "4   2   1", font=font, fill="black")
                path = base / f"thread_{stage}.png"
                image.save(path)
                paths.append(str(path))
            manager = ProjectManager()
            items = manager.add_thread(paths).items
            provider = LocalOCR(replace(OCRSettings(), cache_dir=base / "cache"))
            for item in items:
                source = Path(item.original_image_path)
                original = source.read_bytes()
                payload = OCRJob(source, Event(), provider)(lambda _: None, lambda _: None)
                payload.ocr.validate()
                self.assertTrue(payload.ocr.blocks)
                manager.apply_detection(item, payload.ocr, payload.extraction)
                self.assertEqual(source.read_bytes(), original)
                self.assertNotIn("user_", item.tts_text)
                self.assertNotIn("4 giờ", item.tts_text)
            self.assertIn("tương lai", items[0].tts_text)
            self.assertEqual(items[1].tts_text, "Xem lịch")
            self.assertEqual(items[2].tts_text, "Lịch của năm sau nhé")
            self.assertFalse(any(item.needs_review for item in items))
