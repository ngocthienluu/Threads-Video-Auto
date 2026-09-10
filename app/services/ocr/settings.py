from dataclasses import dataclass
from pathlib import Path
from app.core.config import ROOT

DATA_REVISION = "87416418657359cb625c412a48b6e1d6d41c29bd"
MODEL_HASHES = {
    "eng.traineddata": "7d4322bd2a7749724879683fc3912cb542f19906c83bcc1a52132556427170b2",
    "vie.traineddata": "79df64caf7bcfb2a27df5042ecb6121e196eada34da774956995747636d5bfa1",
    "LICENSE": "cfc7749b96f63bd31c3c42b5c471bf756814053e847c10f3eb003417bc523d30",
}


@dataclass(frozen=True)
class OCRSettings:
    ocr_provider: str = "tesseract"
    ocr_fallback_provider: str = "tesseract"  # Empty string disables fallback.
    paddle_language: str = "vi"
    paddle_enable_mkldnn: bool = False  # Windows CPU compatibility; opt in after testing.
    paddle_timeout_seconds: float = 300.0  # Includes first model download/load.
    data_dir: Path = ROOT / "assets/ocr/tessdata"
    cache_dir: Path = ROOT / "cache/ocr"
    language: str = "vie+eng"
    page_segmentation: int = 3
    timeout_seconds: float = 60.0
    max_pixels: int = 20_000_000
    upscale: int = 2
    pipeline_version: str = "tesserocr-2.10.0-tesseract-5.5.2-bbox-3"
