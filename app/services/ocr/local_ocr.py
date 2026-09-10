import hashlib
import json
import logging
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from threading import Event
from time import monotonic

from app.core.config import ROOT
from app.core.ocr_models import OCRResult
from app.services.ocr.base import OCRProvider
from app.services.ocr.errors import OCRCancelled, OCRError
from app.services.ocr.settings import MODEL_HASHES, OCRSettings

log = logging.getLogger(__name__)


class LocalOCR(OCRProvider):
    def __init__(self, settings: OCRSettings | None = None):
        self.settings = settings or OCRSettings()

    def recognize(self, image: Path, cancel: Event | None = None) -> str:
        return self.read_blocks(image, cancel).full_text

    def read_blocks(self, image: Path, cancel: Event | None = None) -> OCRResult:
        try:
            return self._recognize(image, cancel)
        except OSError as exc:
            raise OCRError("OCR cannot access its files. Check screenshot, language data and cache/ocr folder permissions.") from exc

    def _recognize(self, image: Path, cancel: Event | None = None) -> str:
        cancel = cancel or Event()
        self._check_cancel(cancel)
        config = self.settings
        try:
            content = image.read_bytes()
        except OSError as exc:
            raise OCRError("Cannot read screenshot. Check that the file exists and is accessible.") from exc
        for name, digest in MODEL_HASHES.items():
            if name == "LICENSE":
                continue
            path = config.data_dir / name
            if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
                raise OCRError("OCR language data is missing or damaged. Run: .venv\\Scripts\\python.exe -m app.services.ocr.setup")
        signature = f"{config.pipeline_version}:{config.language}:{config.page_segmentation}:{MODEL_HASHES}"
        key = hashlib.sha256(signature.encode() + content).hexdigest()
        cache = config.cache_dir / f"{key}.json"
        try:
            cached = json.loads(cache.read_text(encoding="utf-8"))
            result = OCRResult.from_dict(cached)
            if result.full_text.strip():
                self._check_cancel(cancel)
                log.info("OCR cache hit")
                return result
        except (OSError, ValueError, TypeError):
            pass
        # Snapshot input to avoid caching results under a hash of subsequently changed media.
        config.cache_dir.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="job-", dir=config.cache_dir) as temporary:
            snapshot = Path(temporary) / ("input" + image.suffix.lower())
            snapshot.write_bytes(content)
            command = [sys.executable, "-m", "app.services.ocr.runner", str(snapshot.resolve()),
                       str(config.data_dir.resolve()), config.language, str(config.page_segmentation)]
            log.info("OCR started")
            text = self._run(command, cancel)
            if isinstance(text, str):  # Compatibility with injected text-only providers/tests.
                text = OCRResult(full_text=text)
        self._check_cancel(cancel)
        temporary_cache = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=config.cache_dir, delete=False) as stream:
                temporary_cache = Path(stream.name)
                json.dump(text.to_dict(), stream, ensure_ascii=False)
            os.replace(temporary_cache, cache)
        except OSError:
            log.warning("OCR completed but cache could not be saved")
        finally:
            if temporary_cache and temporary_cache.exists():
                temporary_cache.unlink()
        log.info("OCR completed")
        return text

    @staticmethod
    def _check_cancel(cancel):
        if cancel.is_set():
            raise OCRCancelled("OCR cancelled; existing text was kept.")

    def _run(self, command, cancel):
        flags = subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0
        try:
            process = subprocess.Popen(command, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                       creationflags=flags, shell=False)
        except OSError as exc:
            raise OCRError("Unable to start OCR. Check your Python environment and permissions.") from exc
        started = monotonic()
        try:
            while True:
                self._check_cancel(cancel)
                if monotonic() - started > self.settings.timeout_seconds:
                    raise OCRError("OCR timed out. Try a smaller screenshot or enter the text manually.")
                try:
                    output, stderr = process.communicate(timeout=.1)
                    break
                except subprocess.TimeoutExpired:
                    continue
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate()
        self._check_cancel(cancel)
        try:
            result = json.loads(output.decode("utf-8"))
            if not isinstance(result, dict):
                raise ValueError()
        except (ValueError, UnicodeError) as exc:
            raise OCRError("OCR engine exited unexpectedly. Reinstall OCR requirements and retry.") from exc
        if process.returncode or "error" in result:
            raise OCRError(result.get("error", "OCR failed. Check your screenshot and language data."))
        try:
            result = OCRResult.from_dict(result)
        except (ValueError, TypeError) as exc:
            raise OCRError("OCR returned invalid position data. Retry recognition.") from exc
        if not result.full_text.strip():
            raise OCRError("No text detected. Try a sharper crop or enter text manually.")
        return result
