"""Shared UI initialization."""
import os
from pathlib import Path
from PySide6.QtGui import QFont, QFontDatabase


def configure_fonts(application):
    """Windows offscreen Qt may not discover system fonts automatically."""
    if not QFontDatabase.families():
        windows_dir = os.environ.get("WINDIR")
        if windows_dir:
            font = Path(windows_dir) / "Fonts" / "segoeui.ttf"
            if font.is_file():
                font_id = QFontDatabase.addApplicationFont(str(font))
                families = QFontDatabase.applicationFontFamilies(font_id)
                if families:
                    application.setFont(QFont(families[0], 10))
