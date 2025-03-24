import asyncio
import logging
import os
from datetime import datetime, time, timedelta

import aiocron
import pytz
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import (KeyboardButton, Message, ReplyKeyboardMarkup,
                           ReplyKeyboardRemove)
from dotenv import load_dotenv
from sqlalchemy import func
from sqlalchemy.future import select

from bot_core.statistics import collect_full_daily_statistics
from db.database import get_db
from db.models import FeedingRecord, SleepRecord, User

# Загружаем переменные окружения
load_dotenv()
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")

if not BOT_TOKEN:
    raise ValueError("Отсутствует BOT_TOKEN в .env")

# Настраиваем бота и диспетчер
bot: Bot = Bot(token=BOT_TOKEN)
dp: Dispatcher = Dispatcher()

TZ = pytz.timezone("Europe/Moscow")


async def send_daily_statistics(user_id: int):
    today_msk = datetime.now(TZ)
    stats = await collect_full_daily_statistics(user_id, today_msk)

    message = (
        f"📊 Статистика за {stats['date']}:\n\n"
        f"🍼 Питание:\n"
        f"— Днем: {stats['feeding']['day_ml']} мл\n"
        f"— Ночью: {stats['feeding']['night_ml']} мл\n"
        f"— Всего: {stats['feeding']['total_ml']} мл\n\n"
        f"😴 Сон:\n"
        f"— Днем: {stats['sleep']['day_minutes']} мин\n"
        f"— Ночью: {stats['sleep']['night_minutes']} мин\n"
        f"— Всего: {stats['sleep']['total_minutes']} мин"
    )

    await bot.send_message(chat_id=user_id, text=message)

# Установим cron-задачу на 00:00 по Москве
aiocron.crontab('0 0 * * *', func=send_daily_statistics, tz=TZ)


class SleepTimeState(StatesGroup):
    waiting_for_time = State()
    waiting_for_end_time = State()


class ManualSleepStartState(StatesGroup):
    waiting_for_time = State()
    waiting_for_date_choice = State()


class ManualEndSleepState(StatesGroup):
    waiting_for_time = State()
    waiting_for_date_choice = State()


date_choice_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Сегодня"),
         KeyboardButton(text="Вчера")],
        [KeyboardButton(text="Отмена")]
    ],
    resize_keyboard=True
)

# Основная клавиатура
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Сон"), KeyboardButton(text="Питание")],
        [KeyboardButton(text="Статистика")]
    ],
    resize_keyboard=True
)

# Клавиатура для сна
sleep_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="✅ Подтвердить"),
         KeyboardButton(text="✏ Изменить время")]
    ],
    resize_keyboard=True
)

# Клавиатура для записи сна
sleep_actions_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Завершить сон"),
         KeyboardButton(text="Завершить сон вручную")],
        [KeyboardButton(text="Питание")]
    ],
    resize_keyboard=True
)

# Клавиатура для ввода объема питания
feed_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Отмена")]
    ],
    resize_keyboard=True
)


@dp.message(Command("start"))
async def start_handler(message: Message) -> None:
    telegram_id = message.from_user.id
    name = message.from_user.full_name

    async for session in get_db():
        # Проверяем, есть ли пользователь
        result = await session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalars().first()

        if not user:
            # Создаем нового пользователя
            new_user = User(telegram_id=telegram_id, name=name)
            session.add(new_user)
            await session.commit()

    await message.answer("Выберите действие:", reply_markup=main_keyboard)


@dp.message(lambda message: message.text == "Сон")
async def ask_sleep_time(message: Message):
    """Предлагает записать время сна с кнопками подтверждения и изменения."""
    now = datetime.now(TZ).strftime("%H:%M")
    await message.answer(
        f"Текущее время сна: {now}\n"
        "Нажмите '✅ Подтвердить' для записи или '✏ Изменить время' для ввода вручную.",
        reply_markup=sleep_keyboard
    )


