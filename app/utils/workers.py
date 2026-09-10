"""Extension point for long jobs. Results are delivered via queued Qt signals."""
import logging
from PySide6.QtCore import QObject, QRunnable, Signal, Slot


class WorkerSignals(QObject):
    progress = Signal(int)
    status = Signal(str)
    error = Signal(str)
    finished = Signal(object)


class Worker(QRunnable):
    def __init__(self, operation, expected_errors=()):
        super().__init__()
        self.signals = WorkerSignals()
        self.operation = operation
        self.expected_errors = expected_errors

    @Slot()
    def run(self):
        result = None
        try:
            result = self.operation(self.signals.progress.emit, self.signals.status.emit)
        except self.expected_errors as exc:
            logging.getLogger(__name__).warning("Background task stopped: %s", exc)
            self.signals.error.emit(str(exc))
        except Exception:
            # Provider adapters must translate failures without leaking request secrets.
            logging.getLogger(__name__).error("Background task failed")
            self.signals.error.emit("Background task failed. Check the provider and input files.")
        finally:
            self.signals.finished.emit(result)
