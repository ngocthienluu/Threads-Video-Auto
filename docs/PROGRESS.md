# Current Status

Last updated: 2026-09-14
Current phase: V1 media settings and final MP4 export
Current milestone: OCR, voice workflow and final MP4 export implemented; see latest dated entry for validation. Older sections below are historical.

## Completed

- [x] Inspected empty project root and recorded scope.
- [x] Created AGENTS.md and initial product/architecture/development documentation.
- [x] Phase 0 foundation: central defaults, dataclass models, strict versioned JSON, atomic save/load, runtime paths and rotating logging.
- [x] Minimal phase 1: PySide6 main window, validated image import, Single/Thread/question/replies, selection, delete and move controls.
- [x] Manual OCR/Display and independent TTS editing; explicit replacement control; stale audio invalidation on text/voice changes.
- [x] Rule-based cleaner with Vietnamese/emoticon/URL/emoji/known-username tests. Cumulative reply cleaning is blocked to prevent repeated question narration.
- [x] Pure timeline foundation with measured-duration contract, padding, scene gaps and progressive screenshot sequence tests.
- [x] JSON roundtrip preserves IDs, settings, manual edits, effect configs and relative media paths; missing media reported; failed load/save preserves previous data.
- [x] Static portrait screenshot preview and disabled, clearly labeled generation/export/settings placeholders.
- [x] Installed PySide6 6.11.0 into project-local .venv; pip check passed.
- [x] 25 tests passed: 10 model/manager/persistence, 6 cleaner, 5 timeline, 4 offscreen UI.
- [x] Main-window startup/event-loop smoke test passed; offscreen screenshot inspected after fixing missing font discovery.
- [x] User-provided screenshot confirmed iteration-1 native window opens and imports an image; this is not full desktop acceptance testing.
- [x] Installed pinned tesserocr Windows wheel, Pillow and checksum-verified Vietnamese/English models locally.
- [x] READ IMAGE fills editable OCR/Display through a worker and isolated native process; no image upload or automatic TTS overwrite.
- [x] Added explicit OCR replacement, Selection → TTS for reply-only review, content-keyed cache, cancellation, timeout, safe close and actionable errors.
- [x] 41 tests passed with zero skips, including real Vietnamese light/dark OCR, blank/corrupt images, cache, process cancellation/timeout and UI lifecycle.
- [x] Ran OCR on both real screenshots in input/comments and visually reviewed the offscreen OCR UI screenshot.
- [x] Iteration 3: provider-neutral OCRBlock/OCRResult with source-coordinate boxes, confidence and line IDs; compatible recognize() string API retained.
- [x] Added ContentExtractor abstraction and ThreadsExtractor using normalized ROI priors, adaptive header/body/footer geometry and contextual noise filtering.
- [x] Added cumulative full_body/new_body fields, fuzzy accent-tolerant progressive prefix matching, heuristic confidence and review state.
- [x] Normal flow now automatically fills Detected Comment and TTS Text; Raw OCR/Selection moved to Advanced. Auto Generate Text processes scene-ordered jobs.
- [x] Independent manual body/TTS protection, explicit selected-item Re-run, empty-text/uncertain-diff guards, downstream recalculation and additive legacy JSON loading.
- [x] 62 tests passed with no skips: existing cleaner/models/timeline/OCR/UI plus content extraction/diff/persistence/manual safety and real-engine progressive image integration.
- [x] Actual comment1.png, comment2.png and comment3.png extracted through Auto Generate Text UI offscreen; source hashes unchanged; structured project saved/reloaded successfully.
- [x] Updated agent rules, README, product/architecture/roadmap/development docs, progress/TODO and ADR-011/012/013.

## In Progress

- No implementation task remains active in this iteration. Review on the user's visible Windows desktop and additional real progressive screenshots are still pending.

## Not Started

- [ ] ElevenLabs, ffprobe duration pipeline, media composition and final export.
- [ ] Advanced preview, meme/SFX rendering, presets and batch generation.

## Known Issues

