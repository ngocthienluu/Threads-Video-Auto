# Architecture decisions

## ADR-001: Python and PySide6 desktop UI

Date: 2026-09-08
Status: Accepted
Context: Local Windows authoring with simple desktop controls.
Decision: Python 3.11+ and Qt Widgets via PySide6; unittest for tests.
Reason: Matches specification and keeps core independent of UI.
Alternatives: Electron, web frontend, Tkinter.
Consequences: Qt dependency required; offscreen tests complement later visible desktop review. See Qt documentation linked in ARCHITECTURE.md.

## ADR-002: FFmpeg final rendering

Date: 2026-09-08
Status: Accepted, implementation deferred
Context: Continuous gameplay and precisely timed screenshot/narration tracks.
Decision: Single FFmpeg graph, ffprobe-measured durations, subprocess argument arrays.
Reason: Avoid Python frame rendering and per-scene background restarts.
Alternatives: MoviePy, rendering individual scenes then concatenating.
Consequences: External tools and Windows filter escaping require integration testing.

## ADR-003: Provider contracts

Date: 2026-09-08
Status: Accepted
Context: Iteration 1 excludes actual OCR/API integration.
Decision: Abstract OCR/TTS providers; explicit unavailable local OCR and ElevenLabs implementations. Local OCR engine choice deferred until tested with Vietnamese screenshots.
Reason: Do not imply unverified OCR or paid API behavior.
Alternatives: Fake OCR/voice, hardwired SDK in UI.
Consequences: Auto Generate remains disabled; .env is a future credential template only.

## ADR-004: Typed dataclasses and versioned JSON

Date: 2026-09-08
Status: Accepted
Context: Persist scenes, manual edits, configuration and future effects.
Decision: Standard-library dataclasses/enums with explicit validation and atomic UTF-8 JSON save; asset references relative to project file where possible.
Reason: Transparent portable data without extra schema/database dependencies.
Alternatives: SQLite, pickle, copying all assets into a bundle.
Consequences: Cross-drive paths remain absolute; users must retain media files. Future schemas require explicit migration.

## ADR-005: Worker and cache boundaries

Date: 2026-09-08
Status: Accepted, pipeline deferred
Context: OCR, network and FFmpeg can block GUI.
Decision: QRunnable/QThreadPool signal-based worker, UUID item IDs, future provider/text/voice/speed cache hashes, explicit stale audio invalidation.
Reason: Keep widgets on GUI thread and prevent reuse after edits.
Alternatives: Synchronous pipeline, background widget mutations.
Consequences: Worker abstraction exists before service orchestration; cancellation/retries remain future work.

## ADR-006: Static preview and incremental scope

Date: 2026-09-08
Status: Accepted
Context: First iteration explicitly prioritizes basic authoring.
Decision: Static aspect-preserving screenshot preview; disabled generation/export; implement pure timeline and JSON roundtrip now for tests.
Reason: Make progress reviewable without faking rendering.
Alternatives: Full real-time media editor in first iteration.
Consequences: No background/audio preview. Adds app/utils/workers.py and UI smoke tests to the requested structure for focused responsibilities. No other structural deviation.

## ADR-007: Protect cumulative reply narration

Date: 2026-09-08
Status: Historical iteration-1 behavior; automatic diff superseded by ADR-011/013
Context: Cleaning OCR from a cumulative reply screenshot would read the question again.
Decision: Require manually authored reply-only TTS in iteration 1; reject automatic cleaning for reply items. Preserve manual text unless replacement is explicitly requested for supported item roles.
Reason: Reply extraction cannot be reliably inferred by a generic emoticon cleaner.
Alternatives: Blindly narrate cumulative OCR or guess a textual diff.
Consequences: Question/Single can use Clean → TTS. Future OCR orchestration needs a reviewable reply extraction stage.

## ADR-008: Offscreen Windows font fallback

Date: 2026-09-08
Status: Accepted and verified by screenshot
Context: Qt offscreen discovered no font families and rendered unreadable square glyphs.
Decision: Only when font discovery is empty, load Segoe UI from WINDIR/Fonts via QFontDatabase. No copied font or hard-coded absolute system path.
Reason: Make offscreen visual validation meaningful without changing native Windows font selection.
Alternatives: Ignore screenshot failure or bundle an additional font asset.
Consequences: Shared UI initialization is also used by UI tests; native desktop rendering remains to be reviewed separately.

## ADR-009: Local Tesseract through standalone Windows wheels

