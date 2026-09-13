"""Connect authoring model and canvas without moving pipeline rules into widgets."""
from app.core.editor_scene import ensure_objects, sync_timings
from app.core.models import now

class EditorController:
    def __init__(self,window):
        self.window=window
        self.project=None
        self.selected_id=""
        self.time=0.0
        self.timeline=None
        window.preview.object_changed.connect(self.changed)
        window.preview.selected.connect(self.select_object)

    def refresh(self,timeline):
        w=self.window
        self.project=w.manager.project
        ensure_objects(self.project)
        sync_timings(self.project,timeline)
        self.timeline=timeline
        w.preview.set_project(self.project)
        w.preview.show_state(self.time,w.item.id if w.item else None,timeline is not None)

    def changed(self,identity):
        w=self.window
        w.manager.dirty=True
        w.manager.project.updated_at=now()
        w.project_title.setText(w.manager.project.name+" *")
        w.setWindowModified(True)

    def select_object(self,identity):
        self.selected_id=identity
        self.window.preview.select_object(identity)
        obj=next((o for o in self.project.editor_objects if o.id==identity),None) if self.project else None
        self.window.inspector_hint.setText(obj.name if obj else "Select an object on the canvas")

    def select_item(self,item):
        if not self.project:return
        obj=next((o for o in self.project.editor_objects if item and o.source_item_id==item.id),None)
        if obj:
            if self.timeline:self.time=obj.start_time
            self.select_object(obj.id)
        self.window.preview.show_state(self.time,item.id if item else None,self.timeline is not None)
