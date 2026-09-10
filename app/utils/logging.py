import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from app.core.config import ROOT


def setup_logging(root: Path = ROOT) -> None:
    directory = root / "logs"
    directory.mkdir(parents=True, exist_ok=True)
    logger = logging.getLogger("app")
    if logger.handlers:
        return
    logger.setLevel(logging.INFO)
    handler = RotatingFileHandler(directory / "app.log", maxBytes=2_000_000,
                                  backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
    logger.addHandler(handler)
