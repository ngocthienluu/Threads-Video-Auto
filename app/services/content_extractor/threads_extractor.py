"""Position-aware Threads layout heuristics, with ROI as a prior, not a hard crop."""
from collections import defaultdict
from dataclasses import dataclass
import re
from statistics import mean, median

from app.core.config import ExtractionSettings
from app.core.ocr_models import OCRResult
from app.services.content_extractor.base import ContentExtractor, ExtractionResult
from app.services.content_extractor.thread_diff import normalized

TIME = re.compile(r"\b(?:\d{1,2}/\d{1,2}(?:/\d{2,4})?|\d+\s*(?:gio|gid|phut|ngay|tuan|thang|nam|giay|hours?|mins?|days?|[hmdw]))\b")
ACTION = re.compile(r"^(?:hien thi tra loi|an tra loi|tra loi|xem them|view replies|hide replies|reply|see more)$")


@dataclass
class Line:
    text: str
    x: float
    y: float
    right: float
    bottom: float
    confidence: float
    line_id: int

    @property
    def height(self):
        return max(1, self.bottom - self.y)


def group_lines(result):
    grouped = defaultdict(list)
    for block in result.blocks:
        if block.text.strip():
            grouped[block.line_id].append(block)
    lines = []
    for identity, blocks in grouped.items():
        blocks.sort(key=lambda b: b.x)
        lines.append(Line(" ".join(b.text for b in blocks), min(b.x for b in blocks), min(b.y for b in blocks),
                          max(b.x + b.width for b in blocks), max(b.y + b.height for b in blocks),
                          mean(b.confidence for b in blocks), identity))
    return sorted(lines, key=lambda line: (line.y, line.x))


