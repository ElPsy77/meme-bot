import asyncio
import hashlib
import logging
import shutil
from pathlib import Path
from app.config import settings
from .pinterest import Pin

log = logging.getLogger(__name__)
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".heic", ".heif"}
VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".webm"}
SUPPORTED_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS | {".gif"}


class LocalFolderSource:
    """Imports files from a local drop folder and archives each content version."""
    def __init__(self, folder: str | Path | None = None):
        self.root = Path(folder or settings.media_folder).expanduser().resolve()
        self.archive = Path(settings.media_archive_folder).expanduser().resolve()
        self._hash_cache: dict[tuple[str, int, int], str] = {}

    async def fetch(self) -> list[Pin]:
        return await asyncio.to_thread(self._scan)

    def _scan(self) -> list[Pin]:
        self.root.mkdir(parents=True, exist_ok=True)
        pins = []
        for path in sorted(self.root.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            try:
                resolved = path.resolve(strict=True)
                relative = resolved.relative_to(self.root)
                if any(part.startswith(".") for part in relative.parts) or resolved.is_relative_to(self.archive):
                    continue
                stat = resolved.stat()
                digest = self._digest(resolved, stat.st_size, stat.st_mtime_ns)
                archived = self.archive / f"{digest}{resolved.suffix.lower()}"
                self.archive.mkdir(parents=True, exist_ok=True)
                if not archived.exists():
                    temporary = archived.with_suffix(archived.suffix + ".tmp")
                    shutil.copyfile(resolved, temporary)
                    temporary.replace(archived)
                extension = resolved.suffix.lower()
                if extension in VIDEO_EXTENSIONS:
                    media_type = "video"
                elif extension == ".gif":
                    media_type = "gif"
                else:
                    media_type = "image"
                label = relative.as_posix()
                pins.append(Pin(
                    pin_id=f"file-{digest}",
                    pin_url=f"Локальный файл: {label}",
                    media_url=str(archived),
                    media_type=media_type,
                    title=resolved.stem,
                ))
            except (OSError, ValueError) as exc:
                log.warning("Skipping inaccessible media file %s: %s", path, exc)
        return pins

    def _digest(self, path: Path, size: int, mtime_ns: int) -> str:
        cache_key = (str(path), size, mtime_ns)
        digest = self._hash_cache.get(cache_key)
        if digest is None:
            hasher = hashlib.sha256()
            with path.open("rb") as source:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    hasher.update(chunk)
            digest = hasher.hexdigest()
            self._hash_cache = {key: value for key, value in self._hash_cache.items() if key[0] != str(path)}
            self._hash_cache[cache_key] = digest
        return digest
