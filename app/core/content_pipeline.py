"""Apply extraction and derive narration in scene order; no widgets or engine calls."""
import json
from app.core.models import ItemRole
from app.core.text_cleaner import clean_text
from app.services.content_extractor.thread_diff import extract_new_thread_text


def apply_detection(manager, item, ocr, extraction, replace_body=False):
    item.ocr_result = ocr
    item.ocr_text = item.raw_ocr_text = ocr.full_text
    item.ocr_status = "done"
    if not item.body_text_is_manual or replace_body:
        item.body_text = item.full_body_text = item.display_text = extraction.body_text
        item.body_text_is_manual = False
        item.extraction_confidence = extraction.confidence
        item.extraction_method = extraction.method
        item.extraction_warnings = list(extraction.warnings)
        item.extraction_debug = json.dumps(extraction.debug_info, ensure_ascii=False)
    refresh_scene(manager, next(scene for scene in manager.project.scenes if item in scene.items))
    manager.changed()


def refresh_scene(manager, scene):
    cfg = manager.project.extraction_settings
    previous = None
    for item in scene.items:
        body = item.body_text
        item.full_body_text = body
        item.extraction_warnings = [w for w in item.extraction_warnings if not w.startswith("Thread: ")]
        confidence = 1.0 if item.body_text_is_manual else item.extraction_confidence
        item.new_body_text = body
        item.thread_diff_confidence = 1.0
        if item.role == ItemRole.REPLY:
            previous_ready = previous and previous.ocr_status != "error" and (previous.body_text_is_manual or
                             previous.extraction_confidence >= cfg.threads_min_confidence)
            diff = extract_new_thread_text(previous.full_body_text if previous_ready else "", body, cfg)
            item.new_body_text = diff.new_text
            item.thread_diff_confidence = diff.confidence
            confidence = min(confidence, diff.confidence)
            item.extraction_warnings.extend("Thread: " + w for w in diff.warnings)
        item.needs_review = confidence < cfg.threads_min_confidence or not item.new_body_text.strip() or item.ocr_status == "error"
        # Empty/ambiguous reply clears only automatic narration; manual narration survives.
        if not item.tts_text_is_manual and item.ocr_status != "error":
            text = clean_text(item.new_body_text, manager.project.cleaner_settings) if item.new_body_text.strip() else ""
            manager.edit_tts(item, text, manual=False)
        previous = item
