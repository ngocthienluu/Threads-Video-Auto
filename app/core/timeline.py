"""Duration-driven timeline foundation. Does not probe audio or mutate the UI."""
from dataclasses import dataclass
import logging
import math
from app.core.models import Project


@dataclass(frozen=True)
class Segment:
    scene_id: str
    item_id: str
    image_path: str
    start_time: float
    voice_start: float
    voice_end: float
    end_time: float


@dataclass(frozen=True)
class Timeline:
    segments: tuple[Segment, ...]
    total_duration: float


def build_timeline(project: Project) -> Timeline:
    project.validate()
    config = project.timing_settings
    segments = []
    cursor = 0.0
    for scene_index, scene in enumerate(project.scenes):
        if scene_index:
            cursor += config.scene_gap
        for item in scene.items:
            if not math.isfinite(item.audio_duration) or item.audio_duration <= 0 or not item.audio_path or item.tts_status != "done":
                raise ValueError("Timeline needs non-stale audio and a measured positive duration for every item.")
            voice_start = cursor + config.voice_pre_padding
            voice_end = voice_start + item.audio_duration
            end = voice_end + config.voice_post_padding
            segments.append(Segment(scene.id, item.id, item.original_image_path,
                                    cursor, voice_start, voice_end, end))
            cursor = end
    logging.getLogger(__name__).info("Timeline built: %d segments", len(segments))
    return Timeline(tuple(segments), cursor)
