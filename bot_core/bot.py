import asyncio
import logging
import os
from datetime import datetime, timedelta

import pytz
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from dotenv import load_dotenv
from sqlalchemy.future import select

from bot_core.keyboards import (date_choice_keyboard, feed_keyboard,
                                main_keyboard, sleep_actions_keyboard,
                                sleep_keyboard)
from bot_core.states import (ManualEndSleepState, ManualSleepStartState,
                             SleepTimeState)
from bot_core.statistics import build_statistics_text
from db.database import get_db
from db.models import FeedingRecord, SleepRecord, User

# Загружаем переменные окружения
load_dotenv()
BOT_TOKEN: str = os.getenv("BOT_TOKEN", "")
CHAT_ID: str = os.getenv("CHAT_ID", "")

if not BOT_TOKEN:
    raise ValueError("Отсутствует BOT_TOKEN в .env")

# Настраиваем бота и диспетчер
bot: Bot = Bot(token=BOT_TOKEN)
dp: Dispatcher = Dispatcher()

TZ = pytz.timezone("Europe/Moscow")


@dp.message(Command("start"))
async def start_handler(message: Message) -> None:
    chat_id = int(CHAT_ID)
    name = message.from_user.full_name

    async for session in get_db():
        # Проверяем, есть ли пользователь
        result = await session.execute(select(User).where(User.chat_id == chat_id))
        user = result.scalars().first()

        if not user:
            # Создаем нового пользователя
            new_user = User(chat_id=chat_id, name=name)
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
        reply_markup=sleep_keyboard,
    )


