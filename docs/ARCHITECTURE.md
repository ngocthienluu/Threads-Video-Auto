# Architecture

## Narration phase (2026-09-10)

TTSSettings reads a small whitelist from .env/environment at startup (environment wins); key is runtime-only and excluded from repr/project JSON. HTTPX 0.28.1 is now an explicit dependency. ElevenLabsTTS maps the official speech/voice-list endpoints, uses Flash v2.5 for Vietnamese, streams bounded MP3 responses and translates HTTP/network errors without exposing response bodies or credentials. No automatic retries. TTSProvider adds optional cancellation to its interface.

TTSService validates nonempty/reviewed text and voice, checks ffprobe before network synthesis, hashes text/voice/speed/model/format for audio cache identity, writes via unique temporary files and only publishes after actual ffprobe validation. Cached files are re-probed. Corrupt cache reports an error rather than silently purchasing another generation. Cancel checks occur before/after requests and between streamed chunks; a blocked HTTP read may wait up to the 20-second timeout. No refund/cancellation of a remote generation is implied. Total streaming limit is 120 seconds; audio size limit is 30 MB.

TTSController owns selected-item worker lifecycle and snapshots; GUI writes results only when project/item and text/voice/speed still match. OCR and TTS cannot run simultaneously through the UI. Closing cancels and waits asynchronously. Voice selection/speed edits go through ProjectManager and invalidate stale audio. Applying measured narration recomputes the existing pure timeline when all files/items are ready; partial projects remain pending. Existing audio_path/duration/status and timing persist in schema 1. Generate Voice never modifies narration text.

utils/audio.py invokes ffprobe with argument lists, captures stderr, enforces process timeout/cancellation and rejects missing/non-audio/invalid-duration input. It uses configured executable/PATH, then project-local tools/ffmpeg/bin/ffprobe.exe for the default setting. Local Gyan 9.0.1 binaries were SHA-256 verified; binaries are ignored, provenance/license retained under tools/ffmpeg. Open generated audio uses the OS default player, not an in-app synchronized preview.

```text
PySide6 views → ProjectManager → dataclass Project / Scene / SceneItem
                    ├→ text_cleaner (pure rules)
                    ├→ JSON persistence (atomic replace)
                    └→ timeline (pure duration calculation)
OCRController queue → Worker/OCRJob → OCRService → selected provider
     ├→ PaddleOCRProvider → persistent isolated Python/PaddleOCR
     └→ LocalOCR → isolated Python/Tesseract (optional technical-error fallback)
     → OCRResult / word boxes → ThreadsExtractor → ExtractionResult
     → queued GUI result → ProjectManager / content_pipeline
     → cumulative body → fuzzy thread prefix diff → new_body_text
     → TextCleaner → automatic TTS Text (manual flags protected)
TTSController → Worker → TTSService → ElevenLabs provider / audio cache → ffprobe
     → queued result → ProjectManager → duration-driven timeline
RenderController -> Worker -> FFmpegRenderer -> shared EditorObject geometry -> MP4
```

## Responsibilities

`core/config.py` owns project defaults, including persisted ExtractionSettings. `core/ocr_models.py` owns provider-neutral geometry types; `core/models.py` adds detected-body/diff/manual/review fields and additive legacy loading. `core/content_pipeline.py` applies results and recomputes narration through scene order; ProjectManager exposes these use cases to UI. `services/content_extractor/base.py` defines ContentExtractor/ExtractionResult; threads_extractor.py groups/filters positioned lines using platform layout; thread_diff.py performs standard-library fuzzy prefix matching. OCR providers contain no Threads parsing. OCR settings/setup remain runtime configuration. TTS has an HTTP provider and measured cache; renderer performs local FFmpeg composition. Core has no Qt dependency.

## Model and persistence

Project contains UUID, name, ISO UTC timestamps, schema_version=1, typed video/background/music/watermark/cleaner/timing settings and ordered scenes. Scene contains type, progressive display mode, transition and items. Item contains role, image reference, OCR/display/TTS strings, manual flag, narration fields, statuses and optional meme/SFX settings. IDs are stable; roles follow scene order. No audio duration guessing.

