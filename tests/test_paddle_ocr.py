from dataclasses import replace
from pathlib import Path
from threading import Event
import unittest
from unittest.mock import MagicMock, patch

from app.core.ocr_models import OCRBlock, OCRResult
from app.services.ocr.errors import OCRError, OCRCancelled
from app.services.ocr.paddle_ocr import PaddleOCRProvider, map_prediction
from app.services.ocr.service import OCRService
from app.services.ocr.settings import OCRSettings


class MappingTests(unittest.TestCase):
    def test_text_polygon_confidence_and_line_grouping(self):
        result = map_prediction({"rec_texts": ["user", "4 giờ", "Tiếng Việt"],
            "rec_scores": [.9, .8, .95], "rec_polys": [
                [[-2, 1], [28, 0], [30, 15], [0, 16]],
                [[40, 0], [60, 0], [60, 16], [40, 16]],
                [[2, 25], [105, 25], [100, 45], [0, 44]]]}, 100, 50)
        self.assertEqual(result.full_text, "user 4 giờ\nTiếng Việt")
        self.assertEqual([b.line_id for b in result.blocks], [0, 0, 1])
        self.assertEqual(result.blocks[0].x, 0)
        self.assertEqual(result.blocks[0].width, 30)
        self.assertEqual(result.blocks[2].width, 100)
        self.assertEqual(result.blocks[2].confidence, .95)
        self.assertEqual(OCRResult.from_dict(result.to_dict()), result)

    def test_empty_and_invalid(self):
        self.assertEqual(map_prediction(dict(rec_texts=[], rec_scores=[], rec_polys=[]), 20, 30), OCRResult("", [], 20, 30))
        for score in (float("nan"), 1.1, -1):
            with self.assertRaises(ValueError):
                map_prediction(dict(rec_texts=["x"], rec_scores=[score], rec_polys=[[[0,0]]*4]), 20, 30)
        with self.assertRaises(ValueError):
            map_prediction(dict(rec_texts=["x"], rec_scores=[], rec_polys=[]), 20, 30)


class ProviderTests(unittest.TestCase):
    def setUp(self):
        self.provider = PaddleOCRProvider()
        self.addCleanup(self.provider.close)

    def test_persistent_process_reused(self):
        context = MagicMock()
        connection, child = MagicMock(), MagicMock()
        context.Pipe.return_value = connection, child
        connection.recv.return_value = {"result": OCRResult("abc", [], 20, 30).to_dict()}
        with patch("app.services.ocr.paddle_ocr.multiprocessing.get_context", return_value=context):
            self.assertEqual(self.provider.recognize(Path("image.png")), "abc")
            self.provider.read_blocks(Path("second.png"))
        self.assertEqual(context.Process.call_count, 1)
        self.assertEqual(connection.send.call_count, 2)

    def test_exception_response_stops_process(self):
        self.provider._process = MagicMock()
        self.provider._connection = MagicMock()
        self.provider._connection.recv.return_value = {"error": "ImportError"}
        with self.assertRaisesRegex(OCRError, "Install requirements"):
            self.provider.read_blocks(Path("x.png"))
        self.assertIsNone(self.provider._process)

    def test_cancel_does_not_start_engine(self):
        cancel = Event()
        cancel.set()
        with self.assertRaises(OCRCancelled):
            self.provider.read_blocks(Path("x.png"), cancel)
        self.assertIsNone(self.provider._process)

    def test_timeout_and_native_crash(self):
        for alive in (True, False):
            self.provider.settings = replace(OCRSettings(), paddle_timeout_seconds=-1 if alive else 300)
            self.provider._process = MagicMock()
            self.provider._process.is_alive.return_value = alive
            self.provider._connection = MagicMock()
            self.provider._connection.poll.return_value = False
            with self.assertRaises(OCRError):
                self.provider.read_blocks(Path("x.png"))
            self.assertIsNone(self.provider._process)


class SelectionTests(unittest.TestCase):
    def test_fallback_only_technical_errors(self):
        service = OCRService(replace(OCRSettings(), ocr_provider="paddle"))
        primary, fallback = MagicMock(), MagicMock()
        service.providers = {"paddle": primary, "tesseract": fallback}
        primary.read_blocks.return_value = OCRResult()
        self.assertEqual(service.read_blocks(Path("x")), OCRResult())
        fallback.read_blocks.assert_not_called()
        primary.read_blocks.return_value = OCRResult("uncertain", [OCRBlock("uncertain", 0, 0, 1, 1, .01)], 10, 10)
        self.assertEqual(service.read_blocks(Path("x")).blocks[0].confidence, .01)
        fallback.read_blocks.assert_not_called()
        primary.read_blocks.side_effect = OCRCancelled("Cancelled")
        with self.assertRaises(OCRCancelled):
            service.read_blocks(Path("x"))
        fallback.read_blocks.assert_not_called()
        primary.read_blocks.side_effect = OCRError("Unavailable")
        fallback.read_blocks.return_value = OCRResult("fallback text")
        self.assertEqual(service.recognize(Path("x")), "fallback text")
        self.assertIn("Unavailable", service.last_warning)
        self.assertEqual(service.last_provider, "tesseract")

    def test_disabled_fallback_and_selection(self):
        service = OCRService(replace(OCRSettings(), ocr_provider="tesseract", ocr_fallback_provider=""))
        from app.services.ocr.local_ocr import LocalOCR
        self.assertIsInstance(service._provider("tesseract"), LocalOCR)
        with patch.object(service._provider("tesseract"), "read_blocks", side_effect=OCRError("bad")):
            with self.assertRaises(OCRError):
                service.read_blocks(Path("x"))
        with self.assertRaises(OCRError):
            service._provider("unknown")