@dp.message(lambda message: message.text == "✅ Подтвердить")
async def confirm_sleep_time(message: Message):
    """Фиксируем начало сна с текущим временем и показываем новые кнопки."""
    telegram_id = message.from_user.id
    now = datetime.now(TZ)

    async for db_session in get_db():
        result = await db_session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalars().first()

        if not user:
            await message.answer("Ошибка! Вы не зарегистрированы. Отправьте /start.")
            return

        # Создаем запись о сне
        sleep_record = SleepRecord(
            user_telegram_id=user.telegram_id, start_time=now.astimezone(pytz.utc))  # Сохраняем в UTC
        db_session.add(sleep_record)
        await db_session.commit()

    await message.answer(
        "Сон зафиксирован! Когда малыш проснется, нажмите 'Завершить сон'.\n"
        "Вы также можете добавить питание во время сна.",
        reply_markup=sleep_actions_keyboard  # Используем новую клавиатуру
    )


@dp.message(lambda message: message.text == "✏ Изменить время")
async def change_sleep_time(message: Message, state: FSMContext):
    await message.answer("Введите время начала сна в формате HH:MM.")
    await state.set_state(ManualSleepStartState.waiting_for_time)


@dp.message(lambda message: message.text == "Завершить сон вручную")
async def manual_wake_up_start(message: Message, state: FSMContext):
    """Запрашиваем время завершения сна вручную."""
    await message.answer("Введите время завершения сна в формате HH:MM.")
    await state.set_state(ManualEndSleepState.waiting_for_time)


@dp.message(ManualSleepStartState.waiting_for_time)
async def manual_sleep_time_input(message: Message, state: FSMContext):
    try:
        custom_time = datetime.strptime(message.text, "%H:%M").time()
        await state.update_data(custom_time=custom_time)
        await state.set_state(ManualSleepStartState.waiting_for_date_choice)

        await message.answer("Выберите дату начала сна:", reply_markup=date_choice_keyboard)
    except ValueError:
        await message.answer("Ошибка! Введите время в формате HH:MM.")


@dp.message(ManualEndSleepState.waiting_for_time)
async def manual_wake_up_time_input(message: Message, state: FSMContext):
    """Сохраняем введенное время и запрашиваем дату."""
    try:
        custom_time = datetime.strptime(message.text, "%H:%M").time()
        await state.update_data(custom_time=custom_time)
        await state.set_state(ManualEndSleepState.waiting_for_date_choice)

        await message.answer("Выберите дату:", reply_markup=date_choice_keyboard)
    except ValueError:
        await message.answer("Ошибка! Введите время в формате HH:MM.")


@dp.message(ManualSleepStartState.waiting_for_date_choice)
async def manual_sleep_date_choice(message: Message, state: FSMContext):
    telegram_id = message.from_user.id
    data = await state.get_data()

    if message.text not in ["Сегодня", "Вчера"]:
        await message.answer("Пожалуйста, выберите 'Сегодня' или 'Вчера'.")
        return

    chosen_date = datetime.today().date()
    if message.text == "Вчера":
        chosen_date -= timedelta(days=1)

    custom_datetime = datetime.combine(chosen_date, data["custom_time"])
    custom_datetime = TZ.localize(custom_datetime).astimezone(pytz.utc)

    async for db_session in get_db():
        result = await db_session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalars().first()

        if not user:
            await message.answer("Ошибка! Вы не зарегистрированы. Отправьте /start.")
            await state.clear()
            return

        sleep_record = SleepRecord(
            user_telegram_id=user.telegram_id,
            start_time=custom_datetime
        )
        db_session.add(sleep_record)
        await db_session.commit()

        await message.answer("Сон зафиксирован по введенному времени!")
        await message.answer("Когда малыш проснется, нажмите 'Завершить сон'.", reply_markup=sleep_actions_keyboard)

    await state.clear()


