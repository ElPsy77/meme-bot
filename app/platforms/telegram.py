import logging
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import Message
from app.config import settings
from app.platforms.media import download_media

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
        await bot.send_message(_chat_id(target_id), f"{caption}\n{pin_url}"[:4000]); return
    try:
        payload, ctype, filename = await download_media(media_url, settings.max_media_mb * 1024 * 1024)
        from aiogram.types import BufferedInputFile
        upload = BufferedInputFile(payload, filename=filename)
        chat_id = _chat_id(target_id)
        text = (caption[:900] + "\n" + pin_url)[:1024]
        if media_type == "gif" or "gif" in ctype or media_url.lower().split("?")[0].endswith(".gif"):
            await bot.send_animation(chat_id, upload, caption=text)
        elif media_type == "video" or "video" in ctype:
            await bot.send_video(chat_id, upload, caption=text)
        else:
            await bot.send_photo(chat_id, upload, caption=text)
    except Exception as exc:
        log.warning("Telegram media upload failed; sending link: %s", exc)
        await bot.send_message(_chat_id(target_id), f"{caption}\n{pin_url}\n{media_url}"[:4000])

def _chat_id(value: str):
    return value if value.startswith("@") else int(value)
