"""Explicit one-time model download, never triggered by image recognition."""
import hashlib
import os
import tempfile
from urllib.request import urlopen
from app.services.ocr.settings import DATA_REVISION, MODEL_HASHES, OCRSettings


def main():
    target = OCRSettings().data_dir
    target.mkdir(parents=True, exist_ok=True)
    for name, expected in MODEL_HASHES.items():
        destination = target / name
        if destination.is_file() and hashlib.sha256(destination.read_bytes()).hexdigest() == expected:
            print(f"Verified {name}")
            continue
        url = f"https://raw.githubusercontent.com/tesseract-ocr/tessdata_fast/{DATA_REVISION}/{name}"
        print(f"Downloading {name} ...", flush=True)
        with urlopen(url, timeout=60) as response:
            data = response.read(20_000_001)
        if hashlib.sha256(data).hexdigest() != expected:
            raise RuntimeError(f"Checksum mismatch for {name}; download was not installed.")
        temporary = None
        try:
            with tempfile.NamedTemporaryFile(dir=target, delete=False) as stream:
                temporary = stream.name
                stream.write(data)
            os.replace(temporary, destination)
        finally:
            if temporary and os.path.exists(temporary):
                os.unlink(temporary)
        print(f"Installed {name}")
    print("Vietnamese + English OCR data ready.")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        raise SystemExit(f"OCR setup failed: {exc}. Check your connection and folder permissions.")
