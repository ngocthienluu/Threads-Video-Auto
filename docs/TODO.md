# High Priority

- [x] Inspect empty root; create structure and agent rules.
- [x] Create initial project documentation.
- [x] Implement and test config, models, cleaner, persistence and timeline foundation.
- [x] Implement and verify PySide6 import, Single/Thread, reply editing and static preview (offscreen).
- [x] Install dependency and run app smoke test (offscreen, exit 0).
- [x] Fix offscreen font discovery and inspect main-window screenshot.
- [x] Verify 25 tests and update first-iteration documentation.
- [x] Confirm initial desktop opening/import from user screenshot (partial acceptance only).
- [ ] Perform full visible Windows desktop acceptance, including new OCR controls and cumulative replies.
- [x] Integrate local OCR with editable results and cumulative-reply review via explicit text selection.
- [x] Install/version/checksum-pin Windows OCR engine and Vietnamese/English data; document offline operation and explicit setup.
- [x] Test real OCR on Vietnamese light/dark fixtures and two user screenshots; record accent/interface-noise limitations.
- [x] Verify cancellation, timeout, cache, error restoration, safe close and manual text protection; 41 tests pass.
- [x] Introduce provider-neutral OCR blocks/source geometry and ContentExtractor abstraction.
- [x] Implement adaptive normalized-ROI Threads body extraction with header/footer/noise filtering and numeric-content preservation.
- [x] Implement cumulative/full/new body state and fuzzy prefix diff; withhold uncertain/empty reply narration.
- [x] Automatically prepare TTS Text and enable scene-ordered Auto Generate Text; move raw OCR and manual selection into Advanced.
- [x] Preserve manual body/TTS independently, support explicit Re-run and legacy JSON defaults, recompute downstream text after edits/reorder.
- [x] Validate 62 tests, real engine progressive fixtures and three user screenshots; update documentation/ADRs.
- [ ] Validate extraction on real cumulative user Thread screenshot sets and more atypical layouts.
- [x] Integrate ElevenLabs, voice selection, protected manual edits and cache (HTTP-mock validation; live account validation remains below).
- [x] Implement ffprobe duration and wire timeline to audio; verify real WAV/MP3 fixtures.
- [x] Implement continuous gameplay, music, watermark and FFmpeg export (2026-09-14).

# Medium Priority

- [ ] Add composed preview and missing-media relink UI.
- [x] Add per-item OCR done/error status from actual jobs while preserving text on failure/cancel.
- [x] Add per-item TTS/error status from worker results; verify success/error/cancellation with mocks.
- [ ] Add render integration tests and complete V1 acceptance run.
- [ ] Add drag/drop import and drag reorder.
- [x] Wire/test OCR worker lifecycle, cancellation, timeout and safe errors.
- [x] Extend lifecycle/cancellation to TTS workers.
- [ ] Improve large-import responsiveness and extend lifecycle/cancellation to render services.
- [x] Test paid-provider orchestration and safe API errors using HTTP mocks; live validation remains below.
- [x] Use normalized region priors/adaptive body selection and optional debug crops (default off).
- [ ] Evaluate OCR accuracy on more screenshots; add interactive crop/region selection before OCR if needed.

# Low Priority

- [ ] Meme/SFX rendering, presets, transitions, richer preview (V2).
- [ ] Subtitles, AI suggestions, batch rendering and templates (V3).

# Blocked

- [x] Actual ffprobe integration validation with real audio and local FFmpeg MP3 encoding.
- [x] Actual final video renderer validation with local synthetic media (2026-09-14).
- [ ] Live ElevenLabs validation.
  Reason: Provider implemented and tested with mocks; live validation requires a configured account key/voice and a credit-consuming request. No live request sent.

## Caption OCR / spelling follow-up
- [x] Fix supplied cmt4/cmt5 caption extraction; verify original images unchanged.
- [x] Add local spelling suggestions with editable preview and Save/Cancel.
- [x] Run 65 tests and offscreen app smoke launch; document actual limits.
- [ ] Expand reviewed Vietnamese spelling vocabulary and test ambiguous names/slang.
- [ ] Improve icon-only footer handling (observed on cmt6) and test more mixed-media layouts.
- [ ] Validate the new dialog in a visible Windows GUI session.

