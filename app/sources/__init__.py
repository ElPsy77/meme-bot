from app.config import settings
from .pinterest import Pin, PinSource, PinterestSource
from .folder import LocalFolderSource

class EmptySource:
    async def fetch(self) -> list[Pin]:
        return []

def build_source() -> PinSource:
    if settings.meme_source == "telegram_inbox":
        return EmptySource()
    if settings.meme_source == "folder":
        return LocalFolderSource()
    if settings.meme_source == "pinterest_rss":
        return PinterestSource(mode="rss")
    return PinterestSource(mode="api")