class ThreadsExtractor(ContentExtractor):
    def __init__(self, settings: ExtractionSettings | None = None, read_username: bool = False):
        self.settings = settings or ExtractionSettings()
        self.read_username = read_username

    def extract(self, result: OCRResult) -> ExtractionResult:
        cfg = self.settings
        lines = group_lines(result)
        if not cfg.threads_extraction_enabled or not lines or not result.image_width or not result.image_height:
            return self._fallback(result, "Position-aware extraction unavailable or disabled.")
        width, height = result.image_width, result.image_height
        # Discard leading icon words before inferring the text column.
        for line in lines:
            tokens = [b for b in result.blocks if b.line_id == line.line_id and any(c.isalpha() for c in b.text)]
            if tokens:
                line.x = min(b.x for b in tokens)
        body_candidates = [line.x for line in lines if sum(c.isalpha() for c in line.text) >= cfg.min_body_letters
                           and len(line.text.split()) > cfg.header_max_words and not TIME.search(normalized(line.text))]
        body_left = median(body_candidates) if body_candidates else cfg.threads_body_left_ratio * width
        typical_height = median(line.height for line in lines)
        selected, dropped, headers = [], [], []
        section_header = None
        footer = False
        for index, line in enumerate(lines):
            text = normalized(line.text)
            words = text.split()
            center_y = (line.y + line.bottom) / 2 / height
            prior_roi = (cfg.threads_body_left_ratio <= line.x / width <= cfg.threads_body_right_ratio and
                         cfg.threads_body_top_ratio <= center_y <= cfg.threads_body_bottom_ratio)
            previous = lines[index - 1] if index else None
            gap = line.y - previous.bottom if previous else 0
            # Headers need timestamp, short-line context and a section boundary.
            timestamp = TIME.search(text)
            prefix_words = text[:timestamp.start()].split() if timestamp else []
            header_shape = (not prefix_words or len(prefix_words) == 1 or ">" in prefix_words or
                            (len(prefix_words) == 2 and len(prefix_words[0]) <= 2))
            header = bool(timestamp and len(words) <= cfg.header_max_words and
                          header_shape and (center_y < cfg.threads_body_top_ratio or footer or (not selected and section_header is None) or
                           gap > cfg.line_gap_height_ratio * typical_height) and
                          (timestamp.start() > 0 or center_y < cfg.threads_body_top_ratio))
            # Dim timestamps may vanish; a short, punctuated handle above aligned prose
            # can still anchor the header. Keep this fallback confined to the first line.
            header = header or bool(index == 0 and center_y < cfg.threads_body_top_ratio and
                                    len(words) <= cfg.header_max_words and any(re.fullmatch(r"[\w]+[._][\w.]+", w) for w in words))
            if header:
                section_header = line
                footer = False
                headers.append(line)
                dropped.append((line.line_id, "header_timestamp"))
                # A username on a separate neighboring line above a timestamp.
                if previous and selected and selected[-1] is previous and timestamp.start() == 0 and len(previous.text.split()) <= 2:
                    selected.pop()
                    dropped.append((previous.line_id, "header_username"))
                continue
            if section_header and line.y < section_header.bottom and sum(c.isalpha() for c in line.text) < 3:
                dropped.append((line.line_id, "header_avatar"))
                continue
            stripped_action = re.sub(r"^[^a-z]+", "", text).strip(" .:")
            action = ACTION.fullmatch(stripped_action)
            # OCR icon prefixes may become letters; only accept a label at line end.
            action_tail = any(text.endswith(label) for label in ("hien thi tra loi", "an tra loi", "view replies"))
            letters = sum(c.isalpha() for c in line.text)
            alnums = max(1, sum(c.isalnum() for c in line.text))
            numeric_icons = bool(re.search(r"\d", text) and len(words) <= cfg.footer_max_words and
                                 letters / alnums < cfg.min_letter_ratio)
            compact_counts = sum(c.isdigit() for c in text) >= 2 and all(len(word) <= 3 for word in words)
            compact_counts = compact_counts or (len(words) <= cfg.footer_max_words and
                sum(bool(re.search(r"\d.*[km]$", w)) for w in words) >= 2)
            numeric_icons = numeric_icons or compact_counts
            separated = bool(selected and gap > cfg.line_gap_height_ratio * typical_height)
            footer_position = bool(selected and (separated or footer or center_y > cfg.threads_body_bottom_ratio))
            if (action or action_tail or numeric_icons) and footer_position:
                footer = True
                dropped.append((line.line_id, "footer_action_or_counts"))
                continue
            if footer:
                dropped.append((line.line_id, "after_footer"))
                continue
            words_in_column = [b for b in result.blocks if b.line_id == line.line_id and
                               b.x >= body_left - cfg.alignment_width_ratio * width]
            if selected and line.y < selected[-1].bottom and line.height < typical_height * .5:
                dropped.append((line.line_id, "small_inline_icon"))
                continue
            if words_in_column and re.fullmatch(r"\d+/\d+", words_in_column[-1].text):
                badge = words_in_column[-1]
                if len(words_in_column) > 1 and badge.height < median(b.height for b in words_in_column[:-1]) * .9:
                    words_in_column = words_in_column[:-1]
            aligned = section_header and words_in_column and line.right >= body_left
            # Body can grow beyond the default ROI when a header anchors its layout.
            if prior_roi or aligned:
                # Exclude avatar/icon blocks left of the inferred body column, not body words.
                if words_in_column:
                    line.text = " ".join(b.text for b in sorted(words_in_column, key=lambda b: b.x))
                selected.append(line)
            else:
                dropped.append((line.line_id, "outside_body_prior"))
        if not selected:
            return self._fallback(result, "No credible body region detected.")
        body = "\n".join(line.text for line in selected).strip()
        letters = sum(c.isalpha() for c in body)
        ocr_score = mean(line.confidence for line in selected)
        anchor_score = 1.0 if headers else .5
        letter_score = min(1, letters / max(1, cfg.min_body_letters))
        roi_score = mean(cfg.threads_body_left_ratio <= line.x / width <= cfg.threads_body_right_ratio for line in selected)
        confidence = (cfg.ocr_score_weight * ocr_score + cfg.header_score_weight * anchor_score +
                      cfg.text_score_weight * letter_score + cfg.roi_score_weight * roi_score)
        warnings = []
        if not headers:
            confidence = min(confidence, cfg.unanchored_score_cap)
            warnings.append("No clear Threads header; ROI prior used. Check for clipped body lines.")
        if letters < cfg.min_body_letters:
            confidence = min(confidence, cfg.weak_score_cap)
            warnings.append("Very little comment text detected.")
        if ocr_score < cfg.threads_min_confidence:
            confidence = min(confidence, cfg.weak_score_cap)
            warnings.append("Low OCR confidence in body text.")
        if self.read_username and headers:
            # Only explicitly identified header text; timestamp is excluded.
            names = [h.text[:match.start()].strip(" @") if (match := TIME.search(normalized(h.text))) else h.text for h in headers]
            warnings.append("Username reading is enabled; check recognized names.")
            body = "\n".join([*filter(None, names), body])
        return ExtractionResult(result.full_text, body, round(confidence, 3), "threads_layout_bbox", warnings,
                                {"kept_lines": [line.line_id for line in selected], "dropped_lines": dropped,
                                 "body_regions": [[line.x, line.y, line.right, line.bottom] for line in selected]})

    def _fallback(self, result, detail):
        return ExtractionResult(result.full_text, result.full_text.strip(), self.settings.fallback_score if result.full_text.strip() else 0,
                                "raw_ocr_fallback", ["Automatic comment extraction failed. Review detected text.", detail])
