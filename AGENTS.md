# Project

Threads Video Studio: a local Windows desktop application for vertical gameplay videos with screenshot comments and timed narration. Build iteratively; correctness comes before visual polish.

## Mandatory Reading Before Coding

Read this file, README.md, docs/PRODUCT_SPEC.md, docs/ARCHITECTURE.md, docs/PROGRESS.md, docs/TODO.md and docs/DECISIONS.md before large changes. Documentation must carry context across sessions.

## Mandatory Actions After Coding

- Run relevant tests and launch the app/render when applicable. After each phase update PROGRESS.md and TODO.md, retaining checked tasks as history.
- Update DECISIONS.md for architectural choices or deviations from the specified folder structure; update PRODUCT_SPEC.md for behavior changes.
- Never mark untested features complete. Explain missing dependencies, untested paths, limitations and blockers explicitly.

## Core Architecture Rules

- Keep modules focused: core/config, models, persistence, cleaner, timeline; services/OCR and TTS; renderer; UI; utilities.
- UI must not implement OCR, TTS, cleaning rules, timeline calculations or FFmpeg business logic.
- OCR providers must not contain platform-specific extraction logic. Platform-specific comment parsing belongs in services/content_extractor.
- Keep the text pipeline OCRResult/bounding boxes → ContentExtractor → body/new reply → TextCleaner → TTS Text. Raw OCR is Advanced/debug data, not the normal narration source.
- Preserve manual body and TTS flags. Only explicit Re-run extraction replaces a manual body; it must still preserve manual TTS. Ambiguous thread overlap must never fall back to narrating the entire question again.
- Use Python/PySide6 locally on Windows and FFmpeg for final rendering. Never render every frame in Python unnecessarily.
- No unnecessary rewrites, premature optimization, unexplained dependencies or monolithic files.
- Centralize defaults; never hard-code absolute paths or API keys. Use .env/environment for secrets; never commit or log secrets.
- Run OCR/TTS/API/FFmpeg and other long operations outside the UI thread. Report status, progress, errors and completion.
- Invoke subprocesses using argument lists, not shell strings. Handle Windows paths, capture FFmpeg stderr and log sanitized commands at DEBUG.
- Use cache/tts, cache/ocr, cache/preview and cache/temp with collision-resistant filenames; invalidate narration when its text/voice changes.
- Handle missing tools/media, invalid images/JSON, permissions, API/OCR/render failures visibly; no silent crashes.

## Product Rules

- Support Single and multi-reply Thread/Q&A scenes. Progressive mode switches user-supplied cumulative screenshots, without pixel stitching; narrate only the newly added reply.
- Keep original screenshots unchanged. OCR/display text and TTS text are separate; user-edited TTS must survive Auto Generate.
- Rule-based cleaner removes emoticons such as =))) and =(( by default, preserves Vietnamese accents and meaningful content, and favors keeping uncertain symbols.
- Audio measured by ffprobe is the source of timeline durations. Padding and gaps are configurable.
- Gameplay fills 9:16 without distortion, loops if needed, remains continuous across items/scenes, and is muted by default.
- Preserve screenshot aspect ratio and content; configurable width/Y. Support quiet music and configurable watermark.
- Prepare data models for meme, SFX, subtitles, presets and batch rendering; do not claim deferred features work.
- Do not render a full video on every small edit. Accurate final export takes priority over advanced preview.

## Development Priority

Runnable code, correct data model, Single/Thread behavior, timeline, render, TTS, usable OCR, usable UI, preview polish, then advanced meme/SFX. Implement V1 in phases: foundation; UI/import; OCR/cleaner; TTS/cache; timeline; media/settings; renderer; preview/persistence; verification/docs.

## Documentation and Truthfulness

PRODUCT_SPEC.md defines behavior, ARCHITECTURE.md defines implementation, PROGRESS.md records actual state, TODO.md records next tasks, DECISIONS.md records reasons, README.md explains setup. A feature is done only with implementation, relevant passing tests, basic error handling and updated documentation. Clearly distinguish target behavior from current implementation; do not claim OCR, paid APIs, FFmpeg or a visible GUI were tested without actually testing them.
