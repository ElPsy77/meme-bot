import logging
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
from app.config import settings

log = logging.getLogger(__name__)
bot = Bot(settings.telegram_bot_token) if settings.telegram_bot_token else None
dp = Dispatcher()
service = None

def bind(core):
    global service
    service = core

@dp.message(Command("status"))
async def status(message: Message):
    if not _admin(message): return
    stats = await service.stats()
    await message.answer(f"Мемов: {stats['total']} · отправлено: {stats['sent']} · очередь: {stats['queued']} · пауза: {stats['paused']}")

@dp.message(Command("pause"))
async def pause(message: Message):
    if _admin(message):
        await service.set_setting("paused", "true")
        await message.answer("Автопостинг приостановлен.")

@dp.message(Command("resume"))
async def resume(message: Message):
    if _admin(message):
        await service.set_setting("paused", "false")
        await message.answer("Автопостинг возобновлён.")

@dp.message(Command("post_now"))
async def post_now(message: Message):
    if _admin(message):
        result = await service.post_next()
        await message.answer("Мем отправлен." if result else "В очереди нет доступных мемов.")

def _admin(message: Message) -> bool:
    return bool(settings.telegram_admin_id and message.from_user and message.from_user.id == settings.telegram_admin_id)

async def send(target_id: str, media_url: str, media_type: str, caption: str, pin_url: str):
    if not bot: raise RuntimeError("Telegram token is not configured")
    if media_type == "link":
        await bot.send_message(int(target_id), f"{caption}\n{pin_url}"[:4000]); return
    url = media_url
    try:
        async with __import__('httpx').AsyncClient(timeout=30) as client:
            response = await client.head(url, follow_redirects=True)
            length = int(response.headers.get("content-length", "0") or 0)
            ctype = response.headers.get("content-type", "")
        if length > settings.max_media_mb * 1024 * 1024: raise ValueError("media exceeds configured upload limit")
        if media_type == "gif" or "gif" in ctype or url.lower().split("?")[0].endswith(".gif"):
            await bot.send_animation(int(target_id), url, caption=(caption[:900] + "\n" + pin_url)[:1024])
        elif media_type == "video" or "video" in ctype:
            await bot.send_video(int(target_id), url, caption=(caption[:900] + "\n" + pin_url)[:1024])
        else:
            await bot.send_photo(int(target_id), url, caption=(caption[:900] + "\n" + pin_url)[:1024])
    except Exception as exc:
        log.warning("Telegram media upload failed; sending link: %s", exc)
        await bot.send_message(int(target_id), f"{caption}\n{pin_url}\n{media_url}"[:4000])
