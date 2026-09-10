from pathlib import Path
from app.core.models import Project


class FFmpegRenderer:
    def render(self, project: Project, output: Path, progress=None) -> Path:
        raise NotImplementedError("Video export is not available in iteration 1.")