- No actual narration audio or video can be generated yet. TTS Text is generated automatically; low-confidence extraction or uncertain thread overlap may require manual correction.
- Preview is an image on a dark portrait canvas: no gameplay, watermark, music, audio playback or timing simulation. Rendering settings are read-only placeholders.
- Iteration-3 UI was verified offscreen; earlier user screenshots confirm previous UI versions open on the desktop, not full acceptance of the new workflow.
- Actual screenshot OCR still has accent/spelling errors. Header/footer extraction worked on the three supplied images, but the confidence score measures heuristics and is not a guarantee of spelling correctness. No universal Threads-layout detector is claimed.
- Atypical crops, unrecognized timestamps, noisy/merged OCR lines, multiple unanchored cards and reply screenshots missing the previous question may need review. Low-confidence Single fallback exposes raw draft text; uncertain replies withhold automatic narration to avoid repetition.
- Real progressive user screenshot sets were not available. Thread behavior was tested with screenshot-like positioned results and three generated progressive PNGs through the real Tesseract engine, plus the Qt batch queue.
- TTS, audio probing and renderer remain interfaces. The OCR worker lifecycle is implemented/tested; paid API behavior remains untested.
- OCR setup downloads models explicitly; normal recognition is offline. Only Windows x64 Python 3.13 was executed here; 3.11/3.12 wheel URLs are configured but untested. Native OCR times out after 60 seconds; input limit is 20 MP.
- Small file saves/image decodes are synchronous; large import responsiveness, media relinking, undo and drag/drop are deferred.
- Cleaner does not implement emoji meaning mode; ThreadsExtractor owns header/user filtering. Media remains externally referenced. Missing new fields in old schema-1 projects are defaulted/migrated; unknown fields/unsupported versions are still rejected. Old app builds may not open newly saved extraction fields.
- A full positioned layout scan precedes adaptive ROI filtering; the app does not hard-crop every screenshot before knowing its layout. Debug region crops are optional and off by default. OCR model/PSM limitations still affect geometry quality.

## Blockers

- No blocker for the tested extraction/text scope. OCR dependencies and models are installed; no new dependency or external API was added in this iteration.
- FFmpeg and ffprobe are not on PATH (discovery checked); actual probe/render testing is blocked until installed and implemented.
- Live ElevenLabs requires later provider implementation and a user-configured key/voice. No key was inspected, no API request was sent, no live TTS was tested.

## Last Work Session

Date: 2026-09-08
What was changed: Added automatic body extraction and reply-only TTS text preparation, replacing mandatory manual selection while preserving overrides and cache/persistence safety.
Files added: app/core/ocr_models.py, app/core/content_pipeline.py; app/services/content_extractor/{__init__,base,threads_extractor,thread_diff}.py; tests/test_content_extractor.py; tests/test_content_integration.py.
Files modified: core/config.py, models.py, project_manager.py; services/ocr/{base,runner,local_ocr,settings,jobs}.py; ui/{comment_editor,ocr_controller,main_window}.py; tests/test_ui.py; AGENTS.md, README.md and all project documentation files.
Tests performed: Full unittest suite: 62 passed, zero skips. Coverage includes screenshot-like header/footer/noise/numbers, variable lengths/scales/dates, ROI/confidence fallback, exact/fuzzy/missing/identical prefix, three-stage real-engine generated Thread screenshots, geometry validation, manual flags/empty overrides, reorder recomputation, legacy JSON, Auto Generate Text and Re-run UI. Also ran actual UI batch over three local user screenshots, source SHA-256 equality, project save/load, offscreen startup (exit 0), compileall and pip check (clean).
Result: comment1/2/3 yielded layout scores .973/.879/.953 and automatic TTS text lengths 170/154/483 respectively; all three were auto-accepted by the heuristic. Header/footer removed and long-post title/final paragraph retained, with remaining OCR spelling errors documented. Screenshot inspected: cache/preview/iteration3-extraction.png. Structured save/load artifact: cache/temp/iteration3-check.json. No actual TTS API or FFmpeg rendering was tested.

## Next Recommended Step

1. Restart run.bat; Read Image or Auto Generate Text should fill detected body and narration without selection. Test with real cumulative Thread screenshots; use Advanced/manual correction if flagged.
2. Integrate ElevenLabs with empty/review safeguards, manual-TTS protection, voice selection and cache; supply credentials through environment only.
3. Add ffprobe measured durations, then background/music/watermark and FFmpeg export. Broaden real-layout fixtures before claiming general extraction reliability.

