"""Explicit real-engine comparison; no fallback so failures cannot masquerade as Paddle."""
import argparse
import hashlib
import json
from pathlib import Path
from statistics import mean
from time import monotonic

from app.services.ocr.local_ocr import LocalOCR
from app.services.ocr.paddle_ocr import PaddleOCRProvider
from app.services.content_extractor.threads_extractor import ThreadsExtractor


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("images", nargs="+", type=Path)
    parser.add_argument("--output", type=Path, default=Path("cache/ocr/comparison.json"))
    args = parser.parse_args()
    report = []
    paddle = PaddleOCRProvider()
    try:
        for image in args.images:
            before = hashlib.sha256(image.read_bytes()).hexdigest()
            entry = {"image": image.name, "engines": {}}
            for name, provider in (("tesseract", LocalOCR()), ("paddle", paddle)):
                started = monotonic()
                try:
                    result = provider.read_blocks(image)
                    extraction = ThreadsExtractor().extract(result)
                    entry["engines"][name] = {"raw_text": result.full_text, "blocks": len(result.blocks),
                        "mean_confidence": mean(b.confidence for b in result.blocks) if result.blocks else None,
                        "body_text": extraction.body_text, "extraction_confidence": extraction.confidence,
                        "warnings": extraction.warnings, "seconds": round(monotonic()-started, 2)}
                    if name == "paddle":
                        entry["engines"][name]["process_id"] = paddle._process.pid
                except Exception as exc:
                    entry["engines"][name] = {"error": str(exc)}
                print(image.name, name, "error" if "error" in entry["engines"][name] else "completed", flush=True)
            entry["source_unchanged"] = hashlib.sha256(image.read_bytes()).hexdigest() == before
            report.append(entry)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    finally:
        paddle.close()
    return int(any("error" in engine for entry in report for engine in entry["engines"].values()))


if __name__ == "__main__":
    raise SystemExit(main())
