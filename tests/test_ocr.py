from dataclasses import replace
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sys
import tempfile
from threading import Event, Timer
import unittest
from unittest.mock import patch

from app.core.project_manager import ProjectManager
from app.services.ocr.errors import OCRError, OCRCancelled
from app.services.ocr.local_ocr import LocalOCR
from app.services.ocr.settings import OCRSettings


class OCRApplyTests(unittest.TestCase):
    def test_ocr_preserves_manual_tts_and_requires_explicit_replacement(self):
        manager = ProjectManager()
        item = manager.add_single("image.png").items[0]
        manager.edit_tts(item, "lời đọc riêng")
        self.assertTrue(manager.apply_ocr(item, "hôm nay vui =)))"))
        self.assertEqual(item.ocr_status, "done")
        self.assertEqual(item.display_text, item.ocr_text)
        self.assertEqual(item.tts_text, "lời đọc riêng")
        self.assertTrue(item.tts_text_is_manual)
        self.assertFalse(manager.apply_ocr(item, "new result"))
        self.assertTrue(manager.apply_ocr(item, "new result", replace_existing=True))
        self.assertEqual(item.tts_text, "lời đọc riêng")

    def test_reply_selection_is_explicit_and_protected(self):
        manager = ProjectManager()
        item = manager.add_thread(["q.png", "qr.png"]).items[1]
        manager.apply_ocr(item, "question\nreply =)))")
        self.assertEqual(item.tts_text, "")
        manager.use_ocr_selection(item, "reply =)))")
        self.assertEqual(item.tts_text, "reply")
        self.assertTrue(item.tts_text_is_manual)
        self.assertFalse(manager.use_ocr_selection(item, "different"))
        self.assertTrue(manager.use_ocr_selection(item, "different", overwrite_manual=True))

    def test_empty_result_and_cleared_manual_ocr_are_preserved(self):
        manager = ProjectManager()
        item = manager.add_single("image.png").items[0]
        manager.edit_ocr(item, "text")
        manager.edit_ocr(item, "")
        self.assertFalse(manager.apply_ocr(item, "new"))
        with self.assertRaises(ValueError):
            manager.apply_ocr(item, " ", replace_existing=True)
        with self.assertRaises(ValueError):
            manager.use_ocr_selection(item, "")


class OCRProviderTests(unittest.TestCase):
    def test_missing_image_and_language_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            provider = LocalOCR(replace(OCRSettings(), data_dir=base, cache_dir=base / "cache"))
            with self.assertRaisesRegex(OCRError, "screenshot"):
                provider.recognize(base / "missing.png")
            source = base / "image.png"
            source.write_bytes(b"image")
            with self.assertRaisesRegex(OCRError, "language data"):
                provider.recognize(source)

    def test_cache_by_content_and_corrupt_cache_recovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            config = replace(OCRSettings(), data_dir=base, cache_dir=base / "cache")
            (base / "vie.traineddata").write_bytes(b"model")
            source = base / "ảnh có dấu.png"
            source.write_bytes(b"image one")
            hashes = {"vie.traineddata": hashlib.sha256(b"model").hexdigest()}
            with patch("app.services.ocr.local_ocr.MODEL_HASHES", hashes), patch.object(LocalOCR, "_run", return_value="xin chào") as run:
                provider = LocalOCR(config)
                self.assertEqual(provider.recognize(source), "xin chào")
                self.assertEqual(provider.recognize(source), "xin chào")
                self.assertEqual(run.call_count, 1)
                next(config.cache_dir.glob("*.json")).write_text("broken")
                provider.recognize(source)
                self.assertEqual(run.call_count, 2)
                source.write_bytes(b"image two")
                provider.recognize(source)
                self.assertEqual(run.call_count, 3)
                self.assertEqual(list(config.cache_dir.glob("job-*")), [])

    def test_cancel_before_work(self):
        cancel = Event()
        cancel.set()
        with self.assertRaises(OCRCancelled):
            LocalOCR().recognize(Path("unused.png"), cancel)

    def test_timeout_kills_process(self):
        provider = LocalOCR(replace(OCRSettings(), timeout_seconds=.15))
        with self.assertRaisesRegex(OCRError, "timed out"):
            provider._run([sys.executable, "-c", "import time; time.sleep(30)"], Event())

    def test_cancel_running_process(self):
        cancel = Event()
        timer = Timer(.15, cancel.set)
        timer.start()
        try:
            with self.assertRaises(OCRCancelled):
                LocalOCR()._run([sys.executable, "-c", "import time; time.sleep(30)"], cancel)
        finally:
            timer.join()

    def test_crashed_or_invalid_process_output(self):
        for code in ("raise SystemExit(7)", "print('not JSON')", "print('[]')", "print('{\"text\":\"\"}')"):
            with self.subTest(code=code), self.assertRaises(OCRError):
                LocalOCR()._run([sys.executable, "-c", code], Event())


READY = (importlib.util.find_spec("tesserocr") is not None and
         importlib.util.find_spec("PIL") is not None and
         (OCRSettings().data_dir / "vie.traineddata").is_file())


@unittest.skipUnless(READY, "Run requirements installation and python -m app.services.ocr.setup for real OCR tests")
class RealOCRTests(unittest.TestCase):
    def test_vietnamese_light_and_dark_images_unchanged(self):
        from PIL import Image, ImageDraw, ImageFont
        font_path = Path(os.environ.get("WINDIR", "")) / "Fonts/segoeui.ttf"
        if not font_path.is_file():
            self.skipTest("Windows Segoe UI fixture font unavailable")
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            provider = LocalOCR(replace(OCRSettings(), cache_dir=base / "cache"))
            font = ImageFont.truetype(str(font_path), 36)
            for background, foreground in (("white", "black"), ("black", "white")):
                picture = Image.new("RGB", (900, 150), background)
                ImageDraw.Draw(picture).text((25, 25), "Hôm nay trời đẹp.\nTôi thích tiếng Việt.", fill=foreground, font=font)
                source = base / f"ảnh tiếng Việt {background}.png"
                picture.save(source)
                original = source.read_bytes()
                text = provider.recognize(source)
                self.assertIn("Hôm nay trời đẹp", text)
                self.assertIn("tiếng Việt", text)
                self.assertEqual(source.read_bytes(), original)

    def test_blank_and_corrupt_images_fail(self):
        from PIL import Image
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            provider = LocalOCR(replace(OCRSettings(), cache_dir=base / "cache"))
            blank = base / "blank.png"
            Image.new("RGB", (250, 100), "white").save(blank)
            with self.assertRaisesRegex(OCRError, "No text"):
                provider.recognize(blank)
            blank.write_bytes(b"not an image")
            with self.assertRaisesRegex(OCRError, "decode"):
                provider.recognize(blank)
