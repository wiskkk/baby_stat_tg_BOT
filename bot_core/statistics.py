from datetime import datetime, time, timedelta

import aiocron
import pytz
from sqlalchemy import func, select

from bot_core.bot import bot
from bot_core.utils import format_minutes
from db.database import get_db
from db.models import FeedingRecord, SleepRecord, User

TZ = pytz.timezone("Europe/Moscow")


async def build_statistics_text(chat_id: int) -> str:
    today = datetime.now(TZ).date()

    day_start = datetime.combine(today, time(6, 0)).astimezone(TZ)
    day_end = datetime.combine(today, time(22, 0)).astimezone(TZ)

    week_start = today - timedelta(days=7)
    month_start = today - timedelta(days=30)

    async for db_session in get_db():
        feeds_today = await db_session.execute(
            select(FeedingRecord).where(
                FeedingRecord.chat_id == chat_id,
                func.date(FeedingRecord.timestamp) == today,
            )
        )
        feeds = feeds_today.scalars().all()
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

        sleeps_today = await db_session.execute(
            select(SleepRecord).where(
                SleepRecord.chat_id == chat_id,
                SleepRecord.end_time.isnot(None),
                func.date(SleepRecord.end_time) == today,
            )
        )
        sleeps = sleeps_today.scalars().all()
        day_sleep = night_sleep = 0
        for s in sleeps:
            end_msk = s.end_time.astimezone(TZ)
            duration = int((s.end_time - s.start_time).total_seconds() // 60)
            if day_start <= end_msk <= day_end:
                day_sleep += duration
            else:
                night_sleep += duration

        # Неделя и месяц — питание
        feeds_week = await db_session.execute(
            select(func.sum(FeedingRecord.amount)).where(
                FeedingRecord.chat_id == chat_id, FeedingRecord.timestamp >= week_start
            )
        )
        week_feed = feeds_week.scalar() or 0

        feeds_month = await db_session.execute(
            select(func.sum(FeedingRecord.amount)).where(
                FeedingRecord.chat_id == chat_id, FeedingRecord.timestamp >= month_start
            )
        )
        month_feed = feeds_month.scalar() or 0

        # Сон неделя и месяц
        sleeps_week = await db_session.execute(
            select(SleepRecord).where(
                SleepRecord.chat_id == chat_id,
                SleepRecord.end_time.isnot(None),
                SleepRecord.end_time >= week_start,
            )
        )
        week_sleeps = sleeps_week.scalars().all()
        week_sleep_minutes = sum(
            int((s.end_time - s.start_time).total_seconds() // 60) for s in week_sleeps
        )

        sleeps_month = await db_session.execute(
            select(SleepRecord).where(
                SleepRecord.chat_id == chat_id,
                SleepRecord.end_time.isnot(None),
                SleepRecord.end_time >= month_start,
            )
        )
        month_sleeps = sleeps_month.scalars().all()
        month_sleep_minutes = sum(
            int((s.end_time - s.start_time).total_seconds() // 60) for s in month_sleeps
        )

    return (
        f"📊 <b>Статистика за {today.strftime('%d.%m.%Y')}:</b>\n"
        f"🥛 Питание: День — {day_feed} мл, Ночь — {night_feed} мл\n"
        f"😴 Сон: День — {format_minutes(day_sleep)} мин, Ночь — {format_minutes(night_sleep)} мин\n\n"
        f"📅 За неделю:\n"
        f"🥛 Питание: {week_feed} мл | 😴 Сон: {format_minutes(week_sleep_minutes)} мин\n"
        f"📅 За месяц:\n"
        f"🥛 Питание: {month_feed} мл | 😴 Сон: {format_minutes(month_sleep_minutes)} мин"
    )


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
