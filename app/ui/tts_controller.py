"""Selected-item voice generation; service owns API/cache/probing, core owns timeline."""
from copy import deepcopy
from dataclasses import replace
import logging
from pathlib import Path
from threading import Event
from PySide6.QtCore import QObject, QThreadPool, QTimer, Slot, QUrl
from PySide6.QtGui import QDesktopServices
from app.services.tts.service import TTSService, Narration, validate_narration
from app.services.tts.settings import TTSSettings
from app.services.tts.errors import TTSError
from app.services.tts.voices import VoiceCatalog
from app.utils.workers import Worker


class TTSController(QObject):
    def __init__(self, window):
        super().__init__(window)
        self.window = window
        self.config_error = ""
        try:
            self.service = TTSService()
        except (OSError, ValueError):
            self.service = TTSService(TTSSettings())
            self.config_error = "Cannot read .env. Check its encoding and file permissions."
        self.catalog = VoiceCatalog(self.service.provider, self.service.settings.cache_dir)
        self.catalog.load_cache()
        window.editor.set_voices(self.catalog.voices)
        panel = window.editor.voice_panel
        panel.notice.setText(self.catalog.warning or ("Cached voice list; use Refresh Voices to update." if self.catalog.voices else "Use Refresh Voices to load the list."))
        panel.account.setText("Configured" if self.service.settings.api_key else "Not configured")
        panel.test_requested.connect(lambda: self.start(test=True))
        panel.regenerate_requested.connect(lambda: self.start(regenerate=True))
        panel.default_requested.connect(self.set_default)
        panel.model_changed.connect(self.set_model)
        self.busy = False
        self.cancel_event = Event()
        self.close_when_finished = False
        window.editor.default_voice = self.service.settings.default_voice
        window.editor.voice_requested.connect(self.start)
        window.editor.voices_requested.connect(lambda: self.start(voices=True))
        window.editor.voice_changed.connect(self.edit_voice)
        window.editor.audio_requested.connect(self.open_audio)

    def edit_voice(self, identity, speed):
        w = self.window
        if w.item and not self.busy and not w.ocr_controller.busy:
            w.manager.set_voice(w.item, w.editor.voice_panel.selection, speed)
            w.editor.update_status(w.item)
            w.update_title()

    def sync_project(self):
        w = self.window
        project = w.manager.project
        panel = w.editor.voice_panel
        model = project.tts_model_id or self.service.settings.model
        if getattr(self, "availability_model", model) != model:
            for voice in self.catalog.voices:
                voice.is_available = None
                voice.availability_status = "unknown"
                voice.availability_reason = "API access not confirmed for this model"
        self.availability_model = model
        panel.default_id = project.default_voice_id or self.service.settings.default_voice
        info = self.catalog.find(panel.default_id)
        panel.default_label.setText(project.default_voice_name or info.name or ("Configured default (see Advanced)" if panel.default_id else "Not selected"))
        panel.model.setText(model)
        panel.update_status()

    def set_default(self):
        if self.busy:
            return
        w = self.window
        identity = w.editor.selected_voice()
        if identity:
            w.manager.set_default_voice(identity, self.catalog.find(identity).name)
            self.sync_project()
            w.editor.update_status(w.item)
            w.update_title()

    def set_model(self, model):
        if not self.busy:
            w = self.window
            w.manager.set_tts_model(model)
            self.sync_project()
            w.editor.update_status(w.item)
            w.update_title()

    def start(self, voices=False, test=False, regenerate=False):
        w = self.window
        if self.busy or w.ocr_controller.busy:
            return
        if self.config_error:
            w.error(self.config_error)
            return
        self.sync_project()
        identity = w.editor.selected_voice()
        if not voices:
            if not w.item or not identity:
                return
            self.edit_voice(identity, w.editor.speed.value())
        self.project, self.item = w.manager.project, w.item
        snapshot = deepcopy(w.item) if w.item else None
        if snapshot:
            snapshot.voice_id = identity
        if not voices and not test:
            try:
                validate_narration(snapshot)
            except TTSError as exc:
                w.error(exc)
                return
            # Persist environment fallbacks used for this project, never credentials.
            if not self.project.default_voice_id and not self.item.voice_id:
                w.manager.set_default_voice(identity, self.catalog.find(identity).name)
            if not self.project.tts_model_id:
                self.project.tts_model_id = self.service.settings.model
                w.manager.changed()
        self.snapshot = snapshot
        self.voices, self.testing = voices, test
        self.requested_voice = identity
        self.requested_model = self.project.tts_model_id or self.service.settings.model
        settings = replace(self.service.settings, model=self.requested_model)
        # Preserve the reusable service when settings match (also keeps test injection simple).
        service = self.service if settings == self.service.settings else TTSService(settings)
        self.failure = ""
        self.cancel_event = Event()
        self.busy = True
        w.centralWidget().setEnabled(False)
        w.cancel_tts_button.setEnabled(True)
        message = "Loading voices..." if voices else "Testing voice..." if test else "Generating audio / checking cache..."
        w.editor.voice_panel.notice.setText(message)
        def operation(progress, status):
            progress(5)
            status(message)
            try:
                if voices:
                    result = self.catalog.list_voices(self.cancel_event)
                elif test:
                    result = self.catalog.validate_voice_access(identity, service, self.cancel_event)
                else:
                    result = service.generate(snapshot, self.cancel_event, force=True) if regenerate else service.generate(snapshot, self.cancel_event)
                progress(100)
                return result
            except TTSError as exc:
                # Carry safe structured errors through the object result signal.
                logging.getLogger(__name__).warning("Voice request stopped: %s (%s)", exc.title, exc.availability_status)
                return exc
        self.worker = Worker(operation)
        self.worker.signals.status.connect(self.on_status)
        self.worker.signals.progress.connect(self.on_progress)
        self.worker.signals.error.connect(self.on_error)
        self.worker.signals.finished.connect(self.finish)
        QThreadPool.globalInstance().start(self.worker)

    @Slot(str)
    def on_status(self, message):
        self.window.statusBar().showMessage(message)

    @Slot(int)
    def on_progress(self, value):
        self.window.progress.setValue(value)

    @Slot(str)
    def on_error(self, message):
        self.failure = message

    def cancel(self):
        self.cancel_event.set()
        self.window.statusBar().showMessage("Cancelling voice operation; waiting for network timeout if necessary...")

    @Slot(object)
    def finish(self, result):
        from PySide6.QtWidgets import QMessageBox
        w = self.window
        self.busy = False
        self.worker = None
        w.centralWidget().setEnabled(True)
        w.cancel_tts_button.setEnabled(False)
        valid = w.manager.project is self.project
        panel = w.editor.voice_panel
        if not self.cancel_event.is_set() and valid:
            if self.voices and isinstance(result, list):
                w.editor.set_voices(result)
                panel.notice.setText(self.catalog.warning or f"{len(result)} voices loaded. Access is confirmed only by synthesis.")
            elif isinstance(result, Narration):
                if not result.cached:
                    self.catalog.observe(self.requested_voice)
                if self.testing:
                    panel.notice.setText("Voice available. Short test completed; comment audio was not changed.")
                elif any(self.item is item for scene in self.project.scenes for item in scene.items):
                    current = (self.item.tts_text, self.item.voice_id or self.project.default_voice_id or self.service.settings.default_voice, self.item.voice_speed)
                    requested = (self.snapshot.tts_text, self.snapshot.voice_id, self.snapshot.voice_speed)
                    if current != requested or (self.project.tts_model_id or self.service.settings.model) != self.requested_model:
                        panel.notice.setText("Inputs changed; outdated result was not applied.")
                    else:
                        try:
                            w.manager.apply_narration(self.item, result)
                            panel.notice.setText(f"Audio ready: {result.duration:.2f}s" + (" (cache; current API access not tested)" if result.cached else ""))
                        except ValueError as exc:
                            w.error(exc)
            else:
                error = result if isinstance(result, TTSError) else TTSError(self.failure or "Voice operation failed.")
                if self.voices:
                    panel.notice.setText("Unable to refresh ElevenLabs voices. Showing cached list. " + str(error) if self.catalog.voices else str(error))
                else:
                    self.catalog.observe(self.requested_voice, error)
                    panel.notice.setText(str(error))
                    if self.item and not self.testing and self.item.tts_status != "done":
                        self.item.tts_status = "error"
                        w.manager.changed()
                QMessageBox.warning(w, error.title, str(error))
        else:
            panel.notice.setText("Voice operation cancelled; previous text/audio kept.")
        if valid:
            w.editor.set_voices(self.catalog.voices)
            self.sync_project()
            w.editor.set_item(w.item, w.manager.project.cleaner_settings)
            w.update_title()
        w.statusBar().showMessage(panel.notice.text())
        if self.close_when_finished:
            self.close_when_finished = False
            QTimer.singleShot(0, w.close)

    def open_audio(self):
        item = self.window.item
        if not item or not item.audio_path or not Path(item.audio_path).is_file():
            self.window.error("Generated audio file is missing. Generate voice again.")
        elif not QDesktopServices.openUrl(QUrl.fromLocalFile(str(Path(item.audio_path).resolve()))):
            self.window.error("No audio player could open this file.")