@dp.message(ManualEndSleepState.waiting_for_date_choice)
async def manual_wake_up_date_choice(message: Message, state: FSMContext):
    telegram_id = message.from_user.id
    data = await state.get_data()

    if message.text not in ["Сегодня", "Вчера"]:
        await message.answer("Пожалуйста, выберите 'Сегодня' или 'Вчера'.")
        return

    # Получаем дату и объединяем с временем
    chosen_date = datetime.today().date()
    if message.text == "Вчера":
        chosen_date = chosen_date - timedelta(days=1)

    combined_datetime = datetime.combine(chosen_date, data["custom_time"])
    combined_datetime = TZ.localize(combined_datetime).astimezone(pytz.utc)

    async for db_session in get_db():
        result = await db_session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalars().first()

        if not user:
            await message.answer("Ошибка! Вы не зарегистрированы. Отправьте /start.")
            await state.clear()
            return

        # Находим активный сон
        result = await db_session.execute(
            select(SleepRecord)
            .where(SleepRecord.user_telegram_id == telegram_id, SleepRecord.end_time.is_(None))
            .order_by(SleepRecord.start_time.desc())
        )
        sleep_record = result.scalars().first()

        if not sleep_record:
            await message.answer("Не найдено активного сна.")
            await state.clear()
            return

        if sleep_record.start_time > combined_datetime:
            await message.answer("Время окончания сна не может быть раньше времени начала сна!")
            await state.clear()
            return

        # Записываем завершение сна
        sleep_record.end_time = combined_datetime
        await db_session.commit()

        duration = ((sleep_record.end_time -
                    sleep_record.start_time).seconds) // 60
        await message.answer(f"Сон завершен вручную! Продолжительность: {duration} минут.", reply_markup=main_keyboard)

    await state.clear()


@dp.message(SleepTimeState.waiting_for_time)
async def manual_sleep_time(message: Message, state: FSMContext):
    """Записывает пользовательское время сна."""
    telegram_id = message.from_user.id
    try:
        custom_time = datetime.strptime(message.text, "%H:%M").time()
        custom_datetime = datetime.combine(datetime.today(), custom_time)
        custom_datetime = TZ.localize(
            custom_datetime)  # Добавляем временную зону

        async for db_session in get_db():  # Открываем сессию БД
            result = await db_session.execute(select(User).where(User.telegram_id == telegram_id))
            user = result.scalars().first()

            if not user:
                await message.answer("Ошибка! Вы не зарегистрированы. Отправьте /start.")
                return

            sleep_record = SleepRecord(
                user_telegram_id=user.telegram_id, start_time=custom_datetime.astimezone(pytz.utc))  # Сохраняем в UTC
            db_session.add(sleep_record)
            await db_session.commit()

        await state.clear()  # Сбрасываем состояние
        await message.answer("Сон зафиксирован по введенному времени!")
        await message.answer("Когда малыш проснется, нажмите 'Завершить сон'.", reply_markup=sleep_actions_keyboard)
    except ValueError as error:
        await message.answer(f"Ошибка {error}! Введите время в формате HH:MM.")


@dp.message(SleepTimeState.waiting_for_end_time)
async def manual_end_time(message: Message, state: FSMContext):
    """Обрабатывает введенное пользователем время завершения сна с проверкой."""
    telegram_id = message.from_user.id
    try:
        # Парсим и локализуем введенное время
        custom_time = datetime.strptime(message.text, "%H:%M").time()
        custom_datetime = datetime.combine(datetime.today(), custom_time)
        custom_datetime = TZ.localize(
            custom_datetime)  # Применяем временную зону

        async for db_session in get_db():
            result = await db_session.execute(
                select(User).where(User.telegram_id == telegram_id)
            )
            user = result.scalars().first()

            if not user:
                await message.answer("Ошибка! Вы не зарегистрированы. Отправьте /start.")
                return

            result = await db_session.execute(
                select(SleepRecord)
                .where(SleepRecord.user_telegram_id == user.telegram_id, SleepRecord.end_time.is_(None))
                .order_by(SleepRecord.start_time.desc())
            )
            last_sleep = result.scalars().first()

            if not last_sleep:
                await message.answer("Не найдено активного сна. Используйте кнопку 'Сон' для начала записи.")
                return

            # Сравниваем start_time и введённое end_time (обе в UTC)
            custom_utc = custom_datetime.astimezone(pytz.utc)

            if custom_utc <= last_sleep.start_time:
                start_local = last_sleep.start_time.astimezone(
                    TZ).strftime("%H:%M")
                await message.answer(
                    f"Ошибка: время завершения сна не может быть раньше или равно времени начала сна ({start_local}).\n"
                    "Пожалуйста, введите корректное время."
                )
                return

            last_sleep.end_time = custom_utc
            await db_session.commit()

            duration = (last_sleep.end_time -
                        last_sleep.start_time).total_seconds() // 60
            await message.answer(f"Сон завершен! Малышка спала {int(duration)} минут.")
            await message.answer("Выберите действие:", reply_markup=main_keyboard)

        await state.clear()  # Сброс состояния

    except ValueError:
        await message.answer("Неверный формат времени. Пожалуйста, введите время в формате HH:MM.")


