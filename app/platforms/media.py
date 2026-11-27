from pathlib import PurePosixPath
from urllib.parse import urlparse
import httpx

class MediaTooLarge(Exception):
    pass

async def download_media(url: str, max_bytes: int) -> tuple[bytes, str, str]:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Media URL must use HTTP or HTTPS")
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
