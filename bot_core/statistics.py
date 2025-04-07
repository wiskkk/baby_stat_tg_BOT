from datetime import datetime, time, timedelta

import pytz
from sqlalchemy.future import select

from db.database import get_db
from db.models import FeedingRecord, SleepRecord

TZ = pytz.timezone("Europe/Moscow")


async def collect_daily_feeding_statistics(chat_id: int, date: datetime) -> dict:
    """
    Собирает статистику по питанию за указанный день.

    :param user_id: Telegram ID пользователя
    :param date: Дата в МСК
    :return: Словарь с объемом питания днем и ночью
    """
    # Границы суток в МСК
    start_of_day_msk = datetime.combine(date.date(), time(0, 0))
    end_of_day_msk = start_of_day_msk + timedelta(days=1)

    # Переводим в UTC
    start_of_day_utc = TZ.localize(start_of_day_msk).astimezone(pytz.utc)
    end_of_day_utc = TZ.localize(end_of_day_msk).astimezone(pytz.utc)

    async for session in get_db():
        # Получаем все записи питания за сутки
        result = await session.execute(
            select(FeedingRecord)
            .where(
                FeedingRecord.chat_id == chat_id,
                FeedingRecord.timestamp >= start_of_day_utc,
                FeedingRecord.timestamp < end_of_day_utc
            )
        )
        feeding_records = result.scalars().all()

    day_ml = 0
    night_ml = 0

    for record in feeding_records:
        # Переводим время записи в МСК
        record_time_msk = record.timestamp.astimezone(TZ)
        hour = record_time_msk.hour

        # Ночное питание: с 22:00 до 05:59
        if hour >= 22 or hour < 6:
            night_ml += record.amount
        else:
            day_ml += record.amount

    return {
        "date": date.strftime("%d.%m.%Y"),
        "feeding": {
            "day_ml": day_ml,
            "night_ml": night_ml,
            "total_ml": day_ml + night_ml
        }
    }


async def collect_daily_sleep_statistics(chat_id: int, date: datetime) -> dict:
    """
    Собирает статистику по сну за указанный день.

    :param user_id: Telegram ID пользователя
    :param date: Дата в МСК
    :return: Словарь с длительностью сна днем и ночью (в минутах)
    """
    # Границы суток в МСК
    start_of_day_msk = datetime.combine(date.date(), time(0, 0))
    end_of_day_msk = start_of_day_msk + timedelta(days=1)

    start_of_day_utc = TZ.localize(start_of_day_msk).astimezone(pytz.utc)
    end_of_day_utc = TZ.localize(end_of_day_msk).astimezone(pytz.utc)

    async for session in get_db():
        # Получаем записи сна, которые закончились в этот день
        result = await session.execute(
            select(SleepRecord)
            .where(
                SleepRecord.chat_id == chat_id,
                SleepRecord.end_time >= start_of_day_utc,
                SleepRecord.end_time < end_of_day_utc
            )
        )
        sleep_records = result.scalars().all()

    day_sleep_minutes = 0
    night_sleep_minutes = 0

    for record in sleep_records:
        if not record.start_time or not record.end_time:
            continue

        # Переводим время завершения в МСК
        end_time_msk = record.end_time.astimezone(TZ)
        hour = end_time_msk.hour

        duration = int(
            (record.end_time - record.start_time).total_seconds() // 60)

        if 22 <= hour or hour < 6:
            night_sleep_minutes += duration
        else:
            day_sleep_minutes += duration

    return {
        "sleep": {
            "day_minutes": day_sleep_minutes,
            "night_minutes": night_sleep_minutes,
            "total_minutes": day_sleep_minutes + night_sleep_minutes
        }
    }


async def collect_full_daily_statistics(chat_id: int, date: datetime) -> dict:
    """
    Собирает полную статистику по питанию и сну за день.

    :param user_id: Telegram ID пользователя
    :param date: Дата в МСК
    :return: Объединенный словарь с итогами
    """
    feeding_stats = await collect_daily_feeding_statistics(chat_id, date)
    sleep_stats = await collect_daily_sleep_statistics(chat_id, date)

    full_stats = {
        "date": feeding_stats["date"],
        "feeding": feeding_stats["feeding"],
        "sleep": sleep_stats["sleep"]
    }
    return full_stats