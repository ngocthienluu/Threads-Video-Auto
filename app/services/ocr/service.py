"""Provider selection and technical-error fallback. Construct once per controller."""
import logging
from dataclasses import replace
from app.services.ocr.base import OCRProvider
from app.services.ocr.errors import OCRError, OCRCancelled
from app.services.ocr.settings import OCRSettings
from app.services.ocr.local_ocr import LocalOCR
from app.services.ocr.paddle_ocr import PaddleOCRProvider

log = logging.getLogger(__name__)


class OCRService(OCRProvider):
    def __init__(self, settings=None):
        self.settings = settings or OCRSettings()
        self.providers = {}
        self.last_warning = ""
        self.last_provider = ""

    def _provider(self, name):
        registry = {"paddle": PaddleOCRProvider, "tesseract": LocalOCR}
        if name not in registry:
            raise OCRError(f"Unknown OCR provider: {name}. Choose paddle or tesseract.")
        if name not in self.providers:
            self.providers[name] = registry[name](self.settings)
        return self.providers[name]

    def recognize(self, image, cancel=None):
        return self.read_blocks(image, cancel).full_text

    def select_provider(self, name):
        """Change the next request's engine without loading or discarding models."""
        if name not in ("paddle", "tesseract"):
            raise OCRError("Choose paddle or tesseract.")
        self.settings = replace(self.settings, ocr_provider=name)

    def read_blocks(self, image, cancel=None):
        self.last_warning = ""
        selected = self.settings.ocr_provider
        primary = self._provider(selected)
        try:
            result = primary.read_blocks(image, cancel=cancel)
            self.last_provider = selected
            return result  # Empty/low-confidence results are successful recognition, not technical failures.
        except OCRCancelled:
            raise
        except OCRError as exc:
            fallback = self.settings.ocr_fallback_provider
            if not fallback or fallback == selected:
                raise
            log.warning("OCR %s failed technically; trying %s", selected, fallback)
            self.last_warning = f"{selected} failed: {exc} Using {fallback} fallback."
            result = self._provider(fallback).read_blocks(image, cancel=cancel)
            self.last_provider = fallback
            return result

    def close(self):
        for provider in self.providers.values():
            if hasattr(provider, "close"):
                provider.close()
