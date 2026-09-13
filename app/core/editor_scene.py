"""Object creation/migration and AUTO timing; no widget coordinates."""
from pathlib import Path
from PIL import Image, ImageOps, ImageDraw, ImageFont
import os
from app.core.editor_objects import EditorObject, ObjectType, CANVAS_WIDTH as W, CANVAS_HEIGHT as H

def watermark_image(project, size=None):
    cfg = project.watermark_settings
    font_path = cfg.font or (str(Path(os.environ["WINDIR"])/"Fonts/segoeui.ttf") if os.environ.get("WINDIR") else "DejaVuSans.ttf")
    font = ImageFont.truetype(font_path, size or cfg.size)
    box = font.getbbox(cfg.text or " ")
    image = Image.new("RGBA", (max(1,box[2]-box[0]),max(1,box[3]-box[1])))
    ImageDraw.Draw(image).text((-box[0],-box[1]),cfg.text,font=font,fill="white")
    return image

def default_comment(project, item):
    try:
        with Image.open(item.original_image_path) as raw:
            im = ImageOps.exif_transpose(raw)
            iw,ih = im.size
    except (OSError,ValueError):
        iw,ih = 3,1
    v = project.video_settings
    scale = min(W*v.comment_max_width_ratio/iw,H*.9/ih)
    w,h = iw*scale,ih*scale
    return EditorObject(name=Path(item.original_image_path).name,source_item_id=item.id,
                        x=(W-w)/2,y=max(0,min(H-h,H*v.comment_y_ratio-h/2)),width=w,height=h)

def ensure_objects(project):
    items = {i.id:i for s in project.scenes for i in s.items}
    project.editor_objects[:] = [o for o in project.editor_objects if o.type != ObjectType.COMMENT_IMAGE or o.source_item_id in items]
    linked = {o.source_item_id for o in project.editor_objects if o.type == ObjectType.COMMENT_IMAGE}
    for item in items.values():
        if item.id not in linked: project.editor_objects.append(default_comment(project,item))
    if not any(o.type == ObjectType.BACKGROUND for o in project.editor_objects):
        project.editor_objects.append(EditorObject(type=ObjectType.BACKGROUND,name="Gameplay (export)",width=W,height=H,z_index=0,locked=True))
    if not any(o.type == ObjectType.WATERMARK for o in project.editor_objects):
        cfg = project.watermark_settings
        try: w,h = watermark_image(project).size
        except (OSError,ValueError): w,h = max(1,len(cfg.text)*cfg.size*.6),cfg.size
        x = cfg.x if cfg.position == "custom" else (W-w)/2
        y = H-h-cfg.y if cfg.position == "bottom-center" else cfg.y
        project.editor_objects.append(EditorObject(type=ObjectType.WATERMARK,name="Watermark",x=x,y=y,width=w,height=h,
                                                   opacity=cfg.opacity,z_index=300,font_size=cfg.size))

def sync_timings(project, timeline):
    segments = {s.item_id:s for s in timeline.segments} if timeline else {}
    total = timeline.total_duration if timeline else 0.0
    for obj in project.editor_objects:
        seg = segments.get(obj.source_item_id)
        obj.start_time = seg.start_time if seg else 0.0
        obj.end_time = seg.end_time if seg else total if obj.type in (ObjectType.BACKGROUND,ObjectType.WATERMARK) else 0.0

def object_image(project,obj):
    if obj.type == ObjectType.WATERMARK: return watermark_image(project,obj.font_size)
    item = next(i for s in project.scenes for i in s.items if i.id == obj.source_item_id)
    with Image.open(item.original_image_path) as image: return ImageOps.exif_transpose(image).convert("RGBA")
