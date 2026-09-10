from pathlib import Path
from PySide6.QtGui import QImageReader

IMAGE_FILTER = "Images (*.png *.jpg *.jpeg *.webp *.bmp)"


def validate_image(path: str) -> str:
    source = Path(path).resolve()
    if not source.is_file():
        raise ValueError(f"Image file is missing: {source.name}")
    if source.suffix.lower() not in {".png", ".jpg", ".jpeg", ".webp", ".bmp"}:
        raise ValueError(f"Unsupported image format: {source.name}")
    reader = QImageReader(str(source))
    reader.setAutoTransform(True)
    if not reader.canRead() or reader.read().isNull():
        raise ValueError(f"Cannot decode image: {source.name}. {reader.errorString()}")
    return str(source)
