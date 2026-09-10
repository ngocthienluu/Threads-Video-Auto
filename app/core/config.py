"""Central defaults. No credentials belong in serializable settings."""
from dataclasses import dataclass
from pathlib import Path


@dataclass
class VideoSettings:
    width: int = 1080
    height: int = 1920
    fps: int = 30
    comment_max_width_ratio: float = 0.88
    comment_y_ratio: float = 0.42


@dataclass
class BackgroundSettings:
    file: str = ""
    random_file: bool = False
    random_start: bool = True
    loop: bool = True
    volume: float = 0.0


@dataclass
class MusicSettings:
    file: str = ""
    enabled: bool = False
    random_file: bool = False
    random_start: bool = True
    loop: bool = True
    volume: float = 0.08
    fade_in: float = 0.5
    fade_out: float = 0.5


@dataclass
class WatermarkSettings:
    enabled: bool = True
    text: str = "@CongDongThreads"
    font: str = ""
    size: int = 40
    opacity: float = 0.7
    position: str = "top-center"
    x: int = 0
    y: int = 60


@dataclass
class CleanerSettings:
    remove_emoticons: bool = True
    remove_urls: bool = True
    read_username: bool = False
    emoji_mode: str = "ignore"


@dataclass
class TimingSettings:
    voice_pre_padding: float = 0.10
    voice_post_padding: float = 0.15
    scene_gap: float = 0.05


@dataclass
class ExtractionSettings:
    threads_extraction_enabled: bool = True
    threads_body_left_ratio: float = 0.07
    threads_body_top_ratio: float = 0.14
    threads_body_right_ratio: float = 0.97
    threads_body_bottom_ratio: float = 0.72
    threads_min_confidence: float = 0.60
    threads_auto_accept_confidence: float = 0.80
    thread_diff_similarity_threshold: float = 0.84
    raw_ocr_visible_by_default: bool = False
    ocr_debug_save_regions: bool = False
    # Layout priors; no fixed screenshot pixels or usernames.
    header_max_words: int = 9
    footer_max_words: int = 10
    line_gap_height_ratio: float = 1.0
    alignment_width_ratio: float = 0.04
    min_letter_ratio: float = 0.40
    min_body_letters: int = 8
    diff_length_tolerance: float = 0.25
    diff_strong_similarity: float = 0.95
    diff_min_context_tokens: int = 3
    ocr_score_weight: float = 0.55
    header_score_weight: float = 0.20
    text_score_weight: float = 0.15
    roi_score_weight: float = 0.10
    unanchored_score_cap: float = 0.75
    weak_score_cap: float = 0.55
    fallback_score: float = 0.25


ROOT = Path(__file__).resolve().parents[2]
RUNTIME_FOLDERS = ("cache/tts", "cache/ocr", "cache/preview", "cache/temp",
                   "logs", "projects", "output")


def ensure_runtime_dirs(root: Path = ROOT) -> None:
    for folder in RUNTIME_FOLDERS:
        (root / folder).mkdir(parents=True, exist_ok=True)
