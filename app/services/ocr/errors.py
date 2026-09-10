class OCRError(RuntimeError):
    """An actionable, safe-to-display OCR error (no credentials or request bodies)."""


class OCRCancelled(OCRError):
    pass
