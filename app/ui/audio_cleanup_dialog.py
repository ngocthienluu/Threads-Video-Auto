"""Review unused audio before deleting; file logic runs in the cleanup service."""
from copy import deepcopy
from PySide6.QtCore import QThreadPool, QTimer
from PySide6.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QPlainTextEdit, QFileDialog
from app.services.tts.cleanup import CleanupError
from app.utils.workers import Worker


class AudioCleanupDialog(QDialog):
    def __init__(self, parent, service, manager):
        super().__init__(parent)
        self.setWindowTitle("Dọn audio thừa")
        self.resize(660, 380)
        self.service, self.manager = service, manager
        self.extra_projects = []
        self.plan = None
        self.busy = False
        layout = QVBoxLayout(self)
        note = QLabel("Giữ audio của project đang mở và mọi project JSON trong thư mục projects.\n"
                      "Nếu có project lưu nơi khác, thêm file bên dưới trước khi xóa.\n"
                      "Chỉ dọn MP3 do app tạo trong cache/tts; xóa rồi muốn dùng lại có thể phải tạo giọng lại.")
        note.setWordWrap(True)
        layout.addWidget(note)
        self.summary = QLabel("Đang kiểm tra...")
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.files = QPlainTextEdit()
        self.files.setReadOnly(True)
        layout.addWidget(self.files)
        row = QHBoxLayout()
        self.add = QPushButton("Thêm project ở nơi khác")
        self.refresh = QPushButton("Kiểm tra lại")
        self.remove = QPushButton("Xóa audio thừa")
        self.remove.setEnabled(False)
        self.close_button = QPushButton("Đóng")
        for button in (self.add, self.refresh, self.remove, self.close_button):
            row.addWidget(button)
        layout.addLayout(row)
        self.add.clicked.connect(self.add_projects)
        self.refresh.clicked.connect(self.scan)
        self.remove.clicked.connect(lambda: self.run(deleting=True))
        self.close_button.clicked.connect(self.reject)
        QTimer.singleShot(0, self.scan)

    def add_projects(self):
        paths, _ = QFileDialog.getOpenFileNames(self, "Project cần giữ audio", "", "Project (*.json)")
        self.extra_projects.extend(paths)
        if paths:
            self.scan()

    def scan(self):
        self.run()

    def run(self, deleting=False):
        if self.busy or (deleting and not self.plan):
            return
        self.busy = True
        for button in (self.add, self.refresh, self.remove, self.close_button):
            button.setEnabled(False)
        self.summary.setText("Đang xóa audio thừa..." if deleting else "Đang kiểm tra audio và project...")
        current = deepcopy(self.manager.project.to_dict())
        project_path = self.manager.path
        extras = tuple(self.extra_projects)
        plan = self.plan
        self.deleting = deleting
        self.failure = ""
        def operation(progress, status):
            if deleting:
                return self.service.delete(plan, current, project_path, extras)
            return self.service.scan(current, project_path, extras)
        self.worker = Worker(operation, expected_errors=(CleanupError,))
        self.worker.signals.error.connect(self.failed)
        self.worker.signals.finished.connect(self.finished_work)
        QThreadPool.globalInstance().start(self.worker)

    def failed(self, message):
        self.failure = message

    def finished_work(self, result):
        self.busy = False
        self.worker = None
        for button in (self.add, self.refresh, self.close_button):
            button.setEnabled(True)
        if self.failure or result is None:
            self.plan = None
            self.remove.setEnabled(False)
            self.summary.setText(self.failure or "Không thể hoàn tất dọn audio.")
            return
        if self.deleting:
            removed, freed, skipped = result
            self.plan = None
            self.summary.setText(f"Đã xóa {removed} file, giải phóng {freed / 1024**2:.2f} MB. Bỏ qua {len(skipped)} file đang dùng/đã thay đổi/không xóa được.")
            self.files.setPlainText("\n".join(skipped))
            self.remove.setEnabled(False)
        else:
            self.plan = result
            self.summary.setText(f"Có {len(result.candidates)} file thừa ({result.bytes / 1024**2:.2f} MB).\n"
                                 f"Giữ {result.protected_count} audio; đã kiểm tra {result.project_count} project đã lưu và project đang mở.")
            self.files.setPlainText("\n".join(f"{entry.path.name}  ({entry.size / 1024:.1f} KB)" for entry in result.candidates))
            self.remove.setEnabled(bool(result.candidates))

    def reject(self):
        if not self.busy:
            super().reject()

    def closeEvent(self, event):
        if self.busy:
            event.ignore()
        else:
            super().closeEvent(event)