## Alternative PaddleOCR provider
- [x] Add OCR Engine dropdown; verify both-direction routing, busy state, manual text and provider reuse (74 tests pass).
- [x] Add PaddleOCRProvider with compatible OCRResult geometry and string API.
- [x] Select paddle/tesseract via runtime config; preserve Tesseract and technical-error-only fallback.
- [x] Reuse an isolated model process; handle cancel, timeout, native failure and shutdown.
- [x] Test conversion, empty/malformed results, confidence, exception handling and selection (73 total tests pass).
- [x] Install official dependencies on current Windows x64 / Python 3.13.1; pip check passes.
- [x] Run both real engines on cmt4/cmt5, confirm model reuse and unchanged source bytes, save raw/body comparison.
- [x] Document setup, CPU compatibility adjustment, known quality limits and ADR-015.
- [x] Verify actual Paddle OCR through the Qt worker/UI offscreen with no fallback; inspect screenshot.
- [ ] Investigate Vietnamese diacritic loss in the current Paddle Latin model; compare alternate official recognition models before recommending it over Tesseract.
- [ ] Improve platform extraction for Paddle span geometry (joined carousel counter/drawing symbols), with regression fixtures.
- [ ] Add provider-specific disk result caching if repeated Paddle runs become a bottleneck.
- [ ] Validate visible GUI and other Windows/Python combinations separately.

## 2026-09-10 - Narration phase
- [x] Make Tesseract the primary/default OCR, retain Paddle selector.
- [x] Implement selected-item ElevenLabs speech adapter, voice list/manual ID and speed controls; verify with HTTP mocks.
- [x] Implement cancellation/error reporting, reviewed-text guard and protected manual narration.
- [x] Implement atomic audio cache keyed by model/format/text/voice/speed; validate cache with ffprobe.
- [x] Install/checksum-verify project-local FFmpeg/ffprobe and measure actual WAV/MP3 fixtures.
- [x] Wire measured audio to core timeline; invalidate stale audio/timing on edits.
- [x] Verify 87 tests, offscreen startup and pip check; update architecture/spec/setup/ADR.
- [ ] LIVE integration: configure an ElevenLabs account key/voice and verify generated Vietnamese speech and audio playback. Not claimed tested; no live API request sent.
- [ ] Add scene-ordered batch voice generation after live selected-item validation.
- [x] Implement continuous gameplay/music/watermark and final video rendering; actual FFmpeg tests pass (2026-09-14).


## ElevenLabs voice access follow-up
- [x] Explain HTTP 402 with subscription/balance/API voice-access checks; verify mocked error, redaction and no retry (10 TTS tests, offscreen smoke pass).
- [ ] Confirm affected voice access in the user account; HTTP status alone does not identify the specific billing restriction.


## Dynamic voice selection/access UX (2026-09-10)
- [x] Add VoiceInfo, API list/details, atomic metadata cache and stale-list warning.
- [x] Show names, search, persistent access status, Refresh and explicit short Test Voice.
- [x] Add manual/effective ID and model under Advanced; preserve .env fallback.
- [x] Persist project default/model and per-item inheritance/override; load older projects.
- [x] Friendly 401/402/403/429/network errors; no automatic voice tests/retries or secret output.
- [x] Preserve previous audio across voice changes and failed regeneration; exclude stale audio from timeline.
- [x] Validate 98 tests and offscreen startup; inspect UI screenshot; update docs/ADR-017.
- [ ] Live integration test of this iteration with account-permitted/restricted voices: integration test not performed.
- [ ] Visible Windows acceptance and listening review of the short sample/selected narration.


## Audio cleanup (2026-09-10)
- [x] Add reference-aware generated MP3 cleanup with current/saved/shared/external project protection.
- [x] Add Tools preview/count/size and explicit delete in worker; block alongside OCR/TTS.
- [x] Recheck references/file identity, refuse unsafe paths or unreadable projects and report skipped deletes.
- [x] Pass 107 tests and offscreen app smoke; update README/spec/architecture/ADR-018.
- [ ] User desktop acceptance of cleanup preview on actual working projects/audio.


## Export phase (2026-09-14)
- [x] Add persisted gameplay/music/watermark/screenshot/timing controls.
- [x] Implement continuous FFmpeg MP4 composition with actual narration duration and progressive screenshots.
- [x] Add worker progress/cancel, close coordination and atomic previous-output preservation.
- [x] Verify 113 tests, offscreen smoke, actual 1080x1920 export and frame inspection; update docs/ADR-019.
- [ ] Visible Windows acceptance with the user's gameplay and narration, including human listening check.
- [ ] Benchmark longer projects/many images and additional FFmpeg versions.
- [ ] Add composed playback preview and missing-media relink UI.

- [x] Fix media Browse default folders and retain current-file parent; verify dialog arguments, 22 UI tests and offscreen startup (2026-09-14).
