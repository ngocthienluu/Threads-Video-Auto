"""Measured AUTO clips. Manual timing/trim can be added without changing canvas geometry."""
from dataclasses import dataclass
from enum import Enum
from app.core.editor_objects import ObjectType

class TimingMode(str,Enum):
    AUTO="AUTO"
    MANUAL="MANUAL"  # Reserved: no manual timing UI or renderer support yet.

TRACKS=("Gameplay","Comments","Voice","Music","Meme / SFX","Watermark")

@dataclass(frozen=True)
class TimelineClip:
    object_id: str
    track: str
    start_time: float
    end_time: float
    label: str
    source_item_id: str = ""
    timing_mode: TimingMode = TimingMode.AUTO
    @property
    def duration(self):return self.end_time-self.start_time

@dataclass
class TimelineScale:
    pixels_per_second: float = 80.0
    def time_to_x(self,time):return max(0,time)*self.pixels_per_second
    def x_to_time(self,x):return max(0,x)/self.pixels_per_second

def clips_from_project(project,timeline):
    if timeline is None:return []
    clips=[];total=timeline.total_duration
    objects=project.editor_objects
    comments={o.source_item_id:o for o in objects if o.type==ObjectType.COMMENT_IMAGE}
    for obj in objects:
        if not obj.visible or obj.deleted:continue
        if obj.type==ObjectType.BACKGROUND:
            clips.append(TimelineClip(obj.id,"Gameplay",0,total,"Gameplay"))
        if obj.type==ObjectType.WATERMARK and project.watermark_settings.enabled:
            clips.append(TimelineClip(obj.id,"Watermark",0,total,"Watermark"))
    for segment in timeline.segments:
        obj=comments.get(segment.item_id)
        if obj and obj.visible and not obj.deleted:
            clips.append(TimelineClip(obj.id,"Comments",segment.start_time,segment.end_time,obj.name,segment.item_id))
        clips.append(TimelineClip(obj.id if obj else "","Voice",segment.voice_start,segment.voice_end,"Narration",segment.item_id))
    if project.music_settings.enabled:clips.append(TimelineClip("","Music",0,total,"Music"))
    return clips
