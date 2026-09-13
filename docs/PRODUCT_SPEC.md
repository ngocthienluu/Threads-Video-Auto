# Product specification

## Goal and workflow

Local Windows desktop tool for creators making TikTok/YouTube Shorts from comment screenshots over continuous gameplay. Target: Import → Auto Generate → review OCR/TTS → optional meme/SFX → Preview → Export. Prioritize correct timing and narration over editor polish.

## Current iteration boundary

As of 2026-09-10: Tesseract is the default; Paddle remains selectable. Selected-item ElevenLabs narration, voice ID/list selection, speed 0.7–1.2, measured audio cache and timeline application are implemented. Generate Voice explicitly sends TTS Text to ElevenLabs; OCR/import/Auto Generate Text never trigger paid speech generation. Empty or unreviewed uncertain automatic text is rejected; manually edited TTS provides reviewed narration. Manual text stays protected. Open generated audio delegates playback to the OS. Export/composed preview remain deferred. Real API generation/voice quality is unverified; HTTP mocks and actual ffprobe fixtures pass. The iteration-3 description below records the earlier OCR phase.

Iteration 3 adds automatic Threads Content Extraction and progressive new-reply detection. Normal workflow: Import → Read Image → Detected Comment and TTS Text filled automatically. AUTO GENERATE TEXT processes all items in scene order; it stops at prepared text because actual voice generation and video export remain unavailable. Rendering settings remain read-only placeholders; no narration duration is fabricated.

Read Image reads the selected item and any preceding items in its scene, so selecting a reply first still provides its cumulative context. Detection uses normalized ROI priors, word/line bounding boxes, relative alignment and spacing, short timestamp/date headers, and separated footer labels/counts. Regions adapt to anchored body length and do not discard the last paragraphs solely because they extend past the default ROI. Numbers/prices inside body lines remain. No fixed username, fixed line count, LLM or trained detector is used.

OCR runs locally in an isolated process coordinated by a sequential Qt job queue. Editor/project actions are disabled while running; status, milestone progress and Cancel OCR remain available. Cancellation/timeout kills the child process; closing cancels before unsaved-change handling. Completed batch results remain on cancellation; dependent automatic thread text is recalculated, while manual edits remain protected. OCR failures preserve the failed item's text, mark OCR error and prevent downstream uncertain overlap from repeating old content. No image is uploaded. Model downloads remain an explicit setup step. OCR cache now stores geometry; previous text-only cache entries are bypassed by a pipeline version change.

## Threads Content Extraction and review

OCRBlock stores text, source-coordinate x/y/width/height, confidence, level and line_id. OCRResult stores full_text, blocks and oriented source dimensions. ContentExtractor returns raw_text, body_text, confidence, method, warnings and debug_info. The provider reads text/geometry only; ThreadsExtractor owns platform-specific header/footer and body-region rules. TextCleaner remains responsible for emoticons/emoji/URLs, not Threads layout.

Detected Comment is editable and shows the cumulative body for a Thread reply; TTS Text uses only new_body_text. Raw OCR is read-only and hidden under Advanced by default. Advanced also shows warnings/method, a manual selection fallback, and Re-run extraction. Editing Detected Comment marks body_text_is_manual and refreshes automatic TTS; editing TTS marks tts_text_is_manual. Subsequent Read Image/Auto Generate preserve both flags, including intentionally empty fields. Re-run extraction explicitly replaces only the selected item's manual body using stored geometry when available; manual TTS still survives. The Advanced Clean/Selection overwrite checkbox is the separate explicit permission to replace manual TTS.

For progressive threads, full_body_text retains each cumulative state. A token-prefix search with difflib.SequenceMatcher and Unicode accent normalization compares the previous cumulative body against current prefixes. Output retains the current OCR spelling. Exact or sufficiently similar overlap produces only the suffix as new_body_text; multiple replies use the immediately previous cumulative state. Missing, unrelated, too-short ambiguous or unchanged context yields empty automatic reply narration and Needs review, never a full-question fallback. Reordering/deleting/editing previous bodies recomputes dependent automatic text and invalidates audio if narration changes.

Confidence is a heuristic, not a calibrated spelling probability: weighted OCR confidence (55%), header support (20%), alphabetic content (15%) and ROI alignment (10%), with caps for missing anchors, tiny content and poor recognition. Thread confidence is additionally limited by fuzzy-overlap confidence. Defaults: >=.80 Comment detected; .60–.79 detected with a warning; <.60 Needs review. Empty body/new reply always requires review. Single extraction failure exposes raw text as a low-confidence fallback and cleans it into draft TTS with a visible warning; a reply fallback is still subject to overlap safety. No voice is generated from an empty string; Generate Voice remains disabled in this iteration.

