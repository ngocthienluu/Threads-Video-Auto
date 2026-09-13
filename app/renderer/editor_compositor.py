"""Rasterize each static asset once; FFmpeg remains responsible for video frames."""
from dataclasses import dataclass
from PIL import Image
from app.core.editor_scene import object_image

@dataclass(frozen=True)
class RenderOverlay:
    input_index: int
    x: int
    y: int
    start_time: float
    end_time: float
    z_index: int

def prepare_overlay(project,obj):
    image=object_image(project,obj)
    sx,sy=project.video_settings.width/1080,project.video_settings.height/1920
    width=max(1,round(obj.width*obj.scale_x*sx));height=max(1,round(obj.height*obj.scale_y*sy))
    image=image.resize((width,height),Image.Resampling.LANCZOS)
    if obj.opacity!=1:image.putalpha(image.getchannel("A").point(lambda value:round(value*obj.opacity)))
    # Qt uses clockwise positive angles around the displayed rectangle center.
    if obj.rotation:image=image.rotate(-obj.rotation,Image.Resampling.BICUBIC,expand=True)
    x=round(obj.x*sx+(width-image.width)/2)
    y=round(obj.y*sy+(height-image.height)/2)
    return image,x,y
