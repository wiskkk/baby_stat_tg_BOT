from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class User(Base):
    """Модель пользователя."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(Integer, unique=True, nullable=False)
    name = Column(String, nullable=False)


class SleepRecord(Base):
    """Модель записи сна."""
    __tablename__ = "sleep_records"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, nullable=False)  # Telegram ID пользователя
    start_time = Column(DateTime(timezone=True), default=func.now(), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<SleepRecord(id={self.id}, user_id={self.user_id}, start={self.start_time}, end={self.end_time})>"


class FeedingRecord(Base):
    """Модель записи питания."""
    __tablename__ = "feeding_records"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    amount = Column(Integer, nullable=False)
    timestamp = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    user = relationship("User")