@dp.message(lambda message: message.text == "Завершить сон")
async def wake_up_button(message: Message):
    """Фиксирует окончание сна с текущим временем."""
    telegram_id = message.from_user.id
    now_msk = datetime.now(TZ)
    now_utc = now_msk.astimezone(pytz.utc)

    async for db_session in get_db():
        result = await db_session.execute(
            select(User).where(User.telegram_id == telegram_id)
        )
        user = result.scalars().first()

        if not user:
            await message.answer("Ошибка! Вы не зарегистрированы. Отправьте /start.")
            return

        result = await db_session.execute(
            select(SleepRecord)
            .where(SleepRecord.user_telegram_id == user.telegram_id, SleepRecord.end_time.is_(None))
            .order_by(SleepRecord.start_time.desc())
        )
        last_sleep = result.scalars().first()

        if not last_sleep:
            await message.answer("Не найдено активного сна. Используйте кнопку 'Сон' для начала записи.")
            return

        last_sleep.end_time = now_utc
        await db_session.commit()

        duration = (last_sleep.end_time -
                    last_sleep.start_time).total_seconds() // 60
        await message.answer(f"Сон завершен! Малыш спал {int(duration)} минут.")
        await message.answer("Выберите действие:", reply_markup=main_keyboard)


@dp.message(lambda message: message.text == "Питание")
async def ask_feed_amount(message: Message):
    """Запрашивает объем молока, не привязывая к сну, но меняет клавиатуру, если сон активен."""
    await message.answer(
        "Введите объем выпитого молока в мл (например, 120).",
        reply_markup=feed_keyboard
    )


@dp.message(lambda message: message.text.isdigit())
async def save_feed_amount(message: Message):
    """Сохраняет количество молока в базе данных без привязки к сну."""
    telegram_id = message.from_user.id
    feed_amount = int(message.text)

    async for db_session in get_db():
        # Записываем питание без проверки сна
        feed_record = FeedingRecord(
            user_telegram_id=telegram_id, amount=feed_amount)
        db_session.add(feed_record)
        await db_session.commit()

        # Проверяем, идет ли сейчас сон
        result = await db_session.execute(
            select(SleepRecord)
            .where(SleepRecord.user_telegram_id == telegram_id, SleepRecord.end_time.is_(None))
        )
        active_sleep = result.scalars().first()

    reply_markup = sleep_actions_keyboard if active_sleep else main_keyboard

    await message.answer(
        f"Объем питания: {feed_amount} мл сохранен!",
        reply_markup=reply_markup
    )


@dp.message(lambda message: message.text == "Отмена")
async def cancel_feed(message: Message):
    """Отменяет процесс ввода объема молока и возвращает в главное меню."""
    await message.answer(
        "Ввод отменен. Выберите действие:",
        reply_markup=main_keyboard  # возвращаемся к стартовой клавиатуре
    )


