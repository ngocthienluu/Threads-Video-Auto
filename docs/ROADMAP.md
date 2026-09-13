# Roadmap

## V1

0. Foundation: structure, agent rules, docs, requirements, config, models, logging, project manager.
1. UI shell, import, Single/Thread, ordered replies, manual fields.
2. OCR provider integration, review workflow, cleaner and protected manual TTS.
3. ElevenLabs, voice selection, cache invalidation, measured audio durations.
4. Wire duration-driven timeline into generation/UI; validate progressive timing.
5. Background/random offsets/loop, quiet music/fades, watermark settings.
6. FFmpeg final renderer with continuous gameplay and integration tests.
7. Basic composed preview, save/load, missing-asset recovery.
8. End-to-end verification, bug fixes and documentation cleanup.

Iteration 1 covers phases 0 and minimal 1, plus cleaner, pure timeline foundation and JSON persistence to make authoring reviewable. No OCR, API or encoding calls are included.

Iteration 2 delivers selected-item local Vietnamese/English OCR, editable results, explicit reply selection, worker cancellation/timeouts and real OCR tests. Full Auto Generate, TTS, audio timing and rendering remain next phases.

Iteration 3 replaces mandatory manual text selection with positioned Threads body extraction, automatic TTS text preparation, progressive fuzzy reply diff, confidence/review status and a scene-ordered Auto Generate Text queue. Raw OCR/manual selection remain Advanced fallbacks. Actual TTS/audio/video phases remain future work.

## V2

Meme and SFX render; timeline editing; transitions; better preview; presets; drag reorder.

## V3

AI meme/SFX suggestions; subtitles; batch generation; template library; advanced automation.


## 2026-09-14 status
V1 phases 3-6 now have selected-item voice generation/cache, measured timeline, media controls and final FFmpeg export. Mock TTS and actual local encode tests pass; live voice permissions and visible production acceptance are separate. Next are composed preview/missing-media recovery and end-to-end acceptance; batch voice generation remains pending.
