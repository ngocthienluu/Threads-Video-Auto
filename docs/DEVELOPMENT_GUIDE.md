# Development guide

Read AGENTS.md before coding, then README, PRODUCT_SPEC, ARCHITECTURE, PROGRESS, TODO and DECISIONS. Do not depend on chat history.

## Setup and conventions

Use `.venv` and `requirements.txt` as in README. Python 3.11+, UTF-8, pathlib paths, dataclasses, type hints, small modules. Prefer standard library unless a dependency has a documented reason. Core has no Qt dependency. UI only binds models/actions; services and renderer own long business operations. Use UUID identities and enum values in JSON, never widget state or credentials.

## Extending modules

- OCR: subclass services/ocr/base.py. Current LocalOCR uses a cancellable child process, pinned tessdata_fast data, Pillow preprocessing and cache. Install requirements then run `python -m app.services.ocr.setup`. Keep recognition offline, return actionable OCRError, preserve screenshots, and test real Vietnamese samples. Bump pipeline_version when preprocessing changes so old OCR cache is not reused. Keep Qt dispatch in ui/ocr_controller.py and result/text rules in ProjectManager.
- Extraction: subclass services/content_extractor/base.py, consuming provider-neutral OCRResult. Platform rules belong here, never in OCR provider/UI/cleaner. Use geometry/layout context when filtering; preserve meaningful numbers and return explicit confidence/warnings. The native ResultIterator maps word boxes to oriented source coordinates. Changing this contract needs cache versioning and coordinate tests.
- Thread narration: core/content_pipeline.py maintains full/new body state and uses standard-library fuzzy prefix matching. Missing/uncertain overlap must not narrate the full question. Preserve body_text_is_manual and tts_text_is_manual independently. Reorder/delete/previous-body edits must refresh dependent automatic text and invalidate changed audio.
- TTS: subclass services/tts/base.py; credentials from environment/.env, no logs containing secrets; cache by provider/text/voice/speed, write safely, ffprobe actual duration. Preserve manual edits and reject empty narration.
- Scene: update model validation, ProjectManager operations, serialization tests, timeline semantics, then UI. Question stays first; cumulative screenshots narrate only new reply text.
- Renderer: implement filter_builder independently of UI, then subprocess runner. Verify continuous gameplay with synthetic inputs and ffprobe; retain stderr, distinguish path arguments from filter escaping, validate missing tools/output paths. Do not claim export support until actual encode passes.
- Long operations: use worker progress/status/error/finished signals; update models/widgets on the UI thread. Define cancellation and shutdown before live pipelines are enabled.

## Tests and debug

Run `.\.venv\Scripts\python.exe -m unittest discover -v`. UI tests set Qt offscreen automatically; run `python -m app.main --smoke-test` with QT_QPA_PLATFORM=offscreen for startup/event-loop check. Core-only tests can run without PySide6 using specific test modules. Use temporary directories for fixtures; no external API calls in unit tests.

`tests/test_ocr.py` includes real local engine checks on generated Vietnamese light/dark images, blank/corrupt input, plus cancellation/timeout subprocess tests and cache/edit-safety checks. Real OCR tests skip if dependencies/models are unavailable; report skips honestly. Windows Segoe UI is used only to generate test fixtures. `tests/test_ui.py` checks off-GUI-thread OCR dispatch, cancellation, close safety, explicit reply selection and error restoration with injected providers.

`tests/test_content_extractor.py` covers screenshot-like geometry, varying usernames/timestamps/dates, long bodies, numeric preservation, ROI/confidence fallback, fuzzy diffs, manual safety, reorder recalculation and legacy JSON. `tests/test_content_integration.py` runs generated three-stage progressive PNGs through the actual OCR engine and extraction pipeline. UI tests additionally verify batch auto text, Advanced-only raw selection and explicit Re-run behavior. Debug crops are opt-in and ignored runtime data; never write to source screenshots.

Logs go to logs/app.log, rotating at 2 MB with three backups. Set logging DEBUG during development when needed; never log keys or complete request bodies. Future FFmpeg failures should log sanitized argument arrays and captured stderr; reproduce with disposable media, not user output files.

## Documentation and release

After each phase run relevant tests, run the app when possible, update PROGRESS/TODO and preserve checked items. Behavior changes require PRODUCT_SPEC; decisions/dependencies/folder changes require ADRs. Distinguish implemented, tested, placeholder and deferred. Later releases should pin verified dependencies, add schema migration tests, Windows packaging (e.g. PyInstaller only after evaluation), license notices and a clean-machine FFmpeg/API setup test. Packaging is not implemented yet.