## 2026-09-08 ? cmt4/cmt5 captions and spelling review
Implemented PSM 3 mixed-media recognition, border-based polarity, OCR cache bump, short-caption/header anchoring, avatar/counter filtering, and a reviewable local spelling dialog. Added core/spelling.py and tests/test_spelling.py; updated OCR settings/runner, ThreadsExtractor and CommentEditor.
Verification: 65 unittest tests passed, including actual supplied cmt4/cmt5 extraction (two caption lines each, no username/carousel counter), source SHA-256 unchanged, contextual spelling suggestions and dialog Save/Cancel. PySide app --smoke-test passed with QT_QPA_PLATFORM=offscreen. No visible native GUI session was tested. OCR models/dependencies unchanged. cmt5 still has accent errors (e.g. Minh/sap); phrase suggestions address some only. General spelling correction, all attachment layouts, voice and export remain incomplete. Additional cmt6 was inspected and still retains an icon-only footer; not claimed fully supported.

## 2026-09-08 — Alternative PaddleOCR provider

Implementation: added `services/ocr/paddle_ocr.py`, `service.py`, and `compare.py`; OCRJob now depends on OCRProvider; OCRController uses OCRService. Runtime settings default to Paddle with optional Tesseract fallback. Main application closes the persistent provider on exit. No ThreadsExtractor changes in this phase. Added eight provider/mapping tests in tests/test_paddle_ocr.py. Updated requirements, README, architecture, product spec and ADR-015.

Dependencies installed successfully in the existing Windows AMD64 Python 3.13.1 .venv: PaddleOCR 3.7.0, PaddlePaddle 3.3.1 CPU, PaddleX 3.7.2. `pip check` reports no broken requirements. Initial sandbox install stalled; authorized installation outside sandbox completed. Model files downloaded to cache/ocr/paddlex. Initial import needed permission to create PaddlePaddle's separate Windows-profile dataset cache. Default MKL-DNN inference raised NotImplementedError; disabling it resolved inference. No installed library files or system HOME/USERPROFILE variables were changed.

Real integration: BOTH cmt4.png and cmt5.png completed with Paddle and Tesseract; no fallback in the comparison command. Paddle process ID 11876 was reused for both images. Source SHA-256 hashes unchanged. Paddle took 38.33/31.65 seconds (first includes initialization); Tesseract read cached results, so this is not a speed benchmark. cmt4: Tesseract 25 word blocks, mean .841; Paddle 9 detected spans, mean .910. cmt5: Tesseract 24 word blocks, mean .902; Paddle 7 spans, mean .956. Full raw text and final extracted bodies are preserved in [OCR_COMPARISON.md](OCR_COMPARISON.md) and cache/ocr/comparison.json.

Quality limitation: Paddle dropped Vietnamese accented letters on these samples despite high confidence. cmt4 also retains a joined image counter and drawing symbols after extraction. Tesseract was more accurate on these two samples; do not claim an accuracy improvement or silently fallback on this basis. Paddle is usable as an experimental selectable provider, not a verified quality upgrade. No disk Paddle result cache or OCR dropdown was added; runtime config suffices for the current read-only settings UI.

Validation: 73 unittest tests passed, covering mapping, empty/invalid output, confidence, process reuse, native-error/timeout cleanup, cancellation, selection, fallback/no-fallback, existing real Tesseract tests and Qt manual-edit protection. Offscreen app --smoke-test and compileall passed. A visible native Windows GUI was not tested.

Additional UI integration passed: actual Paddle OCR of cmt5 through OCRController/Worker in a PySide offscreen window, OCR status done, nonempty detected body/TTS, no fallback. Screenshot inspected at cache/preview/paddle-ui.png. Provider shutdown completed cleanly. Implementation and current-environment integration are complete; quality improvements remain open tasks.

