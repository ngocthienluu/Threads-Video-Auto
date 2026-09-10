from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from app.core.ocr_models import OCRResult


@dataclass
class ExtractionResult:
    raw_text: str
    body_text: str
    confidence: float
    method: str
    warnings: list[str] = field(default_factory=list)
    debug_info: dict = field(default_factory=dict)


class ContentExtractor(ABC):
    @abstractmethod
    def extract(self, result: OCRResult) -> ExtractionResult:
        """Return body content and heuristic confidence, without TTS cleaning."""
