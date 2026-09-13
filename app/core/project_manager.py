"""Authoring use cases, edit safety and project persistence."""
import json
import logging
import os
from pathlib import Path
import tempfile

from app.core.models import ItemRole, Project, Scene, SceneItem, SceneType, now
from app.core.text_cleaner import clean_text

log = logging.getLogger(__name__)


class ProjectManager:
    def __init__(self, project: Project | None = None):
        self.project = project or Project()
        self.path: Path | None = None
        self.dirty = False

    def changed(self) -> None:
        self.dirty = True
        self.project.updated_at = now()
        for scene in self.project.scenes:
            for item in scene.items:
                item.start_time = item.end_time = 0.0
                item.timeline_status = "pending"

    def add_single(self, image: str) -> Scene:
        scene = Scene(items=[SceneItem(original_image_path=image)])
        self.project.scenes.append(scene)
        self.changed()
        return scene

    def add_thread(self, images: list[str]) -> Scene:
        if not images:
            raise ValueError("Choose a question screenshot first.")
        scene = Scene(scene_type=SceneType.THREAD, items=[
            SceneItem(original_image_path=image, role=ItemRole.QUESTION if i == 0 else ItemRole.REPLY)
            for i, image in enumerate(images)])
        self.project.scenes.append(scene)
        self.changed()
        return scene

    def add_thread_item(self, scene: Scene, image: str) -> SceneItem:
        if scene.scene_type != SceneType.THREAD:
            raise ValueError("Select a Thread scene to add a reply.")
        item = SceneItem(original_image_path=image, role=ItemRole.REPLY)
        scene.items.append(item)
        self.changed()
        return item

    def edit_ocr(self, item: SceneItem, text: str) -> None:
        if item.ocr_text != text:
            item.ocr_text = item.display_text = text
            item.ocr_status = "manual"
            self.changed()

    def edit_body(self, item: SceneItem, text: str) -> None:
        from app.core.content_pipeline import refresh_scene
        if item.body_text != text or not item.body_text_is_manual:
            item.body_text = item.full_body_text = item.display_text = text
            item.body_text_is_manual = True
            refresh_scene(self, next(scene for scene in self.project.scenes if item in scene.items))
            self.changed()

    def apply_detection(self, item, ocr, extraction, replace_body=False):
        from app.core.content_pipeline import apply_detection
        apply_detection(self, item, ocr, extraction, replace_body)

    def refresh_content(self, item):
        from app.core.content_pipeline import refresh_scene
        refresh_scene(self, next(scene for scene in self.project.scenes if item in scene.items))

    def apply_ocr(self, item: SceneItem, text: str, replace_existing: bool = False) -> bool:
        """Apply reviewed job results without overwriting prior text implicitly."""
        if (item.ocr_text or item.ocr_status == "manual") and not replace_existing:
            return False
        if not text.strip():
            raise ValueError("OCR returned no text; previous text was kept.")
        item.ocr_text = item.display_text = text
        item.ocr_status = "done"
        self.changed()
        # OCR is review-first: no TTS overwrite or cumulative reply guessing.
        return True

    def use_ocr_selection(self, item: SceneItem, text: str, overwrite_manual: bool = False) -> bool:
        if item.tts_text_is_manual and not overwrite_manual:
            return False
        if not text.strip():
            raise ValueError("Select the comment/reply text in the OCR editor first.")
        self.edit_tts(item, clean_text(text, self.project.cleaner_settings), manual=True)
        return True

    def edit_tts(self, item: SceneItem, text: str, manual: bool = True) -> None:
        if item.tts_text != text or item.tts_text_is_manual != manual:
            item.tts_text = text
            item.tts_text_is_manual = manual
            item.invalidate_audio()
            self.changed()

    def prepare_tts(self, item: SceneItem, overwrite_manual: bool = False) -> bool:
        if item.tts_text_is_manual and not overwrite_manual:
            return False
        if item.extraction_method != "pending" or item.body_text_is_manual:
            if not item.new_body_text.strip():
                raise ValueError("No new comment text. Review detected text before creating narration.")
            self.edit_tts(item, clean_text(item.new_body_text, self.project.cleaner_settings), manual=False)
            return True
        if item.role == ItemRole.REPLY:
            raise ValueError("For cumulative Thread screenshots, enter only the new reply in TTS Text manually.")
        self.edit_tts(item, clean_text(item.ocr_text, self.project.cleaner_settings), manual=False)
        return True

    def set_voice(self, item: SceneItem, voice_id: str, speed: float = 1.0) -> None:
        if speed <= 0:
            raise ValueError("Voice speed must be positive.")
        if (item.voice_id, item.voice_speed) != (voice_id, speed):
            item.voice_id, item.voice_speed = voice_id, speed
            # Keep the previous recording for listening/recovery, but never time
            # the newly selected voice using an older recording.
            item.tts_status = "pending"
            self.changed()

    def set_default_voice(self, voice_id, name):
        if (self.project.default_voice_id, self.project.default_voice_name) != (voice_id, name):
            self.project.default_voice_id, self.project.default_voice_name = voice_id, name
            for scene in self.project.scenes:
                for item in scene.items:
                    if not item.voice_id:
                        item.tts_status = "pending"
            self.changed()

    def set_tts_model(self, model):
        if self.project.tts_model_id != model:
            self.project.tts_model_id = model
            for scene in self.project.scenes:
                for item in scene.items:
                    item.tts_status = "pending"
            self.changed()

    def apply_narration(self, item, narration):
        import math
        if not Path(narration.path).is_file() or not math.isfinite(narration.duration) or narration.duration <= 0:
            raise ValueError("Narration requires an existing audio file and measured duration.")
        item.audio_path, item.audio_duration = narration.path, narration.duration
        item.tts_status = "done"
        self.changed()
        self.refresh_timeline()

    def refresh_timeline(self):
        from app.core.timeline import build_timeline
        items = [item for scene in self.project.scenes for item in scene.items]
        for item in items:
            item.timeline_status = "pending"
            item.start_time = item.end_time = 0.0
        if not items or any(not item.audio_path or not Path(item.audio_path).is_file() for item in items):
            return None
        try:
            timeline = build_timeline(self.project)
        except ValueError:
            return None
        for item, segment in zip(items, timeline.segments):
            item.start_time, item.end_time = segment.start_time, segment.end_time
            item.timeline_status = "done"
        return timeline

    @staticmethod
    def _roles(scene: Scene) -> None:
        for i, item in enumerate(scene.items):
            item.role = ItemRole.SINGLE if scene.scene_type == SceneType.SINGLE else ItemRole.QUESTION if i == 0 else ItemRole.REPLY

    def delete(self, scene: Scene, item: SceneItem | None = None) -> None:
        if item is None or len(scene.items) == 1:
            self.project.scenes.remove(scene)
        else:
            scene.items.remove(item)
            self._roles(scene)
            from app.core.content_pipeline import refresh_scene
            refresh_scene(self, scene)
        self.changed()

    def move(self, scene: Scene, item: SceneItem | None, delta: int) -> None:
        sequence = scene.items if item else self.project.scenes
        index = sequence.index(item or scene)
        target = index + delta
        if 0 <= target < len(sequence):
            sequence[index], sequence[target] = sequence[target], sequence[index]
            self._roles(scene)
            from app.core.content_pipeline import refresh_scene
            refresh_scene(self, scene)
            self.changed()

    def save(self, path: Path) -> None:
        path = path.resolve()
        from app.core.editor_scene import ensure_objects, sync_timings
        ensure_objects(self.project)
        sync_timings(self.project,self.refresh_timeline())
        data = self.project.to_dict()
        Project.from_dict(data)  # Validate before writing anything.
        _map_paths(data, lambda value: _relative(value, path.parent))
        temp_path = None
        try:
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent,
                                             suffix=".tmp", delete=False) as stream:
                temp_path = Path(stream.name)
                json.dump(data, stream, ensure_ascii=False, indent=2, allow_nan=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_path, path)
        finally:
            if temp_path and temp_path.exists():
                temp_path.unlink()
        self.path, self.dirty = path, False
        log.info("Project saved")

    def load(self, path: Path) -> list[str]:
        path = path.resolve()
        try:
            data = json.loads(path.read_text(encoding="utf-8-sig"))
            candidate = Project.from_dict(data)
            data = candidate.to_dict()
            _map_paths(data, lambda value: str((path.parent / value).resolve()))
            candidate = Project.from_dict(data)
        except (ValueError, TypeError, KeyError, RecursionError) as exc:
            raise ValueError("Invalid project JSON: " + str(exc)) from exc
        from app.core.editor_scene import ensure_objects
        ensure_objects(candidate)
        missing = []
        _map_paths(data, lambda value: missing.append(value) or value if not Path(value).is_file() else value)
        self.project, self.path, self.dirty = candidate, path, False
        log.info("Project loaded; missing media: %d", len(missing))
        return list(dict.fromkeys(missing))


def _relative(value: str, base: Path) -> str:
    try:
        return Path(os.path.relpath(Path(value).resolve(), base)).as_posix()
    except ValueError:  # Different Windows drives.
        return str(Path(value).resolve())


def _map_paths(data: dict, transform) -> None:
    for key, value in data.items():
        if key in {"original_image_path", "audio_path", "file", "font"} and isinstance(value, str) and value:
            data[key] = transform(value)
        elif isinstance(value, dict):
            _map_paths(value, transform)
        elif isinstance(value, list):
            for entry in value:
                if isinstance(entry, dict):
                    _map_paths(entry, transform)
