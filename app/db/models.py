from datetime import datetime, timezone
from sqlalchemy import String, Integer, DateTime, Boolean, Text, ForeignKey, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

def now(): return datetime.now(timezone.utc)

class Base(DeclarativeBase): pass

class Meme(Base):
    __tablename__ = "memes"
    id: Mapped[int] = mapped_column(primary_key=True)
    pin_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    pin_url: Mapped[str] = mapped_column(Text)
    media_url: Mapped[str] = mapped_column(Text)
    media_type: Mapped[str] = mapped_column(String(20), default="image")
    title: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(20), default="queued", index=True)
    is_new: Mapped[bool] = mapped_column(Boolean, default=False)
    added_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    send_count: Mapped[int] = mapped_column(Integer, default=0)
    deliveries: Mapped[list["Delivery"]] = relationship(back_populates="meme", cascade="all, delete-orphan")

class Target(Base):
    __tablename__ = "targets"
    id: Mapped[int] = mapped_column(primary_key=True)
    platform: Mapped[str] = mapped_column(String(20))
    target_id: Mapped[str] = mapped_column(String(100))
    label: Mapped[str] = mapped_column(String(200), default="")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    __table_args__ = (UniqueConstraint("platform", "target_id"),)

class Setting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(100), primary_key=True)
    value: Mapped[str] = mapped_column(Text)

class Delivery(Base):
    __tablename__ = "deliveries"
    id: Mapped[int] = mapped_column(primary_key=True)
    meme_id: Mapped[int] = mapped_column(ForeignKey("memes.id", ondelete="CASCADE"))
    platform: Mapped[str] = mapped_column(String(20))
    target_id: Mapped[str] = mapped_column(String(100))
    sent_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=now)
    meme: Mapped[Meme] = relationship(back_populates="deliveries")
