"""Sequential text-generation jobs; all project writes happen on the Qt thread."""
from copy import deepcopy
from pathlib import Path
from threading import Event
from PySide6.QtCore import QObject, QThreadPool, QTimer, Slot
from app.services.ocr.errors import OCRError
from app.services.ocr.jobs import OCRJob, DetectionPayload
from app.services.ocr.service import OCRService
from app.utils.workers import Worker


class OCRController(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.worker = None
        self.provider = OCRService()
        window.settings.set_ocr_engine(self.provider.settings.ocr_provider)
        window.settings.ocr_engine_changed.connect(self.select_engine)
        self.cancel_event = Event()
        self.close_when_finished = False
        self._busy = False

    @property
    def busy(self):
        return self._busy

    @Slot(str)
    def select_engine(self, name):
        if self.busy:
            self.window.settings.set_ocr_engine(self.provider.settings.ocr_provider)
            return
        try:
            self.provider.select_provider(name)
        except OCRError as exc:
            self.window.settings.set_ocr_engine(self.provider.settings.ocr_provider)
            self.window.error(str(exc))
            return
        self.window.statusBar().showMessage(f"OCR engine: {name}. Bấm READ IMAGE để đọc lại ảnh; text sửa tay vẫn được giữ.")

    def start(self, force=False, all_items=False):
        w = self.window
        if getattr(w, "render_controller", None) and w.render_controller.busy:
            return
        if self.busy or (hasattr(w, "tts_controller") and w.tts_controller.busy):
            return
        if all_items:
            targets = [item for scene in w.manager.project.scenes for item in scene.items]
        elif w.item is not None:
            targets = w.scene.items[:w.scene.items.index(w.item) + 1]
        else:
            w.statusBar().showMessage("Select an image first.")
            return
        if not targets:
            w.statusBar().showMessage("Import screenshots first.")
            return
        self.project = w.manager.project
        self.targets = list(targets)
        self.original_selection = w.item.id if w.item else targets[0].id
        self.force_id = w.item.id if force and w.item else None
        self.index = 0
        self.errors = []
        self.cancel_event = Event()
        self._busy = True
        w.centralWidget().setEnabled(False)
        w.cancel_ocr_button.setEnabled(True)
        self._next()

    def _next(self):
        if self.cancel_event.is_set() or self.index >= len(self.targets):
            self._finish()
            return
        self.target = self.targets[self.index]
        self.failure = ""
        job = OCRJob(Path(self.target.original_image_path), self.cancel_event, self.provider,
                     deepcopy(self.project.extraction_settings), self.project.cleaner_settings.read_username,
                     self.target.ocr_result if self.force_id == self.target.id else None)
        self.worker = Worker(job, expected_errors=(OCRError,))
        self.worker.signals.progress.connect(self.on_progress)
        self.worker.signals.status.connect(self.on_status)
        self.worker.signals.error.connect(self.on_error)
        self.worker.signals.finished.connect(self.on_finished)
        QThreadPool.globalInstance().start(self.worker)

    @Slot(int)
    def on_progress(self, value):
        self.window.progress.setValue(round((self.index * 100 + value) / len(self.targets)))

    @Slot(str)
    def on_status(self, message):
        self.window.statusBar().showMessage(f"{self.index + 1}/{len(self.targets)} · {message}")

    def cancel(self):
        if self.busy:
            self.cancel_event.set()
            self.window.statusBar().showMessage("Cancelling OCR...")

    @Slot(str)
    def on_error(self, message):
        self.failure = message

    @Slot(object)
    def on_finished(self, payload):
        w = self.window
        self.worker = None
        valid = w.manager.project is self.project and any(self.target is item for scene in self.project.scenes for item in scene.items)
        if not self.cancel_event.is_set() and valid:
            if isinstance(payload, DetectionPayload):
                w.manager.apply_detection(self.target, payload.ocr, payload.extraction, self.force_id == self.target.id)
            else:
                self.target.ocr_status = "error"
                w.manager.refresh_content(self.target)
                w.manager.changed()
                self.errors.append(self.failure or "OCR failed; existing text was kept.")
        self.index += 1
        QTimer.singleShot(0, self._next)

    def _finish(self):
        w = self.window
        self._busy = False
        w.centralWidget().setEnabled(True)
        w.cancel_ocr_button.setEnabled(False)
        w.refresh(self.original_selection)
        if self.cancel_event.is_set():
            w.statusBar().showMessage("Cancelled. Completed results kept; manual edits preserved.")
        elif self.errors:
            w.error("\n".join(dict.fromkeys(self.errors)))
        else:
            review = sum(item.needs_review for item in self.targets)
            fallback = sum(any("fallback." in warning for warning in item.extraction_warnings) for item in self.targets)
            suffix = f" {fallback} item(s) used OCR fallback; see Advanced for the error." if fallback else ""
            w.statusBar().showMessage(f"Comment extraction complete · {review} item(s) need review. TTS text prepared; choose a voice to generate narration." + suffix)
        if self.close_when_finished:
            self.close_when_finished = False
            QTimer.singleShot(0, w.close)
