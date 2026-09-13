"""Typed project schema, independent of Qt and providers."""
from dataclasses import asdict, dataclass, field, fields
from datetime import datetime, timezone
from enum import Enum
import math
from types import UnionType
from typing import get_args, get_origin, get_type_hints
from uuid import uuid4
from copy import deepcopy
from app.core.ocr_models import OCRResult
from app.core.editor_objects import EditorObject

from app.core.config import (BackgroundSettings, CleanerSettings, MusicSettings,
                             TimingSettings, VideoSettings, WatermarkSettings, ExtractionSettings)


def new_id() -> str:
    return uuid4().hex


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


class SceneType(str, Enum):
    SINGLE = "single"
    THREAD = "thread"


class ItemRole(str, Enum):
    SINGLE = "single"
    QUESTION = "question"
    REPLY = "reply"


@dataclass
class MemeConfig:
    enabled: bool = False
    file: str = ""
    mode: str = "overlay"
    start_mode: str = "end_of_voice"
    start_value: float = 0.0
    duration: float = 1.0
    volume: float = 1.0


@dataclass
class SfxConfig:
    enabled: bool = False
    file: str = ""
    start_mode: str = "end_of_voice"
    start_value: float = 0.0
    offset: float = 0.0
    volume: float = 1.0


@dataclass
class SceneItem:
    id: str = field(default_factory=new_id)
    role: ItemRole = ItemRole.SINGLE
    original_image_path: str = ""
    ocr_text: str = ""
    display_text: str = ""
    raw_ocr_text: str = ""
    ocr_result: OCRResult | None = None
    body_text: str = ""
    full_body_text: str = ""
    new_body_text: str = ""
    body_text_is_manual: bool = False
    extraction_confidence: float = 0.0
    extraction_method: str = "pending"
    extraction_warnings: list[str] = field(default_factory=list)
    extraction_debug: str = ""
    thread_diff_confidence: float = 0.0
    needs_review: bool = True
    tts_text: str = ""
    tts_text_is_manual: bool = False
    voice_id: str = ""
    voice_speed: float = 1.0
    audio_path: str = ""
    audio_duration: float = 0.0
    start_time: float = 0.0
    end_time: float = 0.0
    ocr_status: str = "pending"
    tts_status: str = "pending"
    timeline_status: str = "pending"
    meme: MemeConfig | None = None
    sfx: SfxConfig | None = None

    def invalidate_audio(self) -> None:
        self.audio_path = ""
        self.audio_duration = 0.0
        self.tts_status = "pending"
        self.start_time = self.end_time = 0.0
        self.timeline_status = "pending"


@dataclass
class Scene:
    id: str = field(default_factory=new_id)
    scene_type: SceneType = SceneType.SINGLE
    items: list[SceneItem] = field(default_factory=list)
    display_mode: str = "progressive"
    transition: str | None = None


