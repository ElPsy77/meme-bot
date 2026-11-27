from pathlib import Path
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from .models import Base
from app.config import settings

database_url = make_url(settings.database_url)
if database_url.get_backend_name() == "sqlite" and database_url.database not in (None, ":memory:"):
    Path(database_url.database).parent.mkdir(parents=True, exist_ok=True)
engine = create_async_engine(database_url, pool_pre_ping=True)
Session = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