Date: 2026-09-08
Status: Accepted; tested on Python 3.13.1 Windows x64
Context: Selected-item Vietnamese OCR is the next phase; no Tesseract executable was installed.
Decision: Use tesserocr 2.10.0 / Tesseract 5.5.2 standalone Windows wheels linked by the [upstream installation guide](https://github.com/sirfz/tesserocr#windows), plus Pillow 12.1.1 for preprocessing. Pin wheels and SHA-256 for Python 3.11/3.12/3.13 x64. Use Vietnamese and English data from [tessdata_fast](https://github.com/tesseract-ocr/tessdata_fast) at commit 87416418657359cb625c412a48b6e1d6d41c29bd, downloaded by explicit setup with checksum verification.
Reason: Local recognition without credentials, system-wide installation or per-image network requests. Pillow supports decoding, EXIF, alpha and grayscale before OCR; the wrapper uses the native engine directly.
Alternatives: Separate Tesseract CLI installer, Windows OCR language packs, cloud OCR, larger neural OCR dependencies.
Consequences: Adds assets/ocr/tessdata and focused settings/setup/runner/jobs/errors modules under services/ocr. Model binaries are ignored; LICENSE is downloaded with models. Real samples show useful Vietnamese text but imperfect accents and interface/icon noise; review is mandatory. Other Python/OS/architecture combinations are not verified or packaged. OCR data is independently configured, so project JSON schema stays version 1.

## ADR-010: Isolate OCR and require explicit text review

Date: 2026-09-08
Status: Process isolation retained; selection-only workflow superseded by ADR-011/013
Context: Native OCR can block or fail; cumulative screenshots include text that must not be narrated again.
Decision: QRunnable dispatches OCRJob; LocalOCR launches a child Python process with bounded timeout, cancellation kill/reap and JSON results. OCRController freezes editing during a job and applies results in a queued GUI slot. OCR never writes TTS automatically. Selection → TTS explicitly copies only the user-selected passage, applying cleaner rules and marking it manual.
Reason: Keeps UI responsive and prevents automatic question duplication or manual-text loss. Thread heuristics would be unreliable across screenshot layouts.
Alternatives: Native OCR directly in GUI/worker process, automatic text diffs, automatic full-screen OCR-to-TTS.
Consequences: Adds ui/ocr_controller.py for job lifecycle; generic Worker accepts safe exception types. Central editor is scrollable to fit OCR controls. Progress is stage-based (start/completion), not a claimed character-level percentage. Only one selected item is processed at a time. Cancelling/closing preserves text. Content/model/pipeline cache reuses OCR results; core tests and real-engine tests cover these boundaries.

Preprocessing follows the [Tesseract quality guide](https://tesseract-ocr.github.io/tessdoc/ImproveQuality.html): operate on a copy with orientation/alpha handling, grayscale, dark-background inversion, upscaling and border. Original media bytes remain unchanged.

## ADR-011: Introduce Content Extractor layer between OCR and Text Cleaner

Date: 2026-09-08
Status: Accepted and tested; supersedes the manual-selection-only behavior in ADR-007/010
Context: Whole-screenshot OCR includes usernames, timestamps, interaction counts and UI labels, requiring repetitive manual selection.
Decision: Add ContentExtractor/ExtractionResult and ThreadsExtractor. Use normalized ROI priors, positioned word/line grouping, header/date anchors, inferred body columns and separated footer context to extract full body text. Keep speech cleanup in TextCleaner. A core content pipeline applies results, respects independent manual body/TTS flags and prepares text automatically. Raw OCR and manual selection move into Advanced. Enable Auto Generate Text for all items without implying voice/video generation.
Reason: Deterministic local layout rules address automation without an LLM, heavy detector or extra dependency. Fixed pre-OCR cropping alone would truncate long posts and miss left-aligned cards; the ROI therefore guides extraction after a positioned layout scan and expands with anchors. Optional debug crops expose the selected region.
Consequences: New services/content_extractor/{base,threads_extractor,thread_diff}.py; core/ocr_models.py and content_pipeline.py; additive model/config fields. Low-confidence single extraction falls back to raw draft text with warnings. Confidence is an interpretable heuristic, not an accuracy probability. Atypical layouts and OCR accent errors still need review; rules are not universal platform detection.

## ADR-012: Preserve OCR text API and add source-coordinate word boxes

Date: 2026-09-08
Status: Accepted and tested
Context: Extraction needs geometry while existing callers/tests use recognize() → str.
Decision: Keep recognize() as a compatibility wrapper and add read_blocks() → OCRResult. Use the native [tesserocr ResultIterator API](https://github.com/sirfz/tesserocr/blob/master/tesserocr/tesserocr.pyx) with WORD/TEXTLINE levels (equivalent positional data to TSV); undo preprocessing scale/border and return oriented-source coordinates. Cache full structured data with pipeline bbox-2.
Reason: No extra CLI dependency or duplicate image decoding is required. The existing isolated native process already owns the API lifetime.
Consequences: The internal child-process JSON protocol changes from text to full_text/blocks/dimensions; cache versioning avoids old payload reuse. Public string API remains compatible. Project schema_version remains 1 with additive defaults; the new app loads old projects, but old app builds may reject new fields. Legacy manual OCR becomes protected manual body, and manual TTS survives migration.

## ADR-013: Conservative progressive prefix diff and manual override safety

Date: 2026-09-08
Status: Accepted and tested
Context: Each cumulative Thread screenshot contains earlier narration plus the new reply, with potential OCR variations.
Decision: Accent-normalized token-prefix alignment using difflib.SequenceMatcher; configurable .84 overlap threshold with stricter short-context matching. Emit only the original-text suffix. Missing/uncertain/identical overlap yields no automatic reply and Needs review. Recompute downstream automatic narration after body/order changes. Protect manual body and TTS independently, including empty overrides; explicit Re-run extraction replaces only the selected manual body.
Reason: Prevent repeated questions while tolerating minor spelling/diacritic differences without string-replace-only logic.
Consequences: Store cumulative full_body_text, new_body_text, overlap score and review state. Selected-item jobs read predecessors before applying a reply. Batch cancellation keeps completed results; dependent automatic text can be recomputed, but manual text is preserved. No actual cumulative user Thread screenshot was supplied for this run: progressive behavior is verified with synthetic screenshot geometry, generated image fixtures through the real engine, and Qt queue tests.

## ADR-014 ? Mixed-media OCR and reviewable spelling suggestions
Context: cmt4/cmt5 contain large drawings; PSM 6 interpreted drawings as text, and missing timestamp/short top captions defeated ROI filtering.
Decision: switch to PSM 3, infer polarity from the border, strengthen layout-based header/column/counter handling, and invalidate OCR cache. Keep current Tesseract models. Add local contextual spelling suggestions with explicit preview/edit/Save rather than silently changing ambiguous Vietnamese tokens.
Reason: mixed text/image segmentation fixes the supplied captions without a new dependency; manual review avoids rewriting names and slang.
Consequences: OCR still misses accents; the small phrase vocabulary does not cover general grammar. Existing saved OCR requires READ IMAGE to refresh. Save protects the corrected body and preserves manual TTS.

## ADR-015: Add PaddleOCR as an alternative OCR provider

Context: Tesseract can misrecognize Vietnamese accents and screenshot UI text. We need a practical comparison without replacing the working engine or platform extractor.

Decision: Add PaddleOCRProvider behind the existing OCRProvider/OCRResult interface and OCRService selection; keep LocalOCR as the Tesseract implementation and optional technical-error fallback. Use official PaddleOCR 3.7.0 / CPU PaddlePaddle 3.3.1, with a CPython 3.13 win_amd64 wheel resolved for the current environment. Use PP-OCRv5 Vietnamese (`vi`) recognition, as listed in the [official multilingual guide](https://github.com/PaddlePaddle/PaddleOCR/blob/main/docs/version3.x/algorithm/PP-OCRv5/PP-OCRv5_multi_languages.en.md), and the [3.x prediction API](https://www.paddleocr.ai/main/en/version3.x/pipeline_usage/OCR.html).

Consequences: Larger dependencies and slower first model load/download; accuracy may improve but must be measured on real screenshots. Windows/Python compatibility must be checked per environment. A persistent isolated process reuses the model while preserving cancellation and native-crash containment; this is an added provider implementation, not a Tesseract rewrite. No fallback for empty/low-confidence output. Config remains runtime-only because there is no editable OCR settings UI. Downloaded Paddle models are managed by the upstream SDK, unlike the SHA-pinned Tesseract setup. Integration evidence is recorded separately in PROGRESS.md.

Observed compatibility adjustment: MKL-DNN inference raised NotImplementedError on this Windows CPU setup; `paddle_enable_mkldnn=False` is the default and plain CPU inference was tested. PaddlePaddle import creates its own profile dataset cache, which required access outside the sandbox during initial integration; the PaddleX model cache remains project-local. Do not redirect HOME/USERPROFILE or modify installed library code to hide that requirement.

## ADR-016: Tesseract default and selected-item ElevenLabs narration
Date: 2026-09-10
Context: The user chose Tesseract as the primary engine and requested the next roadmap phase: speech, cache and measured timing.
Decision: Keep the OCR selector but default to Tesseract. Implement ElevenLabs via explicit HTTPX requests, selecting eleven_flash_v2_5 because official model documentation lists Vietnamese (Multilingual v2 does not). Store secrets only in runtime .env/environment settings. Use existing SceneItem voice/audio fields and TTSProvider abstraction, a worker controller, atomic content-keyed audio cache and ffprobe measurements. Generate Voice is an explicit selected-item action; Auto Generate Text does not make paid speech requests.
Consequences: Account/API key and voice permissions are required for live synthesis; requests can use credits even if subsequently cancelled. No automatic API retry. Cancellation can wait for an in-flight network timeout. Cached audio is revalidated, and all-item measured audio is required for the timeline. Add services/tts/{settings,errors,service}.py and ui/tts_controller.py; no project schema change. Local FFmpeg/ffprobe lives under tools/ffmpeg, with binary files ignored, original license and build/checksum provenance retained; system PATH is unchanged. Video renderer remains deferred.
References: https://elevenlabs.io/docs/overview/models ; https://elevenlabs.io/docs/api-reference/text-to-speech/convert ; https://elevenlabs.io/docs/api-reference/voices/search ; https://ffmpeg.org/download.html


## ADR-017: Dynamic ElevenLabs voice selection and access-state handling
Date: 2026-09-10
Status: Accepted; mock/offscreen validation, live integration not performed.
Context: A listed voice returned HTTP 402 when the user attempted speech generation. Voice-list metadata alone does not establish the current account/model's synthesis access.
Decision: Add VoiceInfo/VoiceCatalog and a focused VoicePanel within the existing editor. Cache metadata only and show unknown access until a fresh explicit test/generation succeeds. Use the existing worker for list/details/test/synthesis. Test only the selected voice with a short fixed sample, never scan voices. Typed safe errors support friendly titles, persistent status and no secret response bodies. Retain manual Voice ID and .env fallback; additive project defaults plus item overrides persist selection/model. Keep stale recordings playable but out of the timeline, and publish regenerated files only after validation.
Consequences: More voice-state and cache tests are needed; available is evidence from the current session/model, not a lasting entitlement guarantee. Cache intentionally does not retain access observations or account identifiers. Test and forced regeneration may consume credits, and cancellation cannot guarantee remote billing cancellation. No preview streaming, automatic retries or new dependencies. Existing OCR and renderer architecture is unchanged.


## ADR-018: Explicit reference-aware audio cache cleanup
Date: 2026-09-10
Context: User wants unused generated recordings removed to save disk space and confirms projects are saved in the application projects/ folder.
Decision: Add a single Tools action with an asynchronous scan, count/size preview and explicit deletion. Protect both current unsaved and saved project references, shared audio and remembered external projects. Scan again before deleting and skip changed files. Limit deletion to generated hash-named MP3 files; unreadable projects block cleanup. Preserve active previous recordings even if stale for timeline purposes.
Consequences: Safe reuse across projects takes priority over deleting every old file. Test samples and superseded unreferenced cache entries can be removed, but regenerating them may consume credits. The app cannot discover every JSON saved anywhere on the machine; older external projects must be added. No destructive cleanup is triggered automatically on close, and there is no new dependency.


## ADR-019: Continuous FFmpeg export with static input preparation
Date: 2026-09-14
Context: OCR, selected-item narration and cache are usable; next V1 phases are media controls and final MP4 export.
Decision: Implement the planned single continuous FFmpeg graph, using ffprobe measurements on an immutable project snapshot. Prepare screenshots/watermark once with Pillow, then let FFmpeg handle every video frame. Rasterize watermark text to avoid filter quoting problems. Stage output next to destination, validate it and atomically publish; cancel/error keep prior output. Use existing Worker/UI cancellation conventions and existing project settings, without changing schema or introducing dependencies.
Consequences: Correct final export precedes a composed preview. All items need current audio. Random media files can be selected through existing JSON flags; normal UI selects explicit files and random start/loop. Two encoder/filter threads reduce CPU pressure, but input count/resolution still affect memory; large projects require later scalability validation. FFmpeg 9.0.1 is tested, including its -/filter_complex syntax. Enabled deferred effects are rejected instead of silently dropped.
