from datetime import datetime, time, timedelta

import aiocron
import pytz
from sqlalchemy import func, select

from bot_core.bot_instance import bot
from bot_core.utils import format_minutes
from db.database import get_db
from db.models import FeedingRecord, SleepRecord, User

TZ = pytz.timezone("Europe/Moscow")


async def build_statistics_text(chat_id: int) -> str:
    today = datetime.now(TZ).date()
    days = [today - timedelta(days=i) for i in range(3)]

    day_blocks = []

    async for db_session in get_db():
        for day in days:
            day_start = datetime.combine(day, time(6, 0)).astimezone(TZ)
            day_end = datetime.combine(day, time(22, 0)).astimezone(TZ)

            # === Питание за день ===
            feeds_result = await db_session.execute(
                select(FeedingRecord).where(
                    FeedingRecord.chat_id == chat_id,
                    func.date(FeedingRecord.timestamp) == day,
                )
            )
            feeds = feeds_result.scalars().all()
            day_feed = sum(
                f.amount
                for f in feeds
                if day_start <= f.timestamp.astimezone(TZ) <= day_end
            )
            night_feed = sum(
                f.amount
                for f in feeds
                if not (day_start <= f.timestamp.astimezone(TZ) <= day_end)
            )

            # === Сон за день ===
            sleeps_result = await db_session.execute(
                select(SleepRecord).where(
                    SleepRecord.chat_id == chat_id,
                    SleepRecord.end_time.isnot(None),
                    func.date(SleepRecord.end_time) == day,
                )
            )
            sleeps = sleeps_result.scalars().all()
            day_sleep = night_sleep = 0
            for s in sleeps:
                end_msk = s.end_time.astimezone(TZ)
                duration = int((s.end_time - s.start_time).total_seconds() // 60)
                if day_start <= end_msk <= day_end:
                    day_sleep += duration
                else:
                    night_sleep += duration

            block = (
                f"📅 <b>{day.strftime('%d.%m.%Y')}</b>\n"
                f"🥛 Питание: День — {day_feed} мл, Ночь — {night_feed} мл\n"
                f"😴 Сон: День — {format_minutes(day_sleep)}, Ночь — {format_minutes(night_sleep)}\n"
            )
            day_blocks.append(block)

    return "📊 <b>Статистика за последние 3 дня:</b>\n\n" + "\n".join(day_blocks)


async def send_daily_statistics(chat_id: int):
    text = await build_statistics_text(chat_id)
    await bot.send_message(chat_id=chat_id, text=text, parse_mode="HTML")


async def send_statistics_to_all_users():
    """Функция для отправки статистики всем пользователям."""
    async for session in get_db():
        users = await session.execute(select(User.chat_id))
        chat_ids = [user[0] for user in users.fetchall()]  # Получаем список ID

    for chat_id in chat_ids:
        # Отправляем статистику каждому пользователю
        await send_daily_statistics(chat_id)


# Установим cron-задачу на 23:59 по Москве
aiocron.crontab("59 23 * * *", func=send_statistics_to_all_users, tz=TZ)
