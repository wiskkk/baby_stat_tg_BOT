from datetime import datetime, timezone

from sqlalchemy import (BigInteger, Column, DateTime, ForeignKey, Integer,
                        String, func)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship

Base = declarative_base()


class User(Base):
    """Модель пользователя."""
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    # Используем chat_id вместо telegram_id
    chat_id = Column(BigInteger, unique=True, nullable=False)
    name = Column(String, nullable=False)


class SleepRecord(Base):
    """Модель записи сна."""
    __tablename__ = "sleep_records"

    id = Column(Integer, primary_key=True, index=True)
    chat_id = Column(BigInteger, ForeignKey("users.chat_id"),
                     nullable=False)  # Теперь привязка к chat_id
    start_time = Column(DateTime(timezone=True),
                        default=func.now(), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=True)

    user = relationship("User")

    def __repr__(self) -> str:
        return f"<SleepRecord(id={self.id}, chat_id={self.chat_id}, start={self.start_time}, end={self.end_time})>"


class FeedingRecord(Base):
    """Модель записи питания."""
    __tablename__ = "feeding_records"

    id = Column(Integer, primary_key=True)
    chat_id = Column(BigInteger, ForeignKey("users.chat_id"),
                     nullable=False)  # Привязка к chat_id
    amount = Column(Integer, nullable=False)
    timestamp = Column(DateTime(timezone=True),
                       default=lambda: datetime.now(timezone.utc))

    user = relationship("User")
