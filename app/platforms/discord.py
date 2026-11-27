import logging
import discord
from app.config import settings
from app.platforms.media import download_media

log = logging.getLogger(__name__)
intents = discord.Intents.default()
client = discord.Client(intents=intents)

async def start():
    if settings.discord_bot_token:
        await client.login(settings.discord_bot_token)

async def send(target_id: str, media_url: str, media_type: str, caption: str, pin_url: str):
    if not settings.discord_bot_token: raise RuntimeError("Discord token is not configured")
    channel = client.get_channel(int(target_id))
    if channel is None: channel = await client.fetch_channel(int(target_id))
    if media_type == "link":
        await channel.send("\n".join(part.strip() for part in (caption, pin_url) if part and part.strip())[:2000]); return
    try:
        payload, _, filename = await download_media(media_url, settings.max_media_mb * 1024 * 1024)
        file = discord.File(fp=__import__('io').BytesIO(payload), filename=filename)
        await channel.send(content="\n".join(part.strip() for part in (caption, pin_url) if part and part.strip())[:2000] or None, file=file)
    except Exception as exc:
        log.warning("Discord upload failed; sending links: %s", exc)
        fallback = "\n".join(part.strip() for part in (caption, pin_url) if part and part.strip())
        if media_url.startswith(("http://", "https://")):
            fallback = "\n".join(part for part in (fallback, media_url) if part)
        await channel.send(fallback[:2000] or "Не удалось прикрепить медиафайл.")
