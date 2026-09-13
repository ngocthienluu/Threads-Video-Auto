"""Model/canvas/inspector coordination and undo, isolated from the OCR/TTS pipeline."""
from dataclasses import asdict
from PySide6.QtCore import Qt
from PySide6.QtGui import QAction, QKeySequence, QUndoCommand, QUndoStack
from PySide6.QtWidgets import QHBoxLayout,QPushButton,QCheckBox,QTreeWidgetItem,QGraphicsView,QDoubleSpinBox
from app.core.editor_scene import ensure_objects, sync_timings, default_comment, watermark_image
from app.core.editor_objects import ObjectType
from app.core.models import now
from app.ui.object_inspector import ObjectInspector
from app.ui.timeline.timeline_widget import TimelineWidget
from app.core.editor_timeline import clips_from_project

class ObjectCommand(QUndoCommand):
    def __init__(self,controller,identity,before,after,label):
        super().__init__(label);self.controller=controller;self.identity=identity
        self.before={k:before[k] for k in after if before[k]!=after[k]};self.after={k:after[k] for k in self.before}
    def redo(self):self.controller.apply(self.identity,self.after)
    def undo(self):self.controller.apply(self.identity,self.before)

class EditorController:
    def __init__(self,window):
        self.window=window;self.project=None;self.selected_id="";self.time=0.0;self.timeline=None;self.binding=False;self.selecting=False
        self.undo=QUndoStack(window)
        self.timeline_widget=TimelineWidget();window.timeline_layout.addWidget(self.timeline_widget)
        self.timeline_widget.scrubbed.connect(self.scrub)
        self.timeline_widget.clip_selected.connect(self.select_clip)
        self.inspector=ObjectInspector();window.inspector_layout.insertWidget(1,self.inspector)
        self.inspector.edited.connect(self.edit_field);self.inspector.reset_requested.connect(self.reset_transform)
        controls=QHBoxLayout();window.inspector_layout.addLayout(controls)
        for text,delta in (("Send Backward",-1),("Bring Forward",1)):
            button=QPushButton(text);button.clicked.connect(lambda checked=False,d=delta:self.reorder(d));controls.addWidget(button)
        window.layers.itemSelectionChanged.connect(self.layer_selected);window.layers.itemChanged.connect(self.layer_changed)
        bar=QHBoxLayout();window.canvas_tabs.parentWidget().layout().insertLayout(0,bar)
        for text,callback in (("Select",lambda:self.pan(False)),("Pan",lambda:self.pan(True)),("Reset View",window.preview.fit),("Fit",window.preview.fit),("Delete",self.delete_object)):
            button=QPushButton(text);button.clicked.connect(callback);bar.addWidget(button)
        self.safe=QCheckBox("Safe area");self.snap=QCheckBox("Snap");bar.addWidget(self.safe);bar.addWidget(self.snap)
        self.safe.toggled.connect(lambda v:self.setting("show_safe_area",v));self.snap.toggled.connect(lambda v:self.setting("snap_enabled",v))
        self.threshold=QDoubleSpinBox();self.threshold.setRange(0,100);self.threshold.setSuffix(" px");self.threshold.setToolTip("Snap threshold in logical pixels");self.threshold.setMaximumWidth(95)
        self.threshold.valueChanged.connect(lambda v:self.setting("snap_threshold",v));bar.addWidget(self.threshold)
        menu=window.menuBar().addMenu("Edit")
        action=self.undo.createUndoAction(window,"Undo");action.setShortcut(QKeySequence.StandardKey.Undo);menu.addAction(action)
        action=self.undo.createRedoAction(window,"Redo");action.setShortcuts([QKeySequence("Ctrl+Shift+Z"),QKeySequence("Ctrl+Y")]);menu.addAction(action)
        save=QAction("Save project",window);save.setShortcut(QKeySequence.StandardKey.Save);save.triggered.connect(window.save_project);window.addAction(save)
        delete=QAction("Delete object",window.preview);delete.setShortcut(QKeySequence("Delete"));delete.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut);delete.triggered.connect(self.delete_object);window.preview.addAction(delete)
        window.preview.object_changed.connect(self.changed);window.preview.selected.connect(self.select_object)
        window.preview.gesture_finished.connect(lambda identity,before,after:self.commit(identity,before,after,"Move / Resize object"))

    def pan(self,enabled):
        self.window.preview.setInteractive(not enabled)
        self.window.preview.setDragMode(QGraphicsView.DragMode.ScrollHandDrag if enabled else QGraphicsView.DragMode.NoDrag)

    def find(self,identity=None):
        return next((o for o in self.project.editor_objects if o.id==(identity or self.selected_id)),None) if self.project else None

    def refresh(self,timeline):
        w=self.window
        if self.project is not w.manager.project:
            self.undo.clear();self.selected_id="";self.time=0.0;w.preview.cache.clear();w.preview.select_object("");w.scenes.thumbnails.clear()
        self.project=w.manager.project
        ensure_objects(self.project);sync_timings(self.project,timeline);self.timeline=timeline
        self.time=min(self.time,timeline.total_duration) if timeline else 0.0
        w.preview.set_project(self.project)
        w.preview.show_state(self.time,w.item.id if w.item else None,timeline is not None)
        for widget,key in ((self.safe,"show_safe_area"),(self.snap,"snap_enabled"),(self.threshold,"snap_threshold")):
            widget.blockSignals(True)
            if key=="snap_threshold":widget.setValue(getattr(self.project,key))
            else:widget.setChecked(getattr(self.project,key))
            widget.blockSignals(False)
        self.refresh_layers();self.inspector.bind(self.find())
        self.timeline_widget.set_data(clips_from_project(self.project,timeline),timeline.total_duration if timeline else 0.0)
        self.timeline_widget.set_time(self.time)

    def changed(self,identity):
        w=self.window;w.manager.dirty=True;w.manager.project.updated_at=now()
        name=w.manager.path.stem if w.manager.path else w.manager.project.name
        w.project_title.setText(name+" *");w.setWindowTitle("* "+name+" - Threads Video Studio")
        self.inspector.bind(self.find())

    def apply(self,identity,values):
        obj=self.find(identity)
        if not obj:return
        item=self.window.preview.objects.get(identity)
        if item:item.prepareGeometryChange()
        for key,value in values.items():setattr(obj,key,value)
        self.window.preview.set_project(self.project)
        self.window.preview.show_state(self.time,self.window.item.id if self.window.item else None,self.timeline is not None)
        self.changed(identity);self.refresh_layers();self.select_object(identity if not obj.deleted else "")
        self.timeline_widget.set_data(clips_from_project(self.project,self.timeline),self.timeline.total_duration if self.timeline else 0.0)

    def commit(self,identity,before,after,label):
        if before!=after:self.undo.push(ObjectCommand(self,identity,before,after,label))

    def edit_field(self,key,value):
        obj=self.find()
        if not obj or obj.locked or obj.deleted or obj.type==ObjectType.BACKGROUND:return
        before=asdict(obj);after=dict(before)
        if key=="font_size":
            try:w,h=watermark_image(self.project,int(value)).size
            except (OSError,ValueError) as exc:self.window.error(exc);return
            after.update(font_size=int(value),width=float(w),height=float(h))
        elif key in ("width","height"):
            factor=value/getattr(obj,key);after.update(width=obj.width*factor,height=obj.height*factor)
        elif key=="scale_x":after.update(scale_x=value,scale_y=value)
        else:after[key]=value
        if max(after["width"]*after["scale_x"],after["height"]*after["scale_y"])>8192:
            self.inspector.bind(obj);return
        self.commit(obj.id,before,after,"Change "+key)

    def reset_transform(self):
        obj=self.find()
        if not obj or obj.locked:return
        before=asdict(obj);after=dict(before)
        if obj.type==ObjectType.COMMENT_IMAGE:
            item=next(i for s in self.project.scenes for i in s.items if i.id==obj.source_item_id)
            default=default_comment(self.project,item)
            after.update(x=default.x,y=default.y,width=default.width,height=default.height)
        else:
            try:w,h=watermark_image(self.project).size
            except (OSError,ValueError) as exc:self.window.error(exc);return
            after.update(x=(1080-w)/2,y=60.0,width=float(w),height=float(h),font_size=self.project.watermark_settings.size)
        after.update(scale_x=1.0,scale_y=1.0,rotation=0.0)
        self.commit(obj.id,before,after,"Reset transform")

    def setting(self,key,value):
        if not self.project:return
        setattr(self.project,key,value);self.changed("");self.window.preview.viewport().update()

    def select_object(self,identity,sync_scene=True):
        if self.selecting:return
        obj=self.find(identity) if identity else None
        if obj and obj.deleted:identity="";obj=None
        if obj and obj.source_item_id:
            if sync_scene:self.select_scene_item(obj.source_item_id)
            if self.timeline and not obj.start_time <= self.time < obj.end_time:
                self.time=obj.start_time
                self.timeline_widget.set_time(self.time)
                self.window.preview.show_state(self.time,obj.source_item_id,True)
        self.selected_id=identity;self.window.preview.select_object(identity);obj=self.find()
        self.window.inspector_hint.setText(obj.name if obj else "Select an object on the canvas")
        self.inspector.bind(obj)
        self.binding=True
        self.window.layers.clearSelection()
        for n in range(self.window.layers.topLevelItemCount()):
            row=self.window.layers.topLevelItem(n)
            if row.data(0,Qt.ItemDataRole.UserRole)==identity:row.setSelected(True)
        self.binding=False

    def select_item(self,item):
        if not self.project or self.selecting:return
        if item is None and self.window.scene:item=self.window.scene.items[0]
        obj=next((o for o in self.project.editor_objects if item and o.source_item_id==item.id and not o.deleted),None)
        if obj:
            if self.timeline:
                self.time=obj.start_time;self.timeline_widget.set_time(self.time)
            self.select_object(obj.id,sync_scene=False)
        self.window.preview.show_state(self.time,item.id if item else None,self.timeline is not None)

    def select_scene_item(self,item_id):
        tree=self.window.scenes
        self.selecting=True
        try:
            for n in range(tree.topLevelItemCount()):
                parent=tree.topLevelItem(n)
                for k in range(parent.childCount()):
                    row=parent.child(k);_,item=row.data(0,Qt.ItemDataRole.UserRole)
                    if item.id==item_id:
                        tree.setCurrentItem(row)
                        return
        finally:self.selecting=False

    def scrub(self,time):
        if not self.timeline:return
        self.time=max(0,min(self.timeline.total_duration,time))
        self.timeline_widget.set_time(self.time)
        active=next((o for o in self.project.editor_objects if o.source_item_id and o.active_at(self.time)),None)
        if active:self.select_scene_item(active.source_item_id)
        self.window.preview.show_state(self.time,ready=True)
        selected=self.find()
        if active and (selected is None or selected.source_item_id):self.select_object(active.id)
        elif selected and selected.source_item_id and not selected.active_at(self.time):self.select_object("")
        self.window.statusBar().showMessage(f"Current time {self.time:.2f}s | Layout preview | Timeline zoom {self.timeline_widget.pixels_per_second:.0f} px/s")

    def select_clip(self,clip):
        if clip.source_item_id:self.select_scene_item(clip.source_item_id)
        if clip.object_id:self.select_object(clip.object_id)
        elif clip.track=="Music":
            self.window.right_tabs.setCurrentIndex(1);self.window.settings.sections.setCurrentIndex(2)

    def refresh_layers(self):
        self.binding=True;tree=self.window.layers;tree.blockSignals(True)
        objects=sorted((o for o in self.project.editor_objects if not o.deleted),key=lambda o:o.z_index,reverse=True)
        identities=[tree.topLevelItem(n).data(0,Qt.ItemDataRole.UserRole) for n in range(tree.topLevelItemCount())]
        # Never delete an item while Qt is emitting itemChanged for its checkbox.
        if identities != [o.id for o in objects]:
            tree.clear()
            for obj in objects:
                row=QTreeWidgetItem([obj.name,"",""]);row.setData(0,Qt.ItemDataRole.UserRole,obj.id)
                row.setFlags(row.flags()|Qt.ItemFlag.ItemIsUserCheckable);tree.addTopLevelItem(row)
        for n,obj in enumerate(objects):
            row=tree.topLevelItem(n);row.setText(0,obj.name)
            row.setCheckState(1,Qt.CheckState.Checked if obj.visible else Qt.CheckState.Unchecked)
            if obj.type==ObjectType.BACKGROUND:
                row.setData(2,Qt.ItemDataRole.CheckStateRole,None);row.setText(2,"Fixed")
                row.setToolTip(2,"Background fills the video; geometry editing is reserved for a later version.")
            else:
                row.setText(2,"");row.setCheckState(2,Qt.CheckState.Checked if obj.locked else Qt.CheckState.Unchecked)
            row.setSelected(obj.id==self.selected_id)
        tree.setColumnWidth(0,170);tree.setColumnWidth(1,55);tree.setColumnWidth(2,55)
        tree.blockSignals(False);self.binding=False

    def layer_selected(self):
        if self.binding:return
        rows=self.window.layers.selectedItems()
        if rows:self.select_object(rows[0].data(0,Qt.ItemDataRole.UserRole))

    def layer_changed(self,row,column):
        if self.binding or column not in (1,2):return
        obj=self.find(row.data(0,Qt.ItemDataRole.UserRole))
        if not obj:return
        if obj.type==ObjectType.BACKGROUND and column==2:self.refresh_layers();return
        before=asdict(obj);after=dict(before);after["visible" if column==1 else "locked"]=row.checkState(column)==Qt.CheckState.Checked
        self.commit(obj.id,before,after,"Change layer")

    def reorder(self,delta):
        obj=self.find()
        if not obj or obj.locked:return
        others=[o.z_index for o in self.project.editor_objects if not o.deleted and o.id!=obj.id and o.type!=ObjectType.BACKGROUND]
        values=[z for z in others if (z-obj.z_index)*delta>=0]
        target=(min(values)+1 if delta>0 else max(1,max(values)-1)) if values else max(1,obj.z_index+delta)
        before=asdict(obj);after=dict(before,z_index=target);self.commit(obj.id,before,after,"Reorder layer")

    def delete_object(self):
        obj=self.find()
        if not obj or obj.locked or obj.type==ObjectType.BACKGROUND:return
        before=asdict(obj);self.commit(obj.id,before,dict(before,deleted=True),"Delete overlay")
        self.window.statusBar().showMessage("Overlay deleted; narration kept. Undo restores the overlay.")