## 2026-09-08 — OCR engine dropdown
Added PaddleOCR/Tesseract selection at the top of the right settings panel. The controller changes the service's next-request engine while idle, preserving provider/model instances and manual text. Selection survives editor/project refresh within the session; restart uses config defaults. No model initialization or OCR runs on dropdown changes. The control is disabled during OCR. Updated README, architecture and product behavior.
Validation: 74 tests pass, including an offscreen UI test switching both directions and checking calls to the selected mocked engine, automatic body updates, busy-state disabling, retained provider instance and manual text preservation. App --smoke-test passed offscreen. No new native-model benchmark or visible GUI session was run for this UI-only change.

## 2026-09-10 - Tesseract primary; narration/cache/timing phase
Tesseract is the startup default; Paddle remains selectable. Added runtime ElevenLabs settings (.env/environment), Flash v2.5 speech adapter, paginated voice listing/manual voice ID, speed selection, selected-item Generate Voice, Open generated audio and Cancel Voice. Added measured MP3 cache with atomic publication, reviewed/empty-text safeguards, manual-text protection and voice/text/speed invalidation. ProjectManager applies measured audio and calculates timeline only when every item has valid audio. The UI prevents OCR/TTS overlap and closes after cancelling active jobs.
Verification: 87 unittest tests pass, including HTTP mock request/response mapping, sanitized 401/403/404/422/429/500 errors, empty/non-audio/network failures, voice pagination, cache reuse/invalidation/partial cleanup, missing ffprobe, cancellation, timeline invalidation and GUI success/error/cancel flows. Actual FFmpeg 9.0.1 encoded a generated two-second WAV fixture to MP3; actual ffprobe measured WAV and MP3 through TTSService with mock HTTP and rejected corrupt cached audio. No external ElevenLabs request was sent. App startup tested offscreen; pip check clean. No visible native GUI or listening test.
Tools: Installed project-local FFmpeg/ffprobe 9.0.1 Gyan essentials binaries, validated against published SHA-256 fec81ae03971d9dd4be3ebe02e263bd2ec1d789483f931bdba5f5715e65da2e9. FFprobe executable ran successfully. No system PATH changes. Documentation/setup are in tools/ffmpeg/README.md.
Status: Implementation and local/mock validation complete for selected-item narration. LIVE ELEVENLABS INTEGRATION UNVERIFIED: requires a user-configured account API key and accessible voice; no speech quality/credit/billing claims. Video export, composed preview, batch voice generation and playback synchronization remain deferred. Earlier entries about missing ffprobe and placeholder-only TTS describe the previous phase.
Next: User configures .env, selects an ElevenLabs voice, reviews TTS Text and generates one narration; then continuous gameplay/music/watermark and FFmpeg video export.


## 2026-09-10 - ElevenLabs HTTP 402 guidance
User reports generation with another voice returning HTTP 402. Added safe payment/voice-access guidance instead of the generic code, without claiming the account is out of credits or a particular voice is paid-only. Existing HTTP error regression now covers 402, redaction and no retries. All 10 TTS tests and offscreen app smoke launch pass. No live API call or account inspection performed.


## 2026-09-10 - Dynamic voice selection and access feedback
Implemented VoiceInfo metadata parsing, paginated list/details API, atomic metadata cache with stale-list fallback, name/search/status UI, Refresh Voices, short explicit Test Voice, Advanced manual ID/model/forced regeneration, project default and per-item inheritance/override persistence. Metadata starts unknown; fresh synthesis confirms access for this session/model only. Cached audio never grants available status. Friendly typed 401/402/403/429/network errors persist in the panel without exposing API keys. Voice/speed/default/model edits retain the old recording for playback but mark it stale; failed forced regeneration keeps valid prior audio and timing.
Validation: 98 tests pass, including HTTP mocks, metadata/cache parsing and write failures, pagination, error/redaction/no-retry checks, explicit short sample, forced-regeneration rollback, old-project loading/default/override serialization, UI search/default/refresh failure, persistent restriction status and test isolation. Offscreen app smoke launch passed. Inspected offscreen window screenshot at cache/preview/voice-selection-ui.png; visible Windows desktop acceptance not performed. Existing real local OCR/audio fixture tests also pass. No live ElevenLabs request sent: integration test not performed. User previously reported successful audio generation and a 402 for another voice; that is user feedback, not agent-run integration validation.