Serialization uses UTF-8 JSON and rejects malformed schema, invalid enums/types and unsupported versions. Save to sibling temporary file then os.replace to avoid truncating the last good project on failure. Media paths are relative to the JSON directory where possible, absolute across Windows drives; resolution uses the JSON directory, never current working directory. Missing media yields a warning with the project still editable. Imports reference external files and do not copy/change them. JSON never stores credentials. UUIDs and a future hash of provider/text/voice/speed avoid cache collision.

## UI and execution

QMainWindow keeps the three-panel layout; CommentEditor prioritizes Detected Comment/TTS and hides read-only raw OCR and manual-selection tools under Advanced. OCRController dispatches sequential immutable OCRJobs with copied settings, tracks project/item identity and applies results in Qt slots. Read Image includes predecessor items for thread context; Auto Generate Text traverses all scenes. Explicit Re-run extraction may reuse saved OCR geometry. Cancellation remains responsive between and within jobs; closing waits asynchronously before the unsaved guard. Manual body/TTS edits are protected by core rules, not by UI text-selection state. Small import/persistence operations remain synchronous.

## OCR process and cache

LocalOCR snapshots the source into a unique temporary directory under cache/ocr, hashes image bytes plus pipeline/language/PSM/model identity, validates model checksums and uses atomic text-cache writes. A child Python module loads tesserocr and Pillow; native OCR never runs in the GUI process. Popen uses argument arrays, captured stdout/stderr, CREATE_NO_WINDOW on Windows and no shell. Polling communication allows cancellation and a 60-second timeout with process kill/reap. JSON stdout transports text or safe errors, while raw engine stderr and OCR content are not logged. The worker cleans temporary snapshots; original screenshots are unchanged.

Tesseract preprocessing: EXIF orientation, alpha handling, grayscale, border-theme inversion, bounded 2× scaling and border. Tesseract uses LSTM/PSM 3 with vie+eng. ResultIterator's WORD/TEXTLINE levels expose text, confidence, boxes and line boundaries (equivalent to TSV position data). Border/scaling are removed from coordinates to return oriented-source pixels; image dimensions accompany all results. `recognize()` still returns str, while `read_blocks()` returns OCRResult. Cache pipeline bbox-3 stores full geometry; older cached payloads are not reused. Tesseract model/data downloads are unchanged and its runtime OCR remains offline.

ThreadsExtractor first prioritizes the normalized body ROI, then expands candidate regions using header/date anchors, relative body columns, line heights/gaps and footer context. A full positioned layout scan is retained to locate shifted/long/multiple comments and provide raw diagnostics; it does not blindly feed whole-image text to TTS. Numeric tokens are filtered as interaction counts only in separated footer context, never by blanket digit removal. Optional debug body crops are produced by OCRJob, not the provider, and default off. Fuzzy thread diff accent-normalizes only for matching; emitted suffix preserves current text. Uncertain overlap yields empty automatic narration. Single raw-text fallbacks are low-confidence and visibly require review.

Project JSON stays schema_version=1 with additive defaults for new fields. OCRResult is serializable alongside body/full/new text, manual flags, score/method/warnings/debug and needs_review. Missing legacy fields are defaulted; legacy manual OCR is explicitly protected as a manual body. Older application versions may reject the new fields, so backward loading is supported by the new version, not downgrade compatibility.

`app/ui/__init__.py` supplies a font fallback for offscreen Windows only when Qt discovers no families, using WINDIR to locate the installed Segoe UI font. Image decoding/import is synchronous in this iteration; large-batch responsiveness is not yet verified.

## Rendering strategy

FFmpeg gets argument arrays (shell=False), a single looping/cropped background input and time-enabled screenshot overlays, text watermark, delayed voice tracks and looped/faded quiet music. Audio durations from ffprobe define the timeline. Handle filter-expression escaping independently from subprocess path arguments. Capture stderr, debug-log sanitized commands, surface actionable errors and parse progress. Never restart gameplay per scene. The implemented graph and synthetic-media validation are described below.

