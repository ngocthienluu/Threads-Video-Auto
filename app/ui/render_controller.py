"""Cancellable export worker; never runs TTS or edits narration automatically."""
from copy import deepcopy
from threading import Event
from pathlib import Path
from PySide6.QtCore import QObject, Slot, QThreadPool, QTimer
from PySide6.QtWidgets import QFileDialog
from app.core.config import ROOT
from app.renderer.ffmpeg_renderer import FFmpegRenderer
from app.renderer.media import RenderError
from app.utils.workers import Worker

class RenderController(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.renderer = FFmpegRenderer()
        self.busy = False
        self.close_when_finished = False
        self.cancel_event = Event()
        self.failure = ""

    def start(self, checked=False, output=None):
        w = self.window
        if self.busy or w.ocr_controller.busy or w.tts_controller.busy:return
        if output is None:
            filename, _ = QFileDialog.getSaveFileName(w,"Export MP4",str(ROOT / "output/video.mp4"),"MP4 video (*.mp4)")
            if not filename:return
            output = Path(filename)
            if not output.suffix:output = output.with_suffix(".mp4")
        self.busy = True
        self.cancel_event = Event()
        self.failure = ""
        self.snapshot = deepcopy(w.manager.project)
        w.centralWidget().setEnabled(False)
        w.menuBar().setEnabled(False)
        w.cancel_render_button.setEnabled(True)
        w.progress.setValue(0)
        w.statusBar().showMessage("Checking media / exporting MP4...")
        def operation(progress,status):
            return self.renderer.render(self.snapshot,Path(output),progress,self.cancel_event,overwrite=True)
        self.worker = Worker(operation,expected_errors=(RenderError,ValueError,OSError))
        self.worker.signals.progress.connect(w.progress.setValue)
        self.worker.signals.error.connect(self.error)
        self.worker.signals.finished.connect(self.finish)
        QThreadPool.globalInstance().start(self.worker)

    @Slot(str)
    def error(self,message):self.failure = message

    def cancel(self):
        self.cancel_event.set()
        self.window.statusBar().showMessage("Cancelling export...")

    @Slot(object)
    def finish(self,result):
        w = self.window
        self.busy = False
        self.worker = None
        w.centralWidget().setEnabled(True)
        w.menuBar().setEnabled(True)
        w.cancel_render_button.setEnabled(False)
        if result:
            w.statusBar().showMessage("Export complete: " + str(result))
        elif self.cancel_event.is_set():
            w.statusBar().showMessage("Export cancelled. Previous output kept.")
        else:w.error(self.failure or "Export failed.")
        if self.close_when_finished:
            self.close_when_finished=False
            QTimer.singleShot(0,w.close)