ExtractionSettings in config.py centralizes the normalized body prior (.07/.14/.97/.72), score thresholds/weights, diff threshold .84, raw-view default and optional debug crops (off by default). The ROI is a prior applied to position data after a layout scan, not a destructive fixed crop of every screenshot. Cropping before knowing the layout would remove long bodies or shifted cards; optional body-region crops are debug artifacts only. Screenshot pixels remain unchanged. Old JSON opens with defaults for missing fields; legacy manual OCR becomes a protected manual body, and prior TTS flags/text are preserved.

## Scenes and text

A project contains ordered scenes. Single has exactly one item. Thread has a Question and zero or more Replies while being authored; a finished Q&A should contain at least one reply. Progressive mode uses user-supplied cumulative screenshots: question, question+reply1, question+reply1+reply2. Switch screenshot when the previous item's segment ends; the new voice reads only the new reply. Do not stitch pixels. Keep gameplay continuous. Replace and Show Complete Immediately are future modes.

Each item stores the original-image reference, raw OCR and position data, detected body/full_body/new_body, extraction confidence/method/warnings/debug data, independent manual body/TTS flags, narration fields, timestamps and optional meme/SFX. Display text mirrors the detected/edited body; original screenshots remain untouched. Legacy string-only OCR APIs remain available for compatibility, but normal UI generation uses structured detection. Manual narration survives regeneration; narration changes invalidate audio/timing.

Cleaner defaults: remove emoticons (=))), =((, :), T_T, ^^ and similar); optional URL removal; optional known-username removal; emoji mode ignore/keep/meaning (meaning is reserved, rejected in iteration 1). Preserve Vietnamese diacritics, meaningful punctuation and uncertain symbols. Username removal requires explicit username metadata; never guess which prose is a username.

## Output and media (target V1)

- MP4, H.264/AAC, 1080×1920, 30 fps, 9:16.
- One continuous background stream, scale/crop to fill without distortion; specific/random library file, valid random offset, loop if short; source audio muted by default.
- Screenshot keeps aspect ratio and all content, centered horizontally; max width .88 of video, configurable Y .42. Very tall images fit the available height. Keep a consistent top anchor for progressive screenshots where practical.
- Music specific/random selection, random offset, looping, low volume .08, fade in/out; voice stays dominant.
- Watermark enabled, `@CongDongThreads`, top-center; configurable font, size, opacity, X/Y.

## OCR / TTS / timeline (target V1)

OCR provider returns editable text, with pending/done/error status. TTS provider supports voice selection, regeneration and speed if supported. ElevenLabs credentials from environment/.env; individual collision-resistant cached audio files. Probe actual audio with ffprobe. Timeline walks scenes/items in order: pre-padding .10s + audio duration + post-padding .15s; scene gap .05s only between scenes. Missing or stale audio prevents a ready timeline/export. Half-open intervals prevent overlap. Screenshot stays visible for item padding; scene gaps belong to neither item in the foundation, renderer must explicitly define gap visuals later.

Auto Generate validates images, obtains missing OCR, prepares TTS without overwriting manual edits, generates only necessary narration, probes duration, builds timeline, resolves media and prepares preview. Progress/status/errors for all long tasks, outside the UI thread. A review step must resolve ambiguous thread reply extraction before narration is generated.

## UX and persistence

Left: scene tree, import, add Single/Thread/reply, delete and move up/down. Center: portrait preview and editable Detected Comment/TTS; raw OCR is under Advanced. Right: background/music/watermark/video settings, preset placeholder. Bottom: timeline/status. Main actions Import, Auto Generate Text, Preview, Export (voice/export unavailable until later V1 phases). V1 may use static preview; no full render on minor edits. Save/load versioned JSON; preserve IDs, roles, manual flags, settings, assets and extension data. Missing files reported, not silently discarded. Friendly errors for invalid input, tools, credentials, missing assets, render failures and permissions.

## Extensions

Meme: enabled, file, overlay/fullscreen_replace, start mode seconds/percentage/end_of_voice, value, duration, volume. SFX: enabled, file, start mode/value, offset and volume. Iteration 1 persists optional configs only. V2 adds rendering these, timeline editing, transitions, presets, drag reorder and better preview. V3 adds suggestions, subtitles, batch generation, templates and automation.

## Caption extraction and spelling review update
Current: automatic page segmentation handles comments containing large meme attachments. Header anchoring supports a missing timestamp with a punctuated handle on the first line. Small inline image counters and compact engagement counters are filtered using layout context. The spelling dialog proposes a limited set of contextual Vietnamese corrections, allows editing before Save, and changes detected body only upon acceptance. Raw OCR and manual TTS stay unchanged; accepted body is marked manual. Names/slang are not globally normalized. Full automatic spelling/grammar correction remains deferred.

## Alternative OCR selection
The right panel includes an OCR Engine dropdown (PaddleOCR/Tesseract). Switching changes the next Read Image/Auto Generate Text request without running OCR or modifying existing/manual text. Selection is disabled during OCR and lasts for the current app session; restarting uses the configured default. Re-run extraction continues to reuse saved OCR.

