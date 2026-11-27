import asyncio, logging, os
from pathlib import Path
from contextlib import asynccontextmanager
import uvicorn
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from app.config import settings
from app.db import init_db
from app.core import MemeService
from app.platforms import telegram, discord
from app.admin.web import app as web_app

Path("data").mkdir(exist_ok=True)
logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO), format="%(asctime)s %(levelname)s %(name)s: %(message)s", handlers=[logging.StreamHandler(), logging.FileHandler("data/memovoz.log", encoding="utf-8")])
log = logging.getLogger("memovoz")
service = MemeService()
telegram.bind(service)
scheduler = AsyncIOScheduler(timezone="UTC")

async def guarded_source_check():
    try: await service.check_source()
    except Exception: log.exception("Pinterest source check failed; will retry on next interval")

async def guarded_post():
    try:
        if not await service.post_next(): log.info("No meme sent (queue empty, paused, or no targets)")
    except Exception: log.exception("Scheduled post failed; will retry on next interval")

async def refresh_jobs():
    try:
        post = max(1, int(await service.get_setting("post_interval_minutes", str(settings.post_interval_minutes))))
        poll = max(1, int(await service.get_setting("poll_interval_minutes", str(settings.poll_interval_minutes))))
        for job_id, minutes, func in (("post",post,guarded_post),("poll",poll,guarded_source_check)):
            job=scheduler.get_job(job_id)
            if job is None or job.trigger.interval.total_seconds() != minutes*60:
                scheduler.add_job(func,"interval",minutes=minutes,id=job_id,replace_existing=True,max_instances=1,coalesce=True,misfire_grace_time=120)
                log.info("Job %s interval set to %s minute(s)",job_id,minutes)
    except Exception: log.exception("Could not refresh scheduler settings")

async def run():
    if not settings.secret_key or settings.secret_key == "change-me":
        raise RuntimeError("Set a unique SECRET_KEY in .env before starting")
    if not settings.admin_password_hash:
        raise RuntimeError("Set ADMIN_PASSWORD_HASH in .env; see README for password hash generation")
    await init_db()
    await service.recover_inflight()
    await service.sync_targets()
    await guarded_source_check()
    await refresh_jobs()
    scheduler.add_job(refresh_jobs,"interval",seconds=30,id="refresh",max_instances=1)
    scheduler.start()
    polling = asyncio.create_task(telegram.dp.start_polling(telegram.bot)) if telegram.bot else None
    if settings.discord_bot_token:
        try: await discord.start()
        except Exception: log.exception("Discord login failed; Discord deliveries will retry independently")
    config = uvicorn.Config(web_app, host=settings.web_host, port=settings.web_port, log_level=settings.log_level.lower())
    server = uvicorn.Server(config)
    try: await server.serve()
    finally:
        scheduler.shutdown(wait=False)
        if polling:
            polling.cancel()
            await asyncio.gather(polling, return_exceptions=True)
        if telegram.bot: await telegram.bot.session.close()
        if discord.client.is_ready() or settings.discord_bot_token:
            await discord.client.close()

if __name__ == "__main__": asyncio.run(run())
