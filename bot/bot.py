import asyncio
import logging
import os
from datetime import datetime

import pytz
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup
from dotenv import load_dotenv
from sqlalchemy.future import select
from aiogram.fsm.state import StatesGroup, State
from aiogram.fsm.context import FSMContext
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


class SleepTimeState(StatesGroup):
    waiting_for_time = State()
    waiting_for_end_time = State()


# Основная клавиатура
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Сон"), KeyboardButton(text="Питание")]
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
        [KeyboardButton(text="Завершить сон (текущее время)"),
         KeyboardButton(text="Завершить сон (ввести время)")],
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
    """Переводит бота в режим ожидания пользовательского времени."""
    await message.answer("Введите новое время в формате HH:MM.")
    # Устанавливаем состояние
    await state.set_state(SleepTimeState.waiting_for_time)


@dp.message(lambda message: message.text == "Завершить сон (ввести время)")
async def ask_manual_end_time(message: Message, state: FSMContext):
    """Запрашивает у пользователя время завершения сна."""
    await message.answer("Введите время завершения сна в формате HH:MM.")
    await state.set_state(SleepTimeState.waiting_for_end_time)


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


@dp.message(lambda message: message.text == "Завершить сон (текущее время)")
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
