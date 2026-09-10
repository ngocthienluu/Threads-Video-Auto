from dataclasses import dataclass
from pathlib import Path
from threading import Event
from app.services.ocr.base import OCRProvider
from app.services.ocr.errors import OCRCancelled
from app.core.config import ExtractionSettings
from app.core.ocr_models import OCRResult
from app.services.content_extractor.base import ExtractionResult
from app.services.content_extractor.threads_extractor import ThreadsExtractor
from uuid import uuid4


@dataclass(frozen=True)
class DetectionPayload:
    ocr: OCRResult
    extraction: ExtractionResult


@dataclass(frozen=True)
class OCRJob:
    image: Path
    cancel: Event
    provider: OCRProvider
    settings: ExtractionSettings | None = None
    read_username: bool = False
    existing_ocr: OCRResult | None = None

    def __call__(self, progress, status):
        progress(5)
        status("Reading screenshot locally (Vietnamese + English)...")
        result = self.existing_ocr or self.provider.read_blocks(self.image, cancel=self.cancel)
        if self.cancel.is_set():
            raise OCRCancelled("OCR cancelled; existing text was kept.")
        progress(75)
        status("Detecting comment body from text positions...")
        settings = self.settings or ExtractionSettings()
        extractor = ThreadsExtractor(settings, self.read_username)
        try:
            extraction = extractor.extract(result)
        except Exception:
            extraction = extractor._fallback(result, "Layout could not be interpreted.")
        if not self.existing_ocr:
            warning = getattr(self.provider, "last_warning", "")
            if warning:
                extraction.warnings.append(warning)
            extraction.debug_info["ocr_provider"] = getattr(self.provider, "last_provider", type(self.provider).__name__)
        if settings.ocr_debug_save_regions and extraction.debug_info.get("body_regions"):
            from PIL import Image, ImageOps
            from app.core.config import ROOT
            regions = extraction.debug_info["body_regions"]
            box = (min(b[0] for b in regions), min(b[1] for b in regions), max(b[2] for b in regions), max(b[3] for b in regions))
            try:
                directory = ROOT / "cache/ocr"
                directory.mkdir(parents=True, exist_ok=True)
                with Image.open(self.image) as image:
                    ImageOps.exif_transpose(image).crop(tuple(map(int, box))).save(directory / f"debug_{uuid4().hex}_body.png")
            except OSError:
                extraction.warnings.append("Could not save the optional debug body crop.")
        if self.cancel.is_set():
            raise OCRCancelled("OCR cancelled; existing text was kept.")
        progress(100)
        return DetectionPayload(result, extraction)
