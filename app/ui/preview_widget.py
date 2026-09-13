from PySide6.QtCore import QRectF, Qt
from PySide6.QtGui import QColor, QImageReader, QPainter, QPixmap
from PySide6.QtWidgets import QWidget
from app.core.config import VideoSettings


class PreviewWidget(QWidget):
    """Static portrait canvas, not a final-render compositor."""
    def __init__(self):
        super().__init__()
        self.setMinimumSize(180, 230)
        self.pixmap = QPixmap()
        self.message = "Import a screenshot"
        self.settings = VideoSettings()

    def set_image(self, path: str = ""):
        reader = QImageReader(path)
        reader.setAutoTransform(True)
        self.pixmap = QPixmap.fromImage(reader.read()) if path else QPixmap()
        self.message = "Image missing or unreadable" if path else "Import a screenshot"
        self.update()

    def paintEvent(self, event):
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
        height = max(1, min(self.height() - 8, (self.width() - 8) * 16 / 9))
        width = height * 9 / 16
        canvas = QRectF((self.width() - width) / 2, (self.height() - height) / 2, width, height)
        painter.fillRect(canvas, QColor("#20252c"))
        if self.pixmap.isNull():
            painter.setPen(QColor("#eeeeee"))
            painter.drawText(canvas.adjusted(8, 8, -8, -8), Qt.AlignmentFlag.AlignCenter | Qt.TextFlag.TextWordWrap, self.message)
        else:
            scale = min(width * self.settings.comment_max_width_ratio / self.pixmap.width(), height * .9 / self.pixmap.height())
            w, h = self.pixmap.width() * scale, self.pixmap.height() * scale
            painter.drawPixmap(QRectF(canvas.center().x() - w / 2, canvas.top() + max(0, min(height-h, height*self.settings.comment_y_ratio-h/2)), w, h),
                               self.pixmap, QRectF(self.pixmap.rect()))
