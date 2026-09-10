import argparse
import logging
import sys

from app.core.config import ensure_runtime_dirs
from app.utils.logging import setup_logging


def main() -> int:
    parser = argparse.ArgumentParser(description="Threads Video Studio")
    parser.add_argument("--smoke-test", action="store_true", help="Open main window and exit after the event loop starts")
    args = parser.parse_args()
    try:
        ensure_runtime_dirs()
        setup_logging()
        logging.getLogger("app.main").info("App start; default config loaded")
        from PySide6.QtCore import QTimer
        from PySide6.QtWidgets import QApplication
        from app.ui import configure_fonts
        from app.ui.main_window import MainWindow
        application = QApplication(sys.argv[:1])
        configure_fonts(application)
        application.setApplicationName("Threads Video Studio")
        window = MainWindow()
        application.aboutToQuit.connect(window.ocr_controller.provider.close)
        window.show()
        if args.smoke_test:
            QTimer.singleShot(300, application.quit)
        return application.exec()
    except ImportError:
        print("Missing UI dependency. Install requirements.txt using the .venv Python.", file=sys.stderr)
        return 1
    except Exception:
        logging.getLogger("app.main").exception("Startup failed")
        print("App startup failed. Check logs/app.log and folder permissions.", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
