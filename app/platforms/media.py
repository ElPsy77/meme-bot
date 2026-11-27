from pathlib import PurePosixPath
from pathlib import Path
from urllib.parse import urlparse
import asyncio
import mimetypes
import httpx
from app.config import settings

class MediaTooLarge(Exception):
    pass

async def download_media(url: str, max_bytes: int) -> tuple[bytes, str, str]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        path = Path(url).expanduser().resolve(strict=True)
        roots = [Path(settings.media_folder).expanduser().resolve(), Path(settings.media_archive_folder).expanduser().resolve()]
        if not path.is_file() or not any(path.is_relative_to(root) for root in roots):
            raise ValueError("Local media must be inside MEDIA_FOLDER or MEDIA_ARCHIVE_FOLDER")
        def read_local():
            with path.open("rb") as source:
                payload = source.read(max_bytes + 1)
            if len(payload) > max_bytes:
                raise MediaTooLarge("media exceeds configured upload limit")
            return payload
        payload = await asyncio.to_thread(read_local)
        return payload, mimetypes.guess_type(path.name)[0] or "application/octet-stream", path.name
    if not parsed.hostname:
        raise ValueError("Media URL must include an HTTP host")
    timeout = httpx.Timeout(45, connect=10)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        async with client.stream("GET", url, headers={"User-Agent": "Memovoz/1.0"}) as response:
            response.raise_for_status()
            declared = int(response.headers.get("content-length", "0") or "0")
            if declared > max_bytes:
                raise MediaTooLarge("media exceeds configured upload limit")
            chunks, total = [], 0
            async for chunk in response.aiter_bytes():
                total += len(chunk)
                if total > max_bytes:
                    raise MediaTooLarge("media exceeds configured upload limit")
                chunks.append(chunk)
            filename = PurePosixPath(parsed.path).name or "meme"
            return b"".join(chunks), response.headers.get("content-type", ""), filename
