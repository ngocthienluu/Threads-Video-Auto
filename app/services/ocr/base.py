from abc import ABC, abstractmethod
from pathlib import Path
from app.core.ocr_models import OCRResult


class OCRProvider(ABC):
    @abstractmethod
    def recognize(self, image: Path) -> str:
        """Return editable OCR text, or raise an actionable provider error."""

    def read_blocks(self, image: Path, **kwargs) -> OCRResult:
        """Compatibility for text-only providers; extractor will mark fallback for review."""
        return OCRResult(full_text=self.recognize(image))