## Runtime, errors and observability

Runtime directories: cache/{tts,ocr,preview,temp}, logs, projects, output. Paths derive from the repository root (`__file__`), with optional runtime root argument in configuration. Logging uses rotating UTF-8 logs/app.log and standard INFO/WARNING/ERROR/DEBUG; log operation metadata, not keys/text. UI boundary catches expected file/validation errors in dialogs. Startup prints actionable failures and logs exceptions when possible. Tool availability uses PATH discovery; ffprobe validates actual narration/output durations.

## References

[Qt setup](https://doc.qt.io/qtforpython-6/gettingstarted.html) and [QRunnable contract](https://doc.qt.io/qtforpython-6/PySide6/QtCore/QRunnable.html) were consulted for dependency setup and worker design.

## OCR caption/spelling maintenance
OCR runner uses automatic page segmentation (PSM 3), border-theme polarity and cache pipeline bbox-3; engine and traineddata are unchanged. ThreadsExtractor retains platform-specific handle/counter rules. core/spelling.py provides deterministic phrase suggestions independently of widgets. CommentEditor previews them in a modal editor and routes acceptance through the existing body edit signal/ProjectManager, preserving narration invalidation and manual protections.

## Alternative OCR provider

`services/ocr/service.py` selects `paddle` or `tesseract` from runtime `OCRSettings`. Defaults are `ocr_provider="tesseract"`, `ocr_fallback_provider="tesseract"`; an empty fallback disables it. SettingsPanel now emits engine selection to OCRController, which calls OCRService.select_provider while idle. The service replaces the immutable runtime selection without loading/recreating providers. Selection is session-scoped, independent of project JSON. UI knows only OCRService. OCRJob accepts the abstract OCRProvider.

`paddle_ocr.py` lazily spawns one persistent CPU process and initializes PaddleOCR once there. Repeated jobs reuse its engine; cancel, timeout or a technical failure terminates/reaps it, and the next request starts a fresh process. A lock serializes calls. Qt workers poll a Pipe every 100 ms, so model loading/inference never blocks the GUI. The default 300-second limit includes model initialization/download; this can be changed in OCRSettings. Application shutdown closes the process.

The adapter uses PP-OCRv5 with `lang="vi"`, disables document rotation/unwarping and text-line rotation, handles EXIF/alpha on a decoded copy, and returns oriented-source geometry. `rec_texts`, `rec_scores`, `rec_polys` are mapped to rectangles; horizontally aligned detected spans share a line_id. These are actual detected span boxes, not fabricated word boxes. Empty predictions return an empty OCRResult; malformed results raise OCRError. ThreadsExtractor remains unchanged and owns all platform rules.

Models use PaddleX's cache under `cache/ocr/paddlex` by default, overridable with `PADDLE_PDX_CACHE_HOME`. Unlike Tesseract, Paddle currently has no disk result cache; model reuse avoids repeated initialization. First use may download official model files. Local inference receives image arrays, not remote image URLs. Technical failures can fall back; cancellation, empty results and low confidence cannot. Fallback details persist in extraction warnings/Advanced and batch status reports fallback usage. Parent errors go to app.log; child exception type/stack (without OCR text) goes to logs/paddle.log.


## Dynamic ElevenLabs metadata/access flow (2026-09-10)
services/tts/voices.py adds VoiceInfo and VoiceCatalog. ElevenLabsTTS parses GET /v2/voices and GET /v1/voices/{voice_id}; metadata is allowlisted and absent fields stay None/unknown. Tier/resource metadata is not interpreted as proof of synthesis permission. VoiceCatalog owns atomic cache/tts/elevenlabs_voices.json (fetched_at + metadata only, no key/access observations), details delegation and explicit validate_voice_access. Cache loads are bounded to 5 MB. Refresh failures keep the current list; write failures keep freshly fetched results and report a warning. Metadata cache may be stale or from a previous account, so access resets to unknown on restart. Session observations are also reset when the effective model changes.

VoicePanel is a focused view inside CommentEditor: names, search, status, default/manual controls and test/refresh signals; no HTTP logic. TTSController dispatches all network actions using existing Worker, carries structured safe TTSError objects through the result signal, logs only fixed error titles/statuses, and updates controls on the GUI thread. Test Voice calls TTSService.generate(force=True) on a temporary sample item; Generate uses cache and Advanced Regenerate explicitly bypasses it. Sample audio uses the existing measured audio cache but never attaches to the comment. No new dependency or broad provider rewrite.

Project schema 1 gains additive tts_provider/default_voice_id/default_voice_name/tts_model_id fields; empty item voice_id means inherit project default, then runtime fallback. A worker snapshot resolves effective voice/model, while item inheritance remains persisted. New app accepts old JSON with defaults; old app versions may reject additive fields. ProjectManager.set_default_voice/set_tts_model invalidate affected timing. Voice edits now preserve previous path/duration with pending status; timeline requires done, so stale audio is available only for listening. Atomic publication prevents failed forced regeneration from overwriting valid cache files.

References: [List voices](https://elevenlabs.io/docs/api-reference/voices/search), [Get voice](https://elevenlabs.io/docs/api-reference/voices/get).


## Audio cache collection (2026-09-10)
services/tts/cleanup.py owns reference collection, strict saved-project decoding, candidate plans and verified deletion. References resolve against each project JSON directory; live project paths remain protected independently of the saved snapshot. saved_projects.json stores only paths of projects Save/Open-ed through MainWindow, not credentials. The configured projects/ tree is always scanned; externally saved older projects can be added explicitly. Registry failure is surfaced, and malformed/missing/unreadable project inputs block collection rather than guessing that audio is unused.
AudioCleanupDialog runs scan/delete through Worker under a modal dialog, so the current UI cannot generate/edit while collection runs. Entry is blocked during OCR/TTS. It previews sizes/names before a separate Delete click. The service rechecks project references and candidate stat identities on application; deletes only resolved direct 64-hex.mp3 files inside the configured cache, with no recursive delete and no symlink/junction cache traversal. Failed individual deletes are reported as skipped. Closing the dialog waits for the small local operation to finish. No new dependencies/schema fields; MainWindow remembers save/open paths and routes UI signals only.
Limitations: external projects never opened/saved by this version must be explicitly added; other running application instances are not coordinated. Missing remembered paths conservatively block cleanup until those project files are made accessible again. No automatic cleanup policy or purge of OCR/model caches.


## Implemented FFmpeg export (2026-09-14)
renderer/media.py owns local/PATH executable discovery, safe RenderError/RenderCancelled and cancellable ffprobe. FFmpegRenderer deep-copies and validates project inputs, rejects stale narration/unsupported effects/source-output collisions, probes real durations, and builds the existing pure timeline. Screenshot EXIF/alpha/scale normalization and watermark rasterization happen once per input using Pillow; Python does not render video frames. Watermark rasterization avoids injecting arbitrary text or Windows font paths into filter syntax.
filter_builder.py generates numeric-input filters: continuous scaled/cropped gameplay, time-enabled static image overlays, delayed stereo 48kHz narration, optional looped music/fades and optional gameplay sound, unnormalized amix plus limiter, final yuv420p. One FFmpeg process produces libx264/AAC with faststart. Encoder/filter threads are limited to two. FFmpeg 9 uses -/filter_complex to read a generated script; the obsolete -filter_complex_script is not used. Stream/progress capture is via temporary files, avoiding stdout/stderr pipe deadlock. Polling supports cancellation and a one-hour timeout; failure includes captured FFmpeg stderr. Output is staged beside destination and published only after validation.
RenderController owns Worker lifecycle, snapshots, file-save dialog, progress/cancel, editing/menu locks and close-after-cancel. SettingsPanel emits values; MainWindow validates and persists settings without implementing FFmpeg logic. PreviewWidget now edits persisted logical object geometry and previews timeline visibility; media playback remains deferred. Export reads existing media only; no ElevenLabs request or media upload. Default local binaries are tools/ffmpeg/bin; environment FFMPEG_PATH/FFPROBE_PATH may override them. FFmpeg 9.0.1 Windows x64 is integration-tested; other versions and large projects are not yet validated.
References: https://ffmpeg.org/ffmpeg.html and https://ffmpeg.org/ffmpeg-filters.html .

## Visual editor architecture (2026-09-14)

`core/editor_objects.py` defines a Qt-independent EditorObject and ObjectType enum. Project schema 1 gains additive editor_objects and snap/safe-area settings. Stable object IDs link comment objects to SceneItem IDs, avoiding duplicated media paths. Validation rejects nonfinite/invalid geometry, duplicate global/link IDs and unsupported background geometry. `core/editor_scene.py` creates defaults, migrates after relative paths resolve, prunes deleted-scene links and derives AUTO times. Existing transforms are never regenerated because the default screenshot ratio changes. ProjectManager saves these objects atomically with all other state; deleted overlays remain tombstones. The new reader accepts old JSON, not vice versa.

`ui/preview_widget.py` is a QGraphicsView/QGraphicsScene with logical sceneRect (0,0,1080,1920). CanvasObject owns a reference to the persisted model, with selectable/movable geometry flags. Four child handles use pure `core/editor_geometry.py` proportional/opposite-anchor math, including rotated objects and minimum/maximum dimensions. Positions are written to the model as drag events happen. Per-object pixmaps are cached; drag does not read disk or invoke FFmpeg. Stale font/content cache entries and removed objects are pruned. A locked placeholder represents gameplay until a playback backend exists.

`ui/editor_controller.py` coordinates scene/canvas/layer selection, model edits, ObjectInspector and QUndoStack. Commands retain only changed object fields; timings remain derived. Live gestures update the inspector and dirty state, then create one undo command on release. Project replacement clears the stack/cache. Layer checkbox updates preserve the emitting QTreeWidgetItem to avoid deleting an object inside Qt itemChanged callbacks. Project settings retain content/media configuration; duplicate watermark geometry controls were removed. No OCR/TTS/FFmpeg business rules moved into the UI.

`core/editor_timeline.py` defines immutable TimelineClip records, TimingMode and pixels-per-second conversion. `ui/timeline/` contains the track view, scene, clip painting, ruler, zoom and playhead input. Clip records derive from the existing pure measured timeline; no manual clip timing is enabled. Rebuilds occur only when clip/timing data or zoom changes, not on every object drag. Scrubbing gates object visibility by start <= time < end and synchronizes scene selection without recursively seeking. Without complete current audio the canvas uses explicit selected-item authoring mode and the timeline remains empty/pending.

`renderer/editor_compositor.py` scales static assets once to output resolution from logical dimensions, applies opacity and clockwise center rotation, and supplies numbered RenderOverlay records. Shared `editor_scene.object_image` supplies both Qt and renderer pixels (including identical watermark font rasterization). FFmpeg overlays these assets sorted by z_index at the model X/Y and AUTO times. Guides never enter the renderer. Background crop/loop and all narration/music mixing retain the existing single continuous graph. FFmpeg re-probes audio on its snapshot and refreshes object timing; it never mutates the live project. Pixel comparison tests cover moved/rotated/transparent comments, watermark, hidden/deleted overlays and layer order.

Limits: synchronized gameplay/audio preview, MANUAL timing and additional visual object creation/rendering are future work. Source image decoding/import remains synchronous; large-batch latency and long-project memory still need benchmarking. No new dependency was introduced.

## Acceptance fixes (2026-09-14)
SettingsPanel uses a QComboBox selector with QStackedWidget pages instead of QToolBox headers that clipped under font scaling. SceneItem.reply_body_only is additive/persisted and opt-in; content_pipeline skips prefix subtraction only for explicitly confirmed standalone replies, preserving manual TTS and default cumulative protection. FFmpeg inputs have finite measured lifetimes; encode tracks advancing frame/time/byte markers even without a progress callback, logs a stall and kills/reaps the process after 120 seconds without advancement. RenderController distinguishes encoding from output validation at 99%.
