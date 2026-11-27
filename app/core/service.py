import asyncio, logging, random
from datetime import datetime, timezone
from sqlalchemy import select, func, update
from app.config import settings
from app.db import Session, Meme, Target, Setting, Delivery
from app.sources import PinterestSource
from app.platforms import telegram, discord

log = logging.getLogger(__name__)

class MemeService:
    def __init__(self): self.source = PinterestSource(); self._post_lock = asyncio.Lock()

    async def get_setting(self, key, default=""):
        async with Session() as s:
            item = await s.get(Setting, key)
            return item.value if item else default

    async def set_setting(self, key, value):
        async with Session() as s:
            item = await s.get(Setting, key)
            if item: item.value = str(value)
            else: s.add(Setting(key=key, value=str(value)))
            await s.commit()

    async def sync_targets(self):
        async with Session() as s:
            for platform, values in (("telegram", settings.parse_ids(settings.telegram_targets)), ("discord", settings.parse_ids(settings.discord_targets))):
                for target in values:
                    exists = await s.scalar(select(Target).where(Target.platform == platform, Target.target_id == target))
                    if not exists: s.add(Target(platform=platform, target_id=target, label=target))
            await s.commit()

    async def recover_inflight(self):
        async with Session() as s:
            await s.execute(update(Meme).where(Meme.status == "sending").values(status="queued"))
            await s.commit()

    async def check_source(self):
        pins = await self.source.fetch()
        new_ids = []
        async with Session() as s:
            known = set((await s.scalars(select(Meme.pin_id))).all())
            initial_import = not known
            for pin in pins:
                if pin.pin_id not in known:
                    is_new = not initial_import
                    s.add(Meme(pin_id=pin.pin_id, pin_url=pin.pin_url, media_url=pin.media_url, media_type=pin.media_type, title=pin.title, status="queued", is_new=is_new))
                    if is_new: new_ids.append(pin.pin_id)
            await s.commit()
        if new_ids:
            log.info("Imported %d new pin(s)", len(new_ids))
            if (await self.get_setting("new_pin_mode", settings.new_pin_mode)) == "immediate":
                for pid in new_ids: await self.post_by_pin(pid)

    async def post_next(self):
        if (await self.get_setting("paused", "false")).lower() == "true": return False
        async with self._post_lock:
            async with Session() as s:
                queued = list((await s.scalars(select(Meme).where(Meme.status == "queued", Meme.is_new.is_(False)))).all())
                if not queued:
                    queued = list((await s.scalars(select(Meme).where(Meme.status == "sent", Meme.is_new.is_(False)))).all())
                    if queued:
                        for item in queued: item.status = "queued"
                        await s.commit()
                if not queued:
                    queued = list((await s.scalars(select(Meme).where(Meme.status == "queued", Meme.is_new.is_(True)))).all())
                if not queued: return False
                item = random.choice(queued); pid = item.pin_id
        return await self.post_by_pin(pid)

    async def post_by_pin(self, pin_id):
        async with self._post_lock:
            async with Session() as s:
                item = await s.scalar(select(Meme).where(Meme.pin_id == str(pin_id)))
                if not item: return False
                targets = list((await s.scalars(select(Target).where(Target.enabled.is_(True)))).all())
                if not targets: return False
                previous_status = item.status
                meme_id = item.id; media_url=item.media_url; media_type=item.media_type; caption=item.title; pin_url=item.pin_url
                item.status = "sending"; await s.commit()
            successes, failures = 0, []
            async with Session() as s:
                delivered = set() if previous_status == "sent" else {(d.platform, d.target_id) for d in (await s.scalars(select(Delivery).where(Delivery.meme_id == meme_id))).all()}
            for target in targets:
                if (target.platform, target.target_id) in delivered:
                    continue
                try:
                    for attempt in range(3):
                        try:
                            if target.platform == "telegram": await telegram.send(target.target_id, media_url, media_type, caption, pin_url)
                            else: await discord.send(target.target_id, media_url, media_type, caption, pin_url)
                            break
                        except Exception:
                            if attempt == 2: raise
                            await asyncio.sleep(2 ** attempt)
                    successes += 1
                    async with Session() as s:
                        s.add(Delivery(meme_id=meme_id, platform=target.platform, target_id=target.target_id)); await s.commit()
                except Exception as exc:
                    failures.append(str(exc)); log.exception("Delivery failed for meme %s", pin_id)
            async with Session() as s:
                item = await s.get(Meme, meme_id)
                all_delivered = not failures and len(delivered) + successes >= len(targets)
                if all_delivered:
                    item.send_count += 1; item.sent_at = datetime.now(timezone.utc); item.status = "sent"; item.is_new = False
                else: item.status = "queued"
                await s.commit()
            return successes > 0 or all_delivered

    async def mark(self, meme_id, status):
        async with Session() as s:
            item = await s.get(Meme, meme_id)
            if item:
                if status == "queued":
                    for delivery in (await s.scalars(select(Delivery).where(Delivery.meme_id == meme_id))).all():
                        await s.delete(delivery)
                item.status = status
                if status == "queued": item.is_new = False
                await s.commit()

    async def delete(self, meme_id):
        async with Session() as s:
            item = await s.get(Meme, meme_id)
            if item: await s.delete(item); await s.commit()

    async def stats(self):
        async with Session() as s:
            total = await s.scalar(select(func.count()).select_from(Meme)) or 0
            sent = await s.scalar(select(func.count()).select_from(Meme).where(Meme.status == "sent")) or 0
            queued = await s.scalar(select(func.count()).select_from(Meme).where(Meme.status == "queued")) or 0
        return {"total":total,"sent":sent,"queued":queued,"paused":(await self.get_setting("paused","false")) == "true"}
