from abc import ABC, abstractmethod
from pathlib import Path


class TTSProvider(ABC):
    @abstractmethod
    def synthesize(self, text: str, voice_id: str, output: Path, speed: float = 1.0, cancel=None) -> Path:
        """Write narration and return its path; callers must measure duration."""
