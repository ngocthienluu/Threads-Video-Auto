from dataclasses import replace
import json
from pathlib import Path
import tempfile
import unittest

from app.core.config import ExtractionSettings
from app.core.models import Project
from app.core.project_manager import ProjectManager
from app.core.ocr_models import OCRBlock, OCRResult
from app.services.content_extractor.threads_extractor import ThreadsExtractor
from app.services.content_extractor.thread_diff import extract_new_thread_text


def screenshot(body_lines, header="some_user 4 giờ", width=1000, scale=1, confidence=.96):
    entries = [(header, 90, 20)]
    entries += [(line, 100, 65 + i * 32) for i, line in enumerate(body_lines)]
    footer_y = 65 + len(body_lines) * 32 + 25
    entries += [("4 2 1", 100, footer_y), ("Hiển thị trả lời", 100, footer_y + 60)]
    blocks = [OCRBlock(text, x * scale, y * scale, min(width - x - 10, max(40, len(text) * 9)) * scale,
                       22 * scale, confidence, "line", i) for i, (text, x, y) in enumerate(entries)]
    return OCRResult("\n".join(t for t, _, _ in entries), blocks, int(width * scale), int((footer_y + 100) * scale))


class ThreadsExtractorTests(unittest.TestCase):
    def test_realistic_header_footer_removed_body_numbers_preserved(self):
        body = ["em biết 1 quán có cơm tấm, bún thịt nướng,...",
                "trên đường hoàng diệu 2 giá rẻ mà ăn no.",
                "Quán không có trên map nhưng mà trong hẻm quanh khu này nè",
                "(đầu hẻm là circle K)"]
        result = ThreadsExtractor().extract(screenshot(body, header="vhuy295 4 giờ"))
        self.assertEqual(result.body_text, "\n".join(body))
        self.assertGreaterEqual(result.confidence, .8)
        self.assertEqual(result.method, "threads_layout_bbox")

    def test_numbers_prices_and_ui_phrases_inside_body_remain(self):
        body = ["quán 20k ăn 2 người", "Mình chờ 4 giờ rồi, bấm Trả lời nhé", "2", "đường hoàng diệu 2"]
        self.assertEqual(ThreadsExtractor().extract(screenshot(body)).body_text, "\n".join(body))
        self.assertEqual(ThreadsExtractor().extract(screenshot(["Mình chờ 4 giờ rồi", "quán 20k ăn 2 người"])).body_text,
                         "Mình chờ 4 giờ rồi\nquán 20k ăn 2 người")

    def test_long_body_expands_roi_and_does_not_drop_last_paragraph(self):
        body = [f"Đoạn nội dung thứ {i} với số 20k và 2 người" for i in range(15)]
        self.assertEqual(ThreadsExtractor().extract(screenshot(body)).body_text, "\n".join(body))

    def test_scale_invariant_positions(self):
        body = ["Nội dung tiếng Việt có dấu", "Dòng thứ hai kết thúc"]
        results = [ThreadsExtractor().extract(screenshot(body, scale=scale)).body_text for scale in (.5, 1, 2)]
        self.assertEqual(results, ["\n".join(body)] * 3)

    def test_dates_and_varying_username(self):
        for header in ("another.name 3 phút", "any_user 1 ngày", "artist > Art Threads 21/01/2025"):
            self.assertEqual(ThreadsExtractor().extract(screenshot(["Nội dung chính của bình luận"], header=header)).body_text,
                             "Nội dung chính của bình luận")

    def test_positionless_fallback_and_empty(self):
        result = ThreadsExtractor().extract(OCRResult(full_text="raw text"))
        self.assertEqual(result.body_text, "raw text")
        self.assertLess(result.confidence, .6)
        self.assertTrue(result.warnings)
        self.assertEqual(ThreadsExtractor().extract(OCRResult()).body_text, "")

    def test_low_ocr_confidence_and_tiny_text(self):
        self.assertLess(ThreadsExtractor().extract(screenshot(["Nội dung đọc không rõ"], confidence=.2)).confidence, .6)
        self.assertLess(ThreadsExtractor().extract(screenshot(["A"])).confidence, .6)

    def test_roi_can_be_configured_without_header(self):
        raw = OCRResult("body outside prior", [OCRBlock("body outside prior", 10, 80, 80, 10, .9, "line", 0)], 100, 100)
        default = ThreadsExtractor().extract(raw)
        adjusted = ThreadsExtractor(replace(ExtractionSettings(), threads_body_bottom_ratio=.95)).extract(raw)
        self.assertEqual(default.method, "raw_ocr_fallback")
        self.assertEqual(adjusted.method, "threads_layout_bbox")

    def test_multiple_cumulative_comment_sections(self):
        first = screenshot(["Câu hỏi ban đầu là gì"])
        second = screenshot(["Đây là câu trả lời mới"], header="reply_user 2 giờ")
        offset = first.image_height
        blocks = first.blocks + [replace(b, y=b.y + offset, line_id=b.line_id + len(first.blocks)) for b in second.blocks]
        result = ThreadsExtractor().extract(OCRResult(first.full_text + "\n" + second.full_text, blocks, 1000, offset + second.image_height))
        self.assertEqual(result.body_text, "Câu hỏi ban đầu là gì\nĐây là câu trả lời mới")