@dp.message(lambda message: message.text == "✅ Подтвердить")
async def confirm_sleep_time(message: Message):
    """Фиксируем начало сна с текущим временем и показываем новые кнопки."""
    chat_id = int(CHAT_ID)
    now = datetime.now(TZ)

    async for db_session in get_db():
        result = await db_session.execute(select(User).where(User.chat_id == chat_id))
        user = result.scalars().first()

        if not user:
            await message.answer("Ошибка! Вы не зарегистрированы. Отправьте /start.")
            return

        # Создаем запись о сне
        sleep_record = SleepRecord(
            chat_id=user.chat_id, start_time=now.astimezone(pytz.utc)
        )  # Сохраняем в UTC
        db_session.add(sleep_record)
        await db_session.commit()

    await message.answer(
        "Сон зафиксирован! Когда малыш проснется, нажмите 'Завершить сон'.\n"
        "Вы также можете добавить питание во время сна.",
        reply_markup=sleep_actions_keyboard,  # Используем новую клавиатуру
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

        await message.answer(
            "Выберите дату начала сна:", reply_markup=date_choice_keyboard
        )
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
    chat_id = int(CHAT_ID)
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
        result = await db_session.execute(select(User).where(User.chat_id == chat_id))
        user = result.scalars().first()

        if not user:
            await message.answer("Ошибка! Вы не зарегистрированы. Отправьте /start.")
            await state.clear()
            return

        sleep_record = SleepRecord(chat_id=user.chat_id, start_time=custom_datetime)
        db_session.add(sleep_record)
        await db_session.commit()

        await message.answer("Сон зафиксирован по введенному времени!")
        await message.answer(
            "Когда малыш проснется, нажмите 'Завершить сон'.",
            reply_markup=sleep_actions_keyboard,
        )

    await state.clear()


@dp.message(ManualEndSleepState.waiting_for_date_choice)
async def manual_wake_up_date_choice(message: Message, state: FSMContext):
    chat_id = int(CHAT_ID)
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
        result = await db_session.execute(select(User).where(User.chat_id == chat_id))
        user = result.scalars().first()

        if not user:
            await message.answer("Ошибка! Вы не зарегистрированы. Отправьте /start.")
            await state.clear()
            return

        # Находим активный сон
        result = await db_session.execute(
            select(SleepRecord)
            .where(SleepRecord.chat_id == chat_id, SleepRecord.end_time.is_(None))
            .order_by(SleepRecord.start_time.desc())
        )
        sleep_record = result.scalars().first()

        if not sleep_record:
            await message.answer("Не найдено активного сна.")
            await state.clear()
            return

        if sleep_record.start_time > combined_datetime:
            await message.answer(
                "Время окончания сна не может быть раньше времени начала сна!"
            )
            await state.clear()
            return

        # Записываем завершение сна
        sleep_record.end_time = combined_datetime
        await db_session.commit()

        duration = ((sleep_record.end_time - sleep_record.start_time).seconds) // 60
        await message.answer(
            f"Сон завершен вручную! Продолжительность: {duration} минут.",
            reply_markup=main_keyboard,
        )

    await state.clear()


@dp.message(SleepTimeState.waiting_for_time)
async def manual_sleep_time(message: Message, state: FSMContext):
    """Записывает пользовательское время сна."""
    chat_id = int(CHAT_ID)
    try:
        custom_time = datetime.strptime(message.text, "%H:%M").time()
        custom_datetime = datetime.combine(datetime.today(), custom_time)
        custom_datetime = TZ.localize(custom_datetime)  # Добавляем временную зону

        async for db_session in get_db():  # Открываем сессию БД
            result = await db_session.execute(
                select(User).where(User.chat_id == chat_id)
            )
            user = result.scalars().first()

            if not user:
                await message.answer(
                    "Ошибка! Вы не зарегистрированы. Отправьте /start."
                )
                return

            sleep_record = SleepRecord(
                chat_id=user.chat_id, start_time=custom_datetime.astimezone(pytz.utc)
            )  # Сохраняем в UTC
            db_session.add(sleep_record)
            await db_session.commit()

        await state.clear()  # Сбрасываем состояние
        await message.answer("Сон зафиксирован по введенному времени!")
        await message.answer(
            "Когда малыш проснется, нажмите 'Завершить сон'.",
            reply_markup=sleep_actions_keyboard,
        )
    except ValueError as error:
        await message.answer(f"Ошибка {error}! Введите время в формате HH:MM.")


@dp.message(SleepTimeState.waiting_for_end_time)
async def manual_end_time(message: Message, state: FSMContext):
    """Обрабатывает введенное пользователем время завершения сна с проверкой."""
    chat_id = int(CHAT_ID)
    try:
        # Парсим и локализуем введенное время
        custom_time = datetime.strptime(message.text, "%H:%M").time()
        custom_datetime = datetime.combine(datetime.today(), custom_time)
        custom_datetime = TZ.localize(custom_datetime)  # Применяем временную зону

        async for db_session in get_db():
            result = await db_session.execute(
                select(User).where(User.chat_id == chat_id)
            )
            user = result.scalars().first()

            if not user:
                await message.answer(
                    "Ошибка! Вы не зарегистрированы. Отправьте /start."
                )
                return

            result = await db_session.execute(
                select(SleepRecord)
                .where(
                    SleepRecord.chat_id == user.chat_id, SleepRecord.end_time.is_(None)
                )
                .order_by(SleepRecord.start_time.desc())
            )
            last_sleep = result.scalars().first()

            if not last_sleep:
                await message.answer(
                    "Не найдено активного сна. Используйте кнопку 'Сон' для начала записи."
                )
                return

            # Сравниваем start_time и введённое end_time (обе в UTC)
            custom_utc = custom_datetime.astimezone(pytz.utc)

            if custom_utc <= last_sleep.start_time:
                start_local = last_sleep.start_time.astimezone(TZ).strftime("%H:%M")
                await message.answer(
                    f"Ошибка: время завершения сна не может быть раньше или равно времени начала сна ({start_local}).\n"
                    "Пожалуйста, введите корректное время."
                )
                return

            last_sleep.end_time = custom_utc
            await db_session.commit()

            duration = (
                last_sleep.end_time - last_sleep.start_time
            ).total_seconds() // 60
            await message.answer(f"Сон завершен! Малышка спала {int(duration)} минут.")
            await message.answer("Выберите действие:", reply_markup=main_keyboard)

        await state.clear()  # Сброс состояния

    except ValueError:
        await message.answer(
            "Неверный формат времени. Пожалуйста, введите время в формате HH:MM."
        )


@dp.message(lambda message: message.text == "Завершить сон")
async def wake_up_button(message: Message):
    """Фиксирует окончание сна с текущим временем."""
    chat_id = int(CHAT_ID)
    now_msk = datetime.now(TZ)
    now_utc = now_msk.astimezone(pytz.utc)

    async for db_session in get_db():
        result = await db_session.execute(select(User).where(User.chat_id == chat_id))
        user = result.scalars().first()

        if not user:
            await message.answer("Ошибка! Вы не зарегистрированы. Отправьте /start.")
            return

        result = await db_session.execute(
            select(SleepRecord)
            .where(SleepRecord.chat_id == user.chat_id, SleepRecord.end_time.is_(None))
            .order_by(SleepRecord.start_time.desc())
        )
        last_sleep = result.scalars().first()

        if not last_sleep:
            await message.answer(
                "Не найдено активного сна. Используйте кнопку 'Сон' для начала записи."
            )
            return

        last_sleep.end_time = now_utc
        await db_session.commit()

        duration = (last_sleep.end_time - last_sleep.start_time).total_seconds() // 60
        await message.answer(f"Сон завершен! Малыш спал {int(duration)} минут.")
        await message.answer("Выберите действие:", reply_markup=main_keyboard)


@dp.message(lambda message: message.text == "Питание")
async def ask_feed_amount(message: Message):
    """Запрашивает объем молока, не привязывая к сну, но меняет клавиатуру, если сон активен."""
    await message.answer(
        "Введите объем выпитого молока в мл.", reply_markup=feed_keyboard
    )


@dp.message(lambda message: message.text and message.text.isdigit())
async def save_feed_amount(message: Message):
    """Сохраняет количество молока в базе данных без привязки к сну."""
    feed_amount = int(message.text)

    async for db_session in get_db():
        chat_id = int(CHAT_ID)
        # Записываем питание без проверки сна
        feed_record = FeedingRecord(chat_id=chat_id, amount=feed_amount)
        db_session.add(feed_record)
        await db_session.commit()

        # Проверяем, идет ли сейчас сон
        result = await db_session.execute(
            select(SleepRecord).where(
                SleepRecord.chat_id == chat_id, SleepRecord.end_time.is_(None)
            )
        )
        active_sleep = result.scalars().first()

    reply_markup = sleep_actions_keyboard if active_sleep else main_keyboard

    await message.answer(
        f"Объем питания: {feed_amount} мл сохранен!", reply_markup=reply_markup
    )


@dp.message(lambda message: message.text == "Отмена")
async def cancel_feed(message: Message):
    """Отменяет процесс ввода объема молока и возвращает в главное меню."""
    await message.answer(
        "Ввод отменен. Выберите действие:",
        reply_markup=main_keyboard,  # возвращаемся к стартовой клавиатуре
    )


@dp.message(lambda message: message.text == "Статистика")
async def send_stats_handler(message: Message):
    """Отправляет пользователю статистику за день, неделю и месяц."""
    chat_id = int(CHAT_ID)
    text = await build_statistics_text(chat_id)

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