Runtime config selects Tesseract (default) or PaddleOCR (Vietnamese). Optional Tesseract fallback remains available for technical Paddle errors; cancel, empty text and low confidence never trigger fallback. Fallback is disclosed in Advanced warnings and batch completion status. Both providers feed the same OCRResult, ThreadsExtractor, body/new-reply, TextCleaner and TTS-text pipeline.


### ElevenLabs payment errors
HTTP 402 shows guidance to check subscription, balance and API access for the selected voice, or choose an accessible voice. Listing a voice does not guarantee synthesis access. No automatic retry or voice substitution is performed.


## Dynamic voice selection (2026-09-10)
Voice UI shows ElevenLabs, configured/not-configured key status, searchable voice names, Project Default and Use Default per item. Search matches supplied name/language/accent metadata. Advanced contains manual Voice ID, effective ID and editable model; unknown IDs display a neutral label, not fabricated names. Set selected as project default updates inheriting items; explicit item overrides remain unchanged. Save/Open persist selections and model, never the key. Old projects use runtime environment defaults until configured/generated.

Refresh Voices runs in a worker. Startup reads only local metadata cache; refresh failure keeps the previous list and a persistent warning. Listing a voice is not proof of speech permission. Unknown is the initial status; only a successful fresh synthesis in this session/model confirms Available. Test Voice sends the short fixed sample "Xin chào" with an explicit click, may use credits, and never replaces comment text/audio. No automatic tests, scans, voice substitutions or retries. Availability resets on restart/model change; no cached audio is treated as access proof.

Generate Voice retains existing audio-cache reuse. Advanced > Regenerate Voice (new API request) explicitly bypasses the audio cache, using the current text, speed, effective voice and model. Failure leaves a still-valid old recording intact. Changing voice/speed/default/model marks affected narration/timeline stale while keeping the old audio playable; it is clearly labelled previous recording and excluded from timing. Text changes retain the existing invalidation behavior.

Errors 401/402/403/429 and connection failures have safe explanatory messages, specific dialog titles and persistent feedback. 429 may mean rate/quota limits; the app does not promise waiting will fix depleted credits. Restrictions are recorded for the selected voice, and never trigger another automatic request. Preview URL metadata is retained if supplied; playback of provider preview URLs is not implemented.


## Unused audio cleanup (2026-09-10)
Tools > audio cleanup previews file count/size and requires the explicit Delete action. No automatic deletion on startup/exit. The user's primary project location is projects/. Preserve references from the unsaved current project, all JSON projects recursively in projects/, the current on-disk project and remembered Save/Open paths. The dialog accepts additional external project files. Any unreadable/invalid/missing known project blocks deletion. Shared audio and previous recordings still referenced by items remain protected, regardless of done/pending status. Other media references (music/SFX) are protected too.
Only direct, hash-named MP3 files in cache/tts are candidates. Original media, OCR, voice-list metadata, partial temporary files and directories are excluded. Re-scan references and compare file identity/size/mtime before deleting reviewed candidates. Changed/referenced/locked files are skipped with a count. No network calls. Removing unused paid audio may require credits to recreate it later. Cleanup frees disk space, not substantial runtime RAM.


## Current export phase (2026-09-14)
EXPORT now creates MP4 H.264/AAC from existing, non-stale narration for every item. It does not run OCR/TTS or spend API credits. Gameplay is center-cropped without stretching to 9:16, runs continuously across Single and Thread items, optionally starts at a random offset and loops when enabled. Muted by default; a nonzero gameplay volume requires an audio stream. If looping is disabled, footage must be long enough. Optional music supports volume, looping/random start and fades. Optional watermark supports text, font, size, opacity and top margin in UI; bottom-center/custom positions remain configurable in project JSON.
Images retain their full aspect ratio/content, fit within configured width and 90% frame height, and switch at timeline boundaries. Image center Y is configurable and clamped so the whole image remains visible. Scene gaps show gameplay only; no pixel stitching. Export re-probes actual audio durations on a snapshot, preserving project/manual narration. Timing controls adjust pre/post padding and scene gap. Settings are saved in the existing project settings fields.
Export shows progress and Cancel Export, disables editing/OCR/TTS/cleanup while active and cancels before close. Encoding uses a temporary MP4; success is checked for streams, duration and dimensions before atomic replacement. Existing output is kept on failure/cancel. PREVIEW is still a static screenshot placement preview, not a composed player. Enabled meme/SFX/transitions are rejected visibly rather than ignored; subtitles/batch voice/richer preview remain deferred.

Media Browse starts in assets/backgrounds for gameplay, assets/music for music and assets/fonts for fonts. If a current absolute path has an existing parent folder, that parent takes priority. Cancelling keeps the selection unchanged.