class ThreadDiffTests(unittest.TestCase):
    def test_exact_and_missing_diacritics(self):
        previous = "Vậy làm cách nào để nhìn trước tương lai đi"
        for current in (previous + "\nXem lịch", "Vậy làm cách nao để nhìn truoc tương lai đi Xem lịch"):
            result = extract_new_thread_text(previous, current)
            self.assertEqual(result.new_text, "Xem lịch")
            self.assertGreaterEqual(result.confidence, .84)

    def test_multiple_replies_and_repeated_words(self):
        first = "A B C D"
        self.assertEqual(extract_new_thread_text(first, first + " E").new_text, "E")
        self.assertEqual(extract_new_thread_text(first + " E", first + " E E nữa").new_text, "E nữa")

    def test_ocr_minor_character_error(self):
        result = extract_new_thread_text("Vậy làm cách nào để nhìn trước tương lai đi", "Vậy làm cách nào để nhin trướe tương lai đi\nXem lịch")
        self.assertEqual(result.new_text, "Xem lịch")

    def test_uncertain_missing_and_identical_never_repeat_question(self):
        for before, after in (("", "Question and reply"), ("old unrelated question", "completely different words"),
                              ("Question already read", "Question already read"), ("hello", "hallo new")):
            result = extract_new_thread_text(before, after)
            self.assertEqual(result.new_text, "")
            self.assertLess(result.confidence, .6)
            self.assertTrue(result.warnings)


class ContentPipelineTests(unittest.TestCase):
    def apply(self, manager, item, body, force=False):
        ocr = screenshot(body)
        manager.apply_detection(item, ocr, ThreadsExtractor().extract(ocr), force)

    def test_single_auto_tts_and_manual_body_tts_protection(self):
        manager = ProjectManager()
        item = manager.add_single("image.png").items[0]
        self.apply(manager, item, ["ông này nói chuyện hài =)))"])
        self.assertEqual(item.tts_text, "ông này nói chuyện hài")
        self.assertFalse(item.needs_review)
        manager.edit_body(item, "Nội dung đã sửa tay")
        self.apply(manager, item, ["Nội dung OCR khác"])
        self.assertEqual(item.body_text, "Nội dung đã sửa tay")
        self.assertEqual(item.tts_text, "Nội dung đã sửa tay")
        manager.edit_tts(item, "Lời đọc riêng")
        self.apply(manager, item, ["Nội dung thay thế"], force=True)
        self.assertEqual(item.body_text, "Nội dung thay thế")
        self.assertEqual(item.tts_text, "Lời đọc riêng")

    def test_three_progressive_items_derive_only_new_reply(self):
        manager = ProjectManager()
        items = manager.add_thread(["q.png", "r1.png", "r2.png"]).items
        q = "Vậy làm cách nào để nhìn trước tương lai đi"
        for item, lines in zip(items, ([q], [q, "Xem lịch"], [q, "Xem lịch", "Lịch của năm sau nhé"])):
            self.apply(manager, item, lines)
        self.assertEqual([i.tts_text for i in items], [q, "Xem lịch", "Lịch của năm sau nhé"])
        self.assertEqual(items[2].full_body_text, q + "\nXem lịch\nLịch của năm sau nhé")

    def test_uncertain_reply_blocks_automatic_tts_and_reorder_recomputes(self):
        manager = ProjectManager()
        scene = manager.add_thread(["q.png", "r.png"])
        self.apply(manager, scene.items[0], ["Câu hỏi đầu tiên của tôi"])
        self.apply(manager, scene.items[1], ["Nội dung không khớp câu hỏi"])
        self.assertEqual(scene.items[1].tts_text, "")
        self.assertTrue(scene.items[1].needs_review)
        manager.move(scene, scene.items[1], -1)
        self.assertEqual(scene.items[1].tts_text, "")
        self.assertTrue(scene.items[1].needs_review)

    def test_empty_manual_body_no_automatic_tts_and_manual_empty_tts_preserved(self):
        manager = ProjectManager()
        item = manager.add_single("image.png").items[0]
        self.apply(manager, item, ["Nội dung bình luận gốc"])
        manager.edit_body(item, "")
        self.assertEqual(item.tts_text, "")
        self.apply(manager, item, ["OCR mới"])
        self.assertEqual(item.body_text, "")
        manager.edit_tts(item, "")
        self.apply(manager, item, ["Vẫn giữ TTS trống"], force=True)
        self.assertEqual(item.tts_text, "")
        self.assertTrue(item.tts_text_is_manual)

    def test_serialization_new_fields_and_legacy_default_migration(self):
        manager = ProjectManager()
        item = manager.add_single("image.png").items[0]
        self.apply(manager, item, ["Nội dung tự động được nhận diện"])
        clone = Project.from_dict(json.loads(json.dumps(manager.project.to_dict())))
        self.assertEqual(clone, manager.project)
        legacy = {"schema_version": 1, "scenes": [{"items": [{"original_image_path": "old.png",
                  "ocr_text": "text cũ", "ocr_status": "manual", "tts_text": "TTS cũ", "tts_text_is_manual": True}]}]}
        old = Project.from_dict(legacy).scenes[0].items[0]
        self.assertEqual(old.raw_ocr_text, "text cũ")
        self.assertEqual(old.body_text, "text cũ")
        self.assertTrue(old.body_text_is_manual)
        self.assertEqual(old.tts_text, "TTS cũ")
        self.assertIsNone(old.ocr_result)
