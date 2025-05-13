import io
from datetime import datetime, timedelta

import matplotlib.pyplot as plt
import pytz
from sqlalchemy.future import select

from db.database import get_db
from db.models import FeedingRecord, SleepRecord

TZ = pytz.timezone("Europe/Moscow")


async def generate_feeding_plot(chat_id: int, period: str = "7d") -> io.BytesIO:
    """Генерирует график кормлений за указанный период: 7d / 30d / all (90d)."""
    now = datetime.now(TZ)

    if period == "7d":
        start_date = now.date() - timedelta(days=6)
    elif period == "30d":
        start_date = now.date() - timedelta(days=29)
    elif period == "all":
        start_date = now.date() - timedelta(days=89)
    else:
        raise ValueError("Неподдерживаемый период")

    end_date = now.date()
    days_count = (end_date - start_date).days + 1

    dates = [start_date + timedelta(days=i) for i in range(days_count)]
    amounts = [0] * days_count

    async for db_session in get_db():
        result = await db_session.execute(
            select(FeedingRecord).where(
                FeedingRecord.chat_id == chat_id,
                FeedingRecord.timestamp >= start_date,
            )
        )
        records = result.scalars().all()

        for record in records:
            local_date = record.timestamp.astimezone(TZ).date()
            index = (local_date - start_date).days
            if 0 <= index < days_count:
                amounts[index] += record.amount

    # Рисуем график
    fig_width = min(20, max(6, days_count / 6))
    fig, ax = plt.subplots(figsize=(fig_width, 4))
    ax.plot(dates, amounts, marker="o", color="royalblue", linewidth=2)
    ax.set_title(f"Кормления за {days_count} дней")
    ax.set_xlabel("Дата")
    ax.set_ylabel("мл")
    ax.grid(True)

    step = max(1, days_count // 10)
    ax.set_xticks(dates[::step])
    ax.set_xticklabels([d.strftime("%d.%m") for d in dates[::step]], rotation=45)

    buffer = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buffer, format="png")
    buffer.seek(0)
    plt.close(fig)

    return buffer


async def generate_sleep_plot(chat_id: int, period: str = "7d") -> io.BytesIO:
    now = datetime.now(TZ)

    if period == "7d":
        start_date = now.date() - timedelta(days=6)
    elif period == "30d":
        start_date = now.date() - timedelta(days=29)
    elif period == "all":
        start_date = now.date() - timedelta(days=89)
    else:
        raise ValueError("Неподдерживаемый период")

    end_date = now.date()
    days_count = (end_date - start_date).days + 1

    sleep_data = {start_date + timedelta(days=i): 0 for i in range(days_count)}

    async for session in get_db():
        result = await session.execute(
            select(SleepRecord).where(
                SleepRecord.chat_id == chat_id,
                SleepRecord.end_time.isnot(None),
                SleepRecord.end_time
                >= datetime.combine(start_date, datetime.min.time()),
            )
        )
        records = result.scalars().all()

    for record in records:
        date = record.end_time.astimezone(TZ).date()
        duration = int((record.end_time - record.start_time).total_seconds() // 60)
        if date in sleep_data:
            sleep_data[date] += duration

    dates = list(sleep_data.keys())
    values = [round(v / 60, 2) for v in sleep_data.values()]

    fig_width = min(20, max(6, days_count / 6))
    fig, ax = plt.subplots(figsize=(fig_width, 4))
    ax.bar(dates, values, color="#8ab6d6")
    ax.set_title(f"Сон за {days_count} дней")
    ax.set_ylabel("Часы сна")
    ax.set_xlabel("Дата")
    ax.grid(True, axis="y")

    step = max(1, days_count // 10)
    ax.set_xticks(dates[::step])
    ax.set_xticklabels([d.strftime("%d.%m") for d in dates[::step]], rotation=45)

    buffer = io.BytesIO()
    plt.tight_layout()
    plt.savefig(buffer, format="png")
    buffer.seek(0)
    plt.close(fig)

    return buffer
