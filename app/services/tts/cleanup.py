"""Conservative, explicit collection of unreferenced generated MP3 cache files."""
from dataclasses import dataclass
import json
import os
from pathlib import Path
import re
import tempfile
from app.core.models import Project


class CleanupError(RuntimeError):
    pass


def linked(path):
    return path.is_symlink() or getattr(path, "is_junction", lambda: False)()


def references(value, base):
    found = set()
    if isinstance(value, dict):
        for key, entry in value.items():
            if key in {"audio_path", "file", "original_image_path"} and isinstance(entry, str) and entry:
                found.add((base / entry).resolve())
            elif isinstance(entry, (dict, list)):
                found.update(references(entry, base))
    elif isinstance(value, list):
        for entry in value:
            found.update(references(entry, base))
    return found


@dataclass(frozen=True)
class Candidate:
    path: Path
    size: int
    modified: int
    inode: int


@dataclass
class CleanupPlan:
    candidates: list[Candidate]
    protected_count: int
    project_count: int

    @property
    def bytes(self):
        return sum(entry.size for entry in self.candidates)


class AudioCleanup:
    def __init__(self, cache_dir, projects_dir):
        self.cache_dir = Path(cache_dir).absolute()
        self.projects_dir = Path(projects_dir).absolute()
        self.registry = self.cache_dir / "saved_projects.json"

    def known_projects(self):
        if not self.registry.exists():
            return set()
        try:
            data = json.loads(self.registry.read_text(encoding="utf-8"))
            if not isinstance(data, list) or any(not isinstance(p, str) or not Path(p).is_absolute() for p in data):
                raise ValueError()
            return {Path(p) for p in data}
        except (OSError, ValueError):
            raise CleanupError("Không đọc được danh sách project đã lưu. Chưa xóa audio nào.") from None

    def remember(self, path):
        paths = self.known_projects() | {Path(path).resolve()}
        temporary = None
        try:
            self.cache_dir.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=self.cache_dir, delete=False) as stream:
                temporary = Path(stream.name)
                json.dump(sorted(str(p) for p in paths), stream, ensure_ascii=False)
            os.replace(temporary, self.registry)
        except OSError:
            raise CleanupError("Project đã lưu/mở, nhưng chưa ghi được danh sách bảo vệ audio. Thêm file này khi dọn audio.") from None
        finally:
            if temporary and temporary.exists():
                temporary.unlink()

    def scan(self, current, current_path=None, extra_projects=()):
        # Only generated filenames directly under the configured cache, never recurse/delete folders.
        if linked(self.cache_dir) or self.cache_dir.resolve() != self.cache_dir:
            raise CleanupError("Không dọn cache qua symbolic link/junction.")
        root = self.cache_dir.resolve()
        paths = self.known_projects() | {Path(p).resolve() for p in extra_projects}
        if current_path:
            paths.add(Path(current_path).resolve())
        try:
            if self.projects_dir.exists():
                for folder, dirs, files in os.walk(self.projects_dir, onerror=lambda exc: (_ for _ in ()).throw(exc)):
                    if any(linked(Path(folder) / name) for name in dirs):
                        raise CleanupError("Thư mục projects có liên kết thư mục. Chưa xác minh được mọi project.")
                    paths.update((Path(folder) / name).resolve() for name in files if name.lower().endswith(".json"))
            protected = references(current, Path(current_path).parent if current_path else Path.cwd())
            for path in paths:
                # A missing external disk/project must block, not be treated as unreferenced.
                try:
                    data = json.loads(path.read_text(encoding="utf-8-sig"))
                    Project.from_dict(data)
                    protected.update(references(data, path.parent))
                except (OSError, ValueError, TypeError, RecursionError):
                    raise CleanupError(f"Không kiểm tra được project: {path}. Chưa xóa audio nào.") from None
            candidates = []
            kept = 0
            for path in root.iterdir() if root.exists() else []:
                if not re.fullmatch(r"[0-9a-f]{64}\.mp3", path.name) or path.is_symlink() or not path.is_file():
                    continue
                if path.resolve().parent != root:
                    continue
                if path.resolve() in protected:
                    kept += 1
                else:
                    info = path.stat()
                    candidates.append(Candidate(path.resolve(), info.st_size, info.st_mtime_ns, info.st_ino))
            return CleanupPlan(sorted(candidates, key=lambda e: e.path.name), kept, len(paths))
        except OSError:
            raise CleanupError("Không đọc được thư mục project/cache. Chưa xóa audio nào.") from None

    def delete(self, approved, current, current_path=None, extra_projects=()):
        # Recheck references and file identity after the user has reviewed the preview.
        fresh = {entry.path: entry for entry in self.scan(current, current_path, extra_projects).candidates}
        root = self.cache_dir.resolve()
        removed, freed, skipped = 0, 0, []
        for entry in approved.candidates:
            path = entry.path
            if fresh.get(path) != entry or path.parent != root or path.is_symlink():
                skipped.append(path.name)
                continue
            try:
                info = path.stat()
                if (info.st_size, info.st_mtime_ns, info.st_ino) != (entry.size, entry.modified, entry.inode) or path.resolve().parent != root:
                    skipped.append(path.name)
                    continue
                path.unlink()
                removed += 1
                freed += entry.size
            except OSError:
                skipped.append(path.name)
        return removed, freed, skipped
