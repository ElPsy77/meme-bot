from dataclasses import dataclass
from typing import Protocol
import re
import feedparser
import httpx
from app.config import settings


@dataclass
class Pin:
    pin_id: str
    pin_url: str
    media_url: str
    media_type: str
    title: str = ""


class PinSource(Protocol):
    async def fetch(self) -> list[Pin]: ...


class PinterestSource:
    """Pinterest API v5 or its optional RSS fallback."""
    def __init__(self, mode: str = "api"):
        if mode not in {"api", "rss"}:
            raise ValueError("Pinterest source mode must be 'api' or 'rss'")
        self.mode = mode

    async def fetch(self) -> list[Pin]:
        if self.mode == "rss":
            return await self._rss()
        if not settings.pinterest_access_token or not settings.pinterest_board_id:
            raise RuntimeError("PINTEREST_ACCESS_TOKEN and PINTEREST_BOARD_ID are required for API source")
        return await self._api()

    async def _api(self) -> list[Pin]:
        headers = {"Authorization": f"Bearer {settings.pinterest_access_token}"}
        base_url = f"https://api.pinterest.com/v5/boards/{settings.pinterest_board_id}/pins"
        url, params = base_url, {"page_size": 100}
        result: list[Pin] = []
        async with httpx.AsyncClient(timeout=30) as client:
            while url:
                response = await client.get(url, headers=headers, params=params)
                response.raise_for_status()
                data = response.json()
                for item in data.get("items", []):
                    pin_id = str(item["id"])
                    media = item.get("media") or {}
                    images = media.get("images") or item.get("images") or {}
                    video = media.get("video") or media.get("videos") or media.get("video_url") or item.get("videos") or item.get("video_url")
                    if video:
                        source, kind = _find_video_url(video), "video"
                    else:
                        source = next((v.get("url") for v in images.values() if isinstance(v, dict) and v.get("url")), "")
                        kind = "gif" if source.lower().split("?")[0].endswith(".gif") else "image"
                    # Pinterest's API `link` is the Pin's destination website, not its Pin permalink.
                    pin_url = f"https://www.pinterest.com/pin/{pin_id}/"
                    if not source:
                        source = next((v.get("url") for v in images.values() if isinstance(v, dict) and v.get("url")), "") or pin_url
                        kind = "image" if source != pin_url else "link"
                    result.append(Pin(pin_id, pin_url, source, kind, item.get("title") or item.get("description") or ""))
                bookmark = data.get("bookmark")
                url = base_url if bookmark else ""
                params = {"page_size": 100, "bookmark": bookmark} if bookmark else {}
        return result

    async def _rss(self) -> list[Pin]:
        feed_url = settings.pinterest_rss_url
        if not feed_url:
            feed_url = settings.pinterest_board_url.rstrip("/") + ".rss"
        if not feed_url or feed_url == ".rss":
            raise RuntimeError("Set PINTEREST_RSS_URL or PINTEREST_BOARD_URL for the RSS source")
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            response = await client.get(feed_url, headers={"User-Agent": "Mozilla/5.0 Memovoz/1.0"})
            response.raise_for_status()
        parsed = feedparser.parse(response.text)
        result = []
        for entry in parsed.entries:
            link = entry.get("link", "")
            match = re.search(r"/pin/(\d+)", link)
            pin_id = match.group(1) if match else entry.get("id") or link
            html = entry.get("summary", "")
            img = re.search(r'<img[^>]+src=["\']([^"\']+)', html)
            media = entry.get("enclosures", [{}])[0].get("href", "") if entry.get("enclosures") else ""
            media = media or (img.group(1) if img else "")
            if media:
                kind = "video" if re.search(r"\.(mp4|mov|m4v|webm)(?:\?|$)", media, re.I) else ("gif" if re.search(r"\.gif(?:\?|$)", media, re.I) else "image")
                result.append(Pin(str(pin_id), link, media, kind, entry.get("title", "")))
        return result


def _find_video_url(value) -> str:
    if isinstance(value, str):
        return value if value.startswith(("https://", "http://")) else ""
    if isinstance(value, dict):
        direct = value.get("url") or value.get("video_url")
        if isinstance(direct, str) and direct.startswith(("https://", "http://")):
            return direct
        for nested in value.values():
            found = _find_video_url(nested)
            if found:
                return found
    if isinstance(value, (list, tuple)):
        for nested in value:
            found = _find_video_url(nested)
            if found:
                return found
    return ""
