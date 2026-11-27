import logging
import discord
from app.config import settings

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
        await channel.send(f"{caption}\n{pin_url}"[:2000]); return
    try:
        async with __import__('httpx').AsyncClient(timeout=45, follow_redirects=True) as http:
            response = await http.get(media_url)
            response.raise_for_status()
            if len(response.content) > settings.max_media_mb * 1024 * 1024: raise ValueError("media too large")
        file = discord.File(fp=__import__('io').BytesIO(response.content), filename=media_url.split("?")[0].rsplit("/", 1)[-1] or "meme")
        await channel.send(content=f"{caption}\n{pin_url}"[:2000], file=file)
    except Exception as exc:
        log.warning("Discord upload failed; sending links: %s", exc)
        await channel.send(f"{caption}\n{pin_url}\n{media_url}"[:2000])
