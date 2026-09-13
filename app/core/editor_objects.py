"""Persisted, Qt-independent geometry in 1080 x 1920 logical coordinates."""
from dataclasses import dataclass, field
from enum import Enum
from uuid import uuid4
import math

CANVAS_WIDTH, CANVAS_HEIGHT = 1080, 1920

class ObjectType(str, Enum):
    BACKGROUND = "BACKGROUND"
    COMMENT_IMAGE = "COMMENT_IMAGE"
    WATERMARK = "WATERMARK"
    MEME = "MEME"
    TEXT = "TEXT"
    IMAGE = "IMAGE"

@dataclass
class EditorObject:
    id: str = field(default_factory=lambda: uuid4().hex)
    type: ObjectType = ObjectType.COMMENT_IMAGE
    name: str = "Comment"
    source_item_id: str = ""
    x: float = 0.0
    y: float = 0.0
    width: float = 100.0
    height: float = 100.0
    scale_x: float = 1.0
    scale_y: float = 1.0
    rotation: float = 0.0
    opacity: float = 1.0
    z_index: int = 100
    visible: bool = True
    deleted: bool = False
    locked: bool = False
    start_time: float = 0.0
    end_time: float = 0.0
    font_size: int = 40

    def validate(self):
        values = (self.x,self.y,self.width,self.height,self.scale_x,self.scale_y,
                  self.rotation,self.opacity,self.start_time,self.end_time)
        if not all(math.isfinite(v) for v in values):
            raise ValueError("Object geometry must be finite.")
        if min(self.width,self.height,self.scale_x,self.scale_y,self.font_size) <= 0:
            raise ValueError("Object dimensions and scale must be positive.")
        if not 0 <= self.opacity <= 1 or not 0 <= self.start_time <= self.end_time:
            raise ValueError("Invalid object opacity or timing.")
        if max(self.width*self.scale_x,self.height*self.scale_y) > 8192:
            raise ValueError("Object size exceeds 8192 logical pixels.")

    def active_at(self, seconds):
        return self.visible and not self.deleted and self.start_time <= seconds < self.end_time