@dp.message(lambda message: message.text == "Статистика")
async def send_stats_handler(message: Message):
    """Отправляет пользователю статистику за день, неделю и месяц."""
    telegram_id = message.from_user.id
    today = datetime.now(TZ).date()

    # Границы дней
    day_start = datetime.combine(today, time(6, 0)).astimezone(TZ)
    day_end = datetime.combine(today, time(22, 0)).astimezone(TZ)

    # Границы недели и месяца
    week_start = today - timedelta(days=7)
    month_start = today - timedelta(days=30)

    async for db_session in get_db():
        # === ПИТАНИЕ за сегодня ===
        feeds_today = await db_session.execute(
            select(FeedingRecord)
            .where(FeedingRecord.user_telegram_id == telegram_id,
                   func.date(FeedingRecord.timestamp) == today)
        )
        feeds = feeds_today.scalars().all()
        day_feed = sum(f.amount for f in feeds if day_start <=
                       f.timestamp.astimezone(TZ) <= day_end)
        night_feed = sum(f.amount for f in feeds if not (
            day_start <= f.timestamp.astimezone(TZ) <= day_end))

        # === СОН за сегодня ===
        sleeps_today = await db_session.execute(
            select(SleepRecord)
            .where(SleepRecord.user_telegram_id == telegram_id,
                   SleepRecord.end_time.isnot(None),
                   func.date(SleepRecord.end_time) == today)
        )
        sleeps = sleeps_today.scalars().all()

        day_sleep = 0
        night_sleep = 0
        for s in sleeps:
            end_msk = s.end_time.astimezone(TZ)
            duration = int((s.end_time - s.start_time).total_seconds() // 60)
            if day_start <= end_msk <= day_end:
                day_sleep += duration
            else:
                night_sleep += duration

        # === Питание за неделю и месяц ===
        feeds_week = await db_session.execute(
            select(func.sum(FeedingRecord.amount))
            .where(FeedingRecord.user_telegram_id == telegram_id,
                   FeedingRecord.timestamp >= week_start)
        )
        week_feed = feeds_week.scalar() or 0

        feeds_month = await db_session.execute(
            select(func.sum(FeedingRecord.amount))
            .where(FeedingRecord.user_telegram_id == telegram_id,
                   FeedingRecord.timestamp >= month_start)
        )
        month_feed = feeds_month.scalar() or 0

        # === Сон за неделю и месяц ===
        sleeps_week = await db_session.execute(
            select(SleepRecord)
            .where(SleepRecord.user_telegram_id == telegram_id,
                   SleepRecord.end_time.isnot(None),
                   SleepRecord.end_time >= week_start)
        )
        week_sleeps = sleeps_week.scalars().all()
        week_sleep_minutes = sum(
            int((s.end_time - s.start_time).total_seconds() // 60) for s in week_sleeps)

        sleeps_month = await db_session.execute(
            select(SleepRecord)
            .where(SleepRecord.user_telegram_id == telegram_id,
                   SleepRecord.end_time.isnot(None),
                   SleepRecord.end_time >= month_start)
        )
        month_sleeps = sleeps_month.scalars().all()
        month_sleep_minutes = sum(
            int((s.end_time - s.start_time).total_seconds() // 60) for s in month_sleeps)

    # Формируем отчет
    text = (
        f"📊 <b>Статистика за {today.strftime('%d.%m.%Y')}:</b>\n"
        f"🥛 Питание: День — {day_feed} мл, Ночь — {night_feed} мл\n"
        f"😴 Сон: День — {day_sleep} мин, Ночь — {night_sleep} мин\n\n"
        f"📅 За неделю:\n"
        f"🥛 Питание: {week_feed} мл | 😴 Сон: {week_sleep_minutes} мин\n"
        f"📅 За месяц:\n"
        f"🥛 Питание: {month_feed} мл | 😴 Сон: {month_sleep_minutes} мин"
    )

    await message.answer(text, parse_mode="HTML", reply_markup=main_keyboard)


async def on_startup() -> None:
    """Функции, выполняемые перед запуском бота."""
    logging.info("Бот запущен и готов к работе!")


async def main() -> None:
    """Запуск бота."""
    logging.basicConfig(level=logging.INFO)  # Настроим логирование
    await on_startup()  # Вызываем стартовые функции перед запуском
    await dp.start_polling(bot)  # Запускаем бота

if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
