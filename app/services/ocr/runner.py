"""Isolated native OCR process. Only JSON goes to stdout."""
import json
from pathlib import Path
import sys

from app.services.ocr.settings import OCRSettings
from app.services.ocr.errors import OCRError
from app.core.ocr_models import OCRBlock, OCRResult


def recognize(image_path: Path, data_dir: Path, language: str, psm: int) -> OCRResult:
    from PIL import Image, ImageOps
    from tesserocr import PyTessBaseAPI, OEM, RIL
    settings = OCRSettings()
    with Image.open(image_path) as original:
        if original.width * original.height > settings.max_pixels:
            raise OCRError("Image is too large; crop the comment before OCR (maximum 20 megapixels).")
        # Work only on a decoded copy; source screenshots remain byte-identical.
        source = ImageOps.exif_transpose(original).convert("RGBA")
        width, height = source.size
        background = Image.new("RGBA", source.size, "white")
        gray = ImageOps.grayscale(Image.alpha_composite(background, source))
        # Border pixels describe the UI theme even when a bright attachment fills the image.
        from statistics import median
        edge = median([gray.getpixel((0, y)) for y in range(gray.height)])
        if edge < 127:
            gray = ImageOps.invert(gray)
        factor = min(settings.upscale, (settings.max_pixels / (gray.width * gray.height)) ** .5)
        gray = gray.resize((max(1, round(gray.width * factor)), max(1, round(gray.height * factor))), Image.Resampling.LANCZOS)
        sx, sy = gray.width / width, gray.height / height
        gray = ImageOps.expand(gray, border=12, fill="white")
        with PyTessBaseAPI(path=str(data_dir), lang=language, psm=psm, oem=OEM.LSTM_ONLY) as api:
            api.SetImage(gray)
            api.SetSourceResolution(300)
            text = api.GetUTF8Text().strip()
            if not text:
                return OCRResult("", [], width, height)
            blocks = []
            iterator = api.GetIterator()
            line_id = -1
            if iterator:
                while True:
                    if iterator.IsAtBeginningOf(RIL.TEXTLINE):
                        line_id += 1
                    word = iterator.GetUTF8Text(RIL.WORD)
                    box = iterator.BoundingBox(RIL.WORD)
                    if word and word.strip() and box:
                        left, top, right, bottom = box
                        x = max(0, min(width, (left - 12) / sx))
                        y = max(0, min(height, (top - 12) / sy))
                        right = max(x, min(width, (right - 12) / sx))
                        bottom = max(y, min(height, (bottom - 12) / sy))
                        blocks.append(OCRBlock(word.strip(), x, y, right - x, bottom - y,
                                               max(0, min(1, iterator.Confidence(RIL.WORD) / 100)), "word", max(0, line_id)))
                    if not iterator.Next(RIL.WORD):
                        break
        return OCRResult(text, blocks, width, height)


def main():
    try:
        result = recognize(Path(sys.argv[1]), Path(sys.argv[2]), sys.argv[3], int(sys.argv[4]))
        if not result.full_text:
            raise OCRError("No text detected. Try a sharper, tightly cropped screenshot or enter text manually.")
        print(json.dumps(result.to_dict(), ensure_ascii=True))
        return 0
    except ImportError:
        message = "OCR dependency is missing. Install requirements.txt with the project .venv Python."
    except OCRError as exc:
        message = str(exc)
    except (OSError, ValueError):
        message = "OCR could not decode or read text from this image. Use a clear PNG/JPG crop under 20 megapixels."
    except Exception:
        message = "Tesseract failed. Run python -m app.services.ocr.setup to verify language data, then retry."
    print(json.dumps({"error": message}))
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