## 2026-09-10 - Unused audio cleanup
Added Tools > audio cleanup, background preview/delete, preserved current unsaved/saved/shared references, external project registration on UI Save/Open and manual external additions. Only unreferenced generated MP3 cache files qualify; invalid/missing projects block deletion, changed/locked files are skipped. No automatic deletion or API requests. User confirmed project files are kept under projects/.
Validation: 107 tests passed, including 7 service cleanup tests and 2 offscreen UI tests. Actual deletion was exercised only on temporary test fixtures: saved/shared/unsaved media, malformed/missing registry/project, newly referenced/modified files, outside-cache paths, permission failures, preview-before-delete and active voice-job guard. App smoke launch passed offscreen. User's real audio files were not deleted during development; use the in-app preview with the live current project. Visible desktop acceptance remains pending.


## 2026-09-14 - Gameplay/music/watermark and MP4 export
Implemented local file controls for gameplay/music/font, volume/loop/random start/fades, watermark text/size/opacity/margin, screenshot width/Y and narration padding/gap. EXPORT now renders existing narration and images over continuous gameplay with optional music and watermark, using cancellable FFmpeg in a worker. Actual audio is re-probed; output publication is atomic and guarded. Tesseract/TTS/manual text/cleanup behavior is retained. Static PREVIEW does not play the composed video.
Validation: 113 tests pass, including five real FFmpeg renderer tests and an added offscreen export/settings test. Integration checks verify H.264/AAC, dimensions/duration, re-probed timing, image switches, silent default gameplay, looped footage, music/watermark encode, Thread progression, pixel comparison confirming gameplay continues through replies, preflight/stale input errors, active-process cancellation and prior-output preservation. App smoke launch and compileall pass. A 1080x1920 real test export (1.566667 seconds, 282159 bytes) is at output/export-validation-20260914.mp4; frame at cache/preview/export-validation-frame.png was visually inspected. This uses synthetic media/tones, not a claim of human listening acceptance or full-length production quality. No live ElevenLabs request was sent. Large-project scalability and visible desktop acceptance remain pending.
Next: User chooses gameplay, prepares current audio for every comment, optionally enables music, then exports MP4. Later: composed preview/missing-media recovery and broader real-project acceptance.

## 2026-09-14 - Browse start folders
Media Browse now opens assets/backgrounds, assets/music or assets/fonts when no current path is available; otherwise it opens the existing selected file parent directory. Removes empty dialog start directory that could inherit the previous screenshot input folder. Verified all three defaults, selected-parent and cancel behavior using mocked dialogs; 22 UI tests and offscreen startup pass. Native dialog acceptance remains untested.

## Visual editor migration plan (2026-09-14)
A: Resizable dark editor shell, scene cards, tabbed inspector/project settings.
B: Persisted EditorObject contract and QGraphics canvas with comment/watermark movement.
C: Aspect-preserving handles, inspector/layers binding, visibility/lock/z-order and undo.
D: Separate multi-track timeline with ruler/playhead/zoom using measured timings.
E: Scrub/selection/persistence synchronization; AUTO timings stay non-draggable.
F: Renderer reads the same logical transforms; real render regression and final documentation.
Each phase gets relevant tests, offscreen app startup, dated progress and a separate local commit. No live TTS calls or automatic GitHub push. Realtime gameplay playback, trim/split/manual clip timing and keyframes remain future scope.

- [x] Phase A: resizable dark shell, scene thumbnails/filter, inspector/layers hosts and compact Project sections. Validation: 22 UI tests pass; offscreen app smoke exits 0. Functional object bindings follow in B/C.

- [x] Phase B: additive EditorObject schema, legacy defaults, 1080x1920 QGraphicsScene, selectable/movable cached comment and watermark. Model mutation tested independently of viewport size. 26 editor/UI tests pass; offscreen startup exits 0. Background currently an explicitly labelled export-only placeholder.

- [x] Phase C: four proportional resize handles, minimum size, snap guides/safe area, transform/style binding, layer visibility/lock/z-order, overlay deletion tombstones and QUndoStack. Background geometry stays locked; deleting an overlay preserves narration. 29 editor/UI tests pass; offscreen startup exits 0.
