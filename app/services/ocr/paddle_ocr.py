"""PaddleOCR 3.x adapter, isolated persistent model process; no platform parsing."""
import atexit
import logging
import math
import multiprocessing
from pathlib import Path
from threading import Event, Lock
from time import monotonic

from app.core.ocr_models import OCRBlock, OCRResult
from app.services.ocr.base import OCRProvider
from app.services.ocr.errors import OCRError, OCRCancelled
from app.services.ocr.settings import OCRSettings

log = logging.getLogger(__name__)


def map_prediction(prediction, width, height):
    """Map recognized polygons (not unfiltered detection polygons) to source rectangles."""
    texts = prediction["rec_texts"]
    scores = prediction["rec_scores"]
    polygons = prediction["rec_polys"]
    if not len(texts) == len(scores) == len(polygons):
        raise ValueError("PaddleOCR output lengths differ")
    blocks = []
    for text, score, polygon in zip(texts, scores, polygons):
        if not isinstance(text, str):
            raise ValueError("Invalid recognized text")
        points = [(float(x), float(y)) for x, y in polygon]
        score = float(score)
        if len(points) != 4 or not all(math.isfinite(v) for p in points for v in p) or not math.isfinite(score) or not 0 <= score <= 1:
            raise ValueError("Invalid PaddleOCR polygon/confidence")
        if not text.strip():
            continue
        left = max(0., min(float(width), min(x for x, _ in points)))
        top = max(0., min(float(height), min(y for _, y in points)))
        right = max(left, min(float(width), max(x for x, _ in points)))
        bottom = max(top, min(float(height), max(y for _, y in points)))
        blocks.append(OCRBlock(text.strip(), left, top, right-left, bottom-top, score, "line"))
    blocks.sort(key=lambda b: (b.y + b.height / 2, b.x))
    # Detection may split a header into handle, topic and timestamp boxes.
    # Group horizontally adjacent boxes by vertical overlap without inventing word boxes.
    rows = []
    for block in blocks:
        row = next((row for row in reversed(rows) if
                    min(row[0].y + row[0].height, block.y + block.height) - max(row[0].y, block.y)
                    >= .5 * min(row[0].height, block.height)), None)
        if row is None:
            row = []
            rows.append(row)
        row.append(block)
    ordered = []
    lines = []
    for identity, row in enumerate(rows):
        row.sort(key=lambda b: b.x)
        for block in row:
            block.line_id = identity
        ordered.extend(row)
        lines.append(" ".join(b.text for b in row))
    result = OCRResult("\n".join(lines), ordered, width, height)
    result.validate()
    return result


def _serve(connection, settings):
    """Spawn target: model initialized once and reused until close/cancel/failure."""
    try:
        import os
        from app.core.config import ROOT
        (ROOT / "logs").mkdir(parents=True, exist_ok=True)
        handler = logging.FileHandler(ROOT / "logs/paddle.log", encoding="utf-8")
        log.addHandler(handler)
        log.setLevel(logging.INFO)
        os.environ.setdefault("PADDLE_PDX_CACHE_HOME", str(ROOT / "cache/ocr/paddlex"))
        from paddleocr import PaddleOCR
        from PIL import Image, ImageOps
        import numpy as np
        engine = PaddleOCR(lang=settings.paddle_language, ocr_version="PP-OCRv5",
                           enable_mkldnn=settings.paddle_enable_mkldnn,
                           device="cpu", use_doc_orientation_classify=False,
                           use_doc_unwarping=False, use_textline_orientation=False)
        while True:
            path = connection.recv()
            if path is None:
                break
            with Image.open(path) as source:
                if source.width * source.height > settings.max_pixels:
                    raise ValueError("Image exceeds OCR pixel limit")
                oriented = ImageOps.exif_transpose(source).convert("RGBA")
                image = Image.alpha_composite(Image.new("RGBA", oriented.size, "white"), oriented).convert("RGB")
                predictions = list(engine.predict(np.asarray(image)[:, :, ::-1].copy()))
                if len(predictions) != 1:
                    raise ValueError("Expected one image result")
                result = map_prediction(predictions[0], image.width, image.height)
                connection.send({"result": result.to_dict()})
    except Exception as exc:
        import traceback
        # Keep traceback structure without engine exception text or recognized content.
        log.error("PaddleOCR failure (%s)\n%s", type(exc).__name__, "".join(traceback.format_tb(exc.__traceback__)))
        try:
            connection.send({"error": type(exc).__name__})
        except (OSError, EOFError):
            pass
    finally:
        connection.close()


class PaddleOCRProvider(OCRProvider):
    def __init__(self, settings=None):
        self.settings = settings or OCRSettings()
        self._process = self._connection = None
        self._lock = Lock()
        atexit.register(self.close)

    def recognize(self, image: Path, cancel=None):
        return self.read_blocks(image, cancel).full_text

    def close(self):
        if self._process is not None:
            if self._process.pid is not None:
                if self._process.is_alive():
                    self._process.terminate()
                self._process.join(timeout=2)
            self._process.close()
        if self._connection is not None:
            self._connection.close()
        self._process = self._connection = None

    def read_blocks(self, image: Path, cancel: Event | None = None):
        cancel = cancel or Event()
        with self._lock:
            try:
                if cancel.is_set():
                    raise OCRCancelled("OCR cancelled; existing text was kept.")
                if self._process is None:
                    context = multiprocessing.get_context("spawn")
                    self._connection, child = context.Pipe()
                    self._process = context.Process(target=_serve, args=(child, self.settings), daemon=True)
                    self._process.start()
                    child.close()
                self._connection.send(str(Path(image).resolve()))
                started = monotonic()
                while not self._connection.poll(.1):
                    if cancel.is_set():
                        raise OCRCancelled("OCR cancelled; existing text was kept.")
                    if monotonic() - started > self.settings.paddle_timeout_seconds:
                        raise OCRError("PaddleOCR timed out while loading models or reading image. Check network/model cache, then retry.")
                    if not self._process.is_alive():
                        raise OCRError("PaddleOCR process exited unexpectedly. Check Windows/Python dependencies.")
                response = self._connection.recv()
                if cancel.is_set():
                    raise OCRCancelled("OCR cancelled; existing text was kept.")
                if "error" in response:
                    raise OCRError("PaddleOCR failed (" + response["error"] + "). Install requirements.txt; check model download access and cache permissions. See logs.")
                return OCRResult.from_dict(response["result"])
            except OCRCancelled:
                self.close()
                raise
            except Exception as exc:
                log.exception("PaddleOCR provider failed")
                self.close()
                if isinstance(exc, OCRError):
                    raise
                raise OCRError("PaddleOCR unavailable or returned invalid data. Check installed dependencies and model cache.") from exc
