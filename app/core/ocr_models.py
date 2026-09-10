"""Provider-neutral OCR geometry in the oriented source image's coordinates."""
from dataclasses import asdict, dataclass, field
import math


@dataclass
class OCRBlock:
    text: str
    x: float
    y: float
    width: float
    height: float
    confidence: float = 0.0
    level: str = "word"
    line_id: int = 0


@dataclass
class OCRResult:
    full_text: str = ""
    blocks: list[OCRBlock] = field(default_factory=list)
    image_width: int = 0
    image_height: int = 0

    def to_dict(self):
        return asdict(self)

    @classmethod
    def from_dict(cls, data):
        if not isinstance(data, dict) or not isinstance(data.get("full_text"), str):
            raise ValueError("Invalid OCR result")
        result = cls(data["full_text"], [OCRBlock(**block) for block in data.get("blocks", [])],
                     data.get("image_width", 0), data.get("image_height", 0))
        result.validate()
        return result

    def validate(self):
        if type(self.image_width) is not int or type(self.image_height) is not int or min(self.image_width, self.image_height) < 0:
            raise ValueError("Invalid OCR image dimensions")
        for block in self.blocks:
            if not isinstance(block.text, str) or type(block.line_id) is not int:
                raise ValueError("Invalid OCR block")
            values = (block.x, block.y, block.width, block.height, block.confidence)
            if not all(type(v) in (int, float) and math.isfinite(v) and v >= 0 for v in values):
                raise ValueError("Invalid OCR coordinates/confidence")
            if block.confidence > 1 or block.x + block.width > self.image_width + 1 or block.y + block.height > self.image_height + 1:
                raise ValueError("OCR block outside image")
