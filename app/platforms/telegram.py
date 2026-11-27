import logging
import uuid
from datetime import datetime
from pathlib import Path
from aiogram import Bot, Dispatcher, F
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

@dp.message(Command("start"))
async def start(message: Message):
    if _admin(message) and message.chat.type == "private":
        await message.answer("Пришли сюда фото, GIF или видео — добавлю его в очередь мемов.")

@dp.message(F.photo | F.animation | F.video | F.document)
async def receive_upload(message: Message):
    if not _admin(message) or message.chat.type != "private" or not bot or not service:
        return
    media, media_type, filename = _message_media(message)
    if not media:
        await message.answer("Поддерживаются изображения, GIF и видео в форматах JPG, PNG, WEBP, GIF, MP4, MOV или WEBM.")
        return
    try:
        telegram_file = await bot.get_file(media.file_id)
        file_size = telegram_file.file_size or media.file_size or 0
        if file_size > settings.inbox_max_mb * 1024 * 1024:
            await message.answer(f"Файл больше лимита приёма ({settings.inbox_max_mb} МБ). Уменьши его или отправь фото с обычным сжатием Telegram.")
            return
        inbox = Path(settings.media_archive_folder).expanduser().resolve() / ".inbox"
        inbox.mkdir(parents=True, exist_ok=True)
        suffix = Path(filename).suffix.lower() or {"image":".jpg", "gif":".gif", "video":".mp4"}[media_type]
        temporary = inbox / f"{uuid.uuid4().hex}{suffix}.part"
        try:
            await bot.download_file(telegram_file.file_path, destination=temporary)
            title = message.caption or Path(filename).stem or f"Мем {datetime.now():%Y-%m-%d %H:%M}"
            _, created, sent = await service.ingest_upload(temporary, suffix, media_type, title)
        finally:
            temporary.unlink(missing_ok=True)
        if not created:
            await message.answer("Этот файл уже добавлен — повторно не добавлял его в очередь.")
        elif sent:
            await message.answer("Мем добавлен и отправлен в настроенные каналы.")
        else:
            await message.answer("Мем сохранён в очереди.")
    except Exception:
        log.exception("Could not import Telegram upload from user %s", message.from_user.id)
        await message.answer("Не получилось сохранить файл. Проверь формат и размер, затем попробуй ещё раз.")

def _message_media(message: Message):
    if message.photo:
        item = message.photo[-1]
        return item, "image", f"photo-{item.file_unique_id}.jpg"
    if message.animation:
        item = message.animation
        return item, "gif", item.file_name or f"{item.file_unique_id}.gif"
    if message.video:
        item = message.video
        return item, "video", item.file_name or f"{item.file_unique_id}.mp4"
    if message.document:
        item = message.document
        suffix = Path(item.file_name or "").suffix.lower()
        if suffix == ".gif" or item.mime_type == "image/gif":
            return item, "gif", item.file_name or f"{item.file_unique_id}.gif"
        video_extensions = {".mp4", ".mov", ".m4v", ".webm"}
        image_extensions = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".heic", ".heif"}
        if suffix in video_extensions:
            return item, "video", item.file_name or f"{item.file_unique_id}{suffix}"
        if suffix in image_extensions:
            return item, "image", item.file_name or f"{item.file_unique_id}{suffix}"
        mime_extension = {"video/mp4":".mp4", "video/quicktime":".mov", "video/x-m4v":".m4v", "video/webm":".webm", "image/jpeg":".jpg", "image/png":".png", "image/webp":".webp", "image/bmp":".bmp", "image/heic":".heic", "image/heif":".heif"}.get(item.mime_type or "")
        if mime_extension in video_extensions:
            return item, "video", f"{item.file_unique_id}{mime_extension}"
        if mime_extension in image_extensions:
            return item, "image", f"{item.file_unique_id}{mime_extension}"
    return None, "", ""

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
        await bot.send_message(_chat_id(target_id), _message_text(caption, pin_url)[:4000]); return
    try:
        payload, ctype, filename = await download_media(media_url, settings.max_media_mb * 1024 * 1024)
        from aiogram.types import BufferedInputFile
        upload = BufferedInputFile(payload, filename=filename)
        chat_id = _chat_id(target_id)
        text = _message_text(caption[:900], pin_url)[:1024]
        if media_type == "gif" or "gif" in ctype or media_url.lower().split("?")[0].endswith(".gif"):
            await bot.send_animation(chat_id, upload, caption=text)
        elif media_type == "video" or "video" in ctype:
            if filename.lower().endswith(".mp4"):
                await bot.send_video(chat_id, upload, caption=text)
            else:
                await bot.send_document(chat_id, upload, caption=text)
        elif filename.lower().endswith((".bmp", ".heic", ".heif")):
            await bot.send_document(chat_id, upload, caption=text)
        else:
            await bot.send_photo(chat_id, upload, caption=text)
    except Exception as exc:
        log.warning("Telegram media upload failed; sending link: %s", exc)
        fallback = _message_text(caption, pin_url)
        if media_url.startswith(("http://", "https://")):
            fallback = _message_text(fallback, media_url)
        await bot.send_message(_chat_id(target_id), fallback[:4000] or "Не удалось прикрепить медиафайл.")

def _chat_id(value: str):
    return value if value.startswith("@") else int(value)

def _message_text(*parts: str) -> str:
    return "\n".join(part.strip() for part in parts if part and part.strip())