@dataclass
class Project:
    editor_objects: list[EditorObject] = field(default_factory=list)
    snap_enabled: bool = True
    snap_threshold: float = 12.0
    show_safe_area: bool = False
    schema_version: int = 1
    id: str = field(default_factory=new_id)
    name: str = "Untitled"
    tts_provider: str = "elevenlabs"
    default_voice_id: str = ""
    default_voice_name: str = ""
    tts_model_id: str = ""
    created_at: str = field(default_factory=now)
    updated_at: str = field(default_factory=now)
    video_settings: VideoSettings = field(default_factory=VideoSettings)
    background_settings: BackgroundSettings = field(default_factory=BackgroundSettings)
    music_settings: MusicSettings = field(default_factory=MusicSettings)
    watermark_settings: WatermarkSettings = field(default_factory=WatermarkSettings)
    cleaner_settings: CleanerSettings = field(default_factory=CleanerSettings)
    timing_settings: TimingSettings = field(default_factory=TimingSettings)
    extraction_settings: ExtractionSettings = field(default_factory=ExtractionSettings)
    scenes: list[Scene] = field(default_factory=list)

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Project":
        if not isinstance(data, dict) or "schema_version" not in data:
            raise ValueError("Project JSON must contain schema_version.")
        data = deepcopy(data)
        if isinstance(data.get("scenes", []), list):
            for scene in data.get("scenes", []):
                if not isinstance(scene, dict) or not isinstance(scene.get("items", []), list):
                    continue
                for item in scene.get("items", []):
                    if isinstance(item, dict) and "raw_ocr_text" not in item:
                        item["raw_ocr_text"] = item.get("ocr_text", "")
                        if item.get("ocr_status") == "manual":
                            item.setdefault("body_text", item.get("ocr_text", ""))
                            item.setdefault("full_body_text", item.get("ocr_text", ""))
                            item.setdefault("body_text_is_manual", True)
        project = _decode(cls, data)
        project.validate()
        return project

    def validate(self) -> None:
        if self.tts_provider != "elevenlabs":
            raise ValueError("Unsupported TTS provider.")
        if self.schema_version != 1:
            raise ValueError("Unsupported project schema version.")
        ids = {self.id}
        if not self.id:
            raise ValueError("Project ID cannot be empty.")
        for scene in self.scenes:
            for identity in [scene.id, *(item.id for item in scene.items)]:
                if not identity or identity in ids:
                    raise ValueError("Scene and item IDs must be unique and nonempty.")
                ids.add(identity)
            if not scene.items or (scene.scene_type == SceneType.SINGLE and len(scene.items) != 1):
                raise ValueError("Single needs one item; Thread needs a question image.")
            if scene.display_mode != "progressive":
                raise ValueError("Only progressive display is supported.")
            for index, item in enumerate(scene.items):
                expected = (ItemRole.SINGLE if scene.scene_type == SceneType.SINGLE else
                            ItemRole.QUESTION if index == 0 else ItemRole.REPLY)
                if item.role != expected:
                    raise ValueError("Item role does not match its scene position.")
                if not item.original_image_path:
                    raise ValueError("Item image path cannot be empty.")
                if item.voice_speed <= 0 or min(item.audio_duration, item.start_time, item.end_time) < 0:
                    raise ValueError("Invalid voice speed or item timing.")
                if item.end_time < item.start_time:
                    raise ValueError("Item end precedes start.")
                if not 0 <= item.extraction_confidence <= 1 or not 0 <= item.thread_diff_confidence <= 1:
                    raise ValueError("Invalid extraction confidence.")
                if item.ocr_result:
                    item.ocr_result.validate()
                if item.ocr_status not in {"pending", "done", "manual", "error"} or item.tts_status not in {"pending", "done", "error"} or item.timeline_status not in {"pending", "done"}:
                    raise ValueError("Invalid item status.")
        for obj in self.editor_objects:
            obj.validate()
            if not obj.id or obj.id in ids:
                raise ValueError("Object IDs must be unique.")
            ids.add(obj.id)
        if not 0 <= self.snap_threshold <= 100:
            raise ValueError("Invalid snap threshold.")
        v = self.video_settings
        cfg = self.extraction_settings
        if not (0 <= cfg.threads_body_left_ratio < cfg.threads_body_right_ratio <= 1 and
                0 <= cfg.threads_body_top_ratio < cfg.threads_body_bottom_ratio <= 1 and
                0 <= cfg.threads_min_confidence <= cfg.threads_auto_accept_confidence <= 1 and
                0 < cfg.thread_diff_similarity_threshold <= 1):
            raise ValueError("Invalid extraction ROI or confidence thresholds.")
        if min(cfg.header_max_words, cfg.footer_max_words, cfg.min_body_letters, cfg.diff_min_context_tokens) <= 0:
            raise ValueError("Extraction limits must be positive.")
        if cfg.line_gap_height_ratio <= 0 or not 0 <= cfg.alignment_width_ratio <= 1 or not 0 <= cfg.diff_length_tolerance <= 1:
            raise ValueError("Invalid extraction geometry/diff tolerance.")
        for value in (cfg.min_letter_ratio, cfg.diff_strong_similarity, cfg.unanchored_score_cap, cfg.weak_score_cap, cfg.fallback_score):
            if not 0 <= value <= 1:
                raise ValueError("Invalid extraction score setting.")
        weights = (cfg.ocr_score_weight, cfg.header_score_weight, cfg.text_score_weight, cfg.roi_score_weight)
        if min(weights) < 0 or not math.isclose(sum(weights), 1.0):
            raise ValueError("Extraction confidence weights must be nonnegative and sum to 1.")
        if min(v.width, v.height, v.fps) <= 0 or v.width % 2 or v.height % 2:
            raise ValueError("Video dimensions must be positive even numbers; FPS must be positive.")
        if not 0 < v.comment_max_width_ratio <= 1 or not 0 <= v.comment_y_ratio <= 1:
            raise ValueError("Invalid screenshot placement ratios.")
        if self.cleaner_settings.emoji_mode not in {"ignore", "keep"}:
            raise ValueError("Emoji meaning mode is not implemented.")
        t = self.timing_settings
        if min(t.voice_pre_padding, t.voice_post_padding, t.scene_gap) < 0:
            raise ValueError("Padding and gaps cannot be negative.")
        if not 0 <= self.watermark_settings.opacity <= 1 or self.watermark_settings.size <= 0:
            raise ValueError("Invalid watermark opacity/size.")
        if not 0 <= self.music_settings.volume <= 1 or not 0 <= self.background_settings.volume <= 1:
            raise ValueError("Volume must be between 0 and 1.")
        if min(self.music_settings.fade_in, self.music_settings.fade_out) < 0:
            raise ValueError("Music fades cannot be negative.")


def _decode(kind, value):
    """Strict recursive decoding: malformed JSON must not partially replace a project."""
    if get_origin(kind) is UnionType:
        if value is None and type(None) in get_args(kind):
            return None
        return _decode(next(t for t in get_args(kind) if t is not type(None)), value)
    if get_origin(kind) is list:
        if not isinstance(value, list):
            raise ValueError("Expected a list.")
        return [_decode(get_args(kind)[0], entry) for entry in value]
    if isinstance(kind, type) and issubclass(kind, Enum):
        return kind(value)
    if hasattr(kind, "__dataclass_fields__"):
        if not isinstance(value, dict):
            raise ValueError(f"Expected object for {kind.__name__}.")
        hints = get_type_hints(kind)
        unknown = set(value) - {f.name for f in fields(kind)}
        if unknown:
            raise ValueError(f"Unknown fields in {kind.__name__}: {', '.join(sorted(unknown))}")
        return kind(**{key: _decode(hints[key], val) for key, val in value.items()})
    if kind is float:
        if type(value) not in (float, int) or not math.isfinite(value):
            raise ValueError("Expected a finite number.")
        return float(value)
    if type(value) is not kind:
        raise ValueError(f"Expected {kind.__name__}.")
    return value
