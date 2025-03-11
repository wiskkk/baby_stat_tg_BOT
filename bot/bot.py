import asyncio
import logging
import os
from datetime import datetime

import pytz
from aiogram import Bot, Dispatcher
from aiogram.filters import Command
from aiogram.types import KeyboardButton, Message, ReplyKeyboardMarkup
from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

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

# Часовой пояс (Москва, GMT+3)
TZ = pytz.timezone("Europe/Moscow")


def get_current_time() -> str:
    """Возвращает текущее время в формате HH:MM с учетом таймзоны."""
    return datetime.now(TZ).strftime("%H:%M")


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


# Клавиатура с кнопкой завершения сна
async def get_wake_up_keyboard():
    return ReplyKeyboardMarkup(
        keyboard=[
            [KeyboardButton(text="Завершить сон")]
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
async def start_handler(message: Message, session: AsyncSession = get_db()) -> None:
    """Обработчик команды /start. Регистрирует пользователя, если его нет."""
    telegram_id = message.from_user.id
    name = message.from_user.full_name

    async for db_session in session:
        # Проверяем, есть ли пользователь
        result = await db_session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalars().first()

        if not user:
            # Создаем нового пользователя
            new_user = User(telegram_id=telegram_id, name=name)
            db_session.add(new_user)
            await db_session.commit()

    await message.answer("Выберите действие:", reply_markup=main_keyboard)


@dp.message(lambda message: message.text == "Сон")
async def ask_sleep_time(message: Message):
    """Предлагает записать время сна с кнопками подтверждения и изменения."""
    now = get_current_time()
    await message.answer(
        f"Текущее время сна: {now}\n"
        "Нажмите '✅ Подтвердить' для записи или '✏ Изменить время' для ввода вручную.",
        reply_markup=sleep_keyboard
    )


@dp.message(lambda message: message.text == "✅ Подтвердить")
async def confirm_sleep_time(message: Message, session: AsyncSession = get_db()):
    """Фиксируем начало сна с текущим временем."""
    telegram_id = message.from_user.id
    now = datetime.now(TZ)

    async for db_session in session:
        result = await db_session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalars().first()

        if not user:
            await message.answer("Ошибка! Вы не зарегистрированы. Отправьте /start.")
            return

        # Создаем запись о сне
        sleep_record = SleepRecord(user_id=user.id, start_time=now)
        db_session.add(sleep_record)
        await db_session.commit()

    await message.answer(
        "Сон зафиксирован! Когда малыш проснется, нажмите 'Завершить сон'.",
        reply_markup=await get_wake_up_keyboard()
    )


@dp.message(lambda message: message.text == "✏ Изменить время")
async def change_sleep_time(message: Message):
    """Просит пользователя ввести время вручную."""
    await message.answer("Введите новое время в формате HH:MM.")


@dp.message(lambda message: message.text and ":" in message.text)
async def manual_sleep_time(message: Message, session: AsyncSession = get_db()):
    """Записывает сон с пользовательским временем."""
    telegram_id = message.from_user.id
    try:
        custom_time = datetime.strptime(
            message.text, "%H:%M").time()  # Парсим только время
        custom_datetime = datetime.combine(
            datetime.today(), custom_time, tzinfo=TZ)  # Добавляем дату и зону

        async for db_session in session:
            result = await db_session.execute(select(User).where(User.telegram_id == telegram_id))
            user = result.scalars().first()

            if not user:
                await message.answer("Ошибка! Вы не зарегистрированы. Отправьте /start.")
                return

            # Создаем запись о сне
            sleep_record = SleepRecord(
                user_id=user.id, start_time=custom_datetime)
            db_session.add(sleep_record)
            await db_session.commit()

        await message.answer("Сон зафиксирован по введенному времени!")
        await message.answer(
            "Когда малыш проснется, нажмите 'Завершить сон'.",
            reply_markup=await get_wake_up_keyboard()
        )
    except ValueError:
        await message.answer("Ошибка! Введите время в формате HH:MM.")


@dp.message(lambda message: message.text == "Завершить сон")
async def wake_up_button(message: Message, session: AsyncSession = get_db()):
    """Фиксируем окончание сна при нажатии на кнопку"""
    telegram_id = message.from_user.id

    async for db_session in session:
        # Ищем пользователя
        result = await db_session.execute(select(User).where(User.telegram_id == telegram_id))
        user = result.scalars().first()

        if not user:
            await message.answer("Ошибка! Вы не зарегистрированы. Отправьте /start.")
            return

        # Ищем последний активный сон
        result = await db_session.execute(
            select(SleepRecord)
            .where(SleepRecord.user_id == user.id, SleepRecord.end_time.is_(None))
            .order_by(SleepRecord.start_time.desc())
        )
        last_sleep = result.scalars().first()

        if not last_sleep:
            await message.answer("Не найдено активного сна. Используйте команду /sleep для начала записи.")
            return

        last_sleep.end_time = datetime.now(TZ)
        await db_session.commit()

        duration = (last_sleep.end_time - last_sleep.start_time).seconds // 60  # минуты
        await message.answer(f"Сон завершен! Малышка спала {duration} минут.")
    await message.answer("Выберите действие:", reply_markup=main_keyboard)



@dp.message(lambda message: message.text == "Завершить сон")
async def wake_up_button(message: Message, session: AsyncSession = get_db()):
    """Фиксируем окончание сна при нажатии на кнопку"""
    user_id = message.from_user.id

    # Получаем активный сон
    async for db_session in session:
        result = await db_session.execute(
            select(SleepRecord)
            .where(SleepRecord.user_id == user_id, SleepRecord.end_time.is_(None))
            .order_by(SleepRecord.start_time.desc())
        )
        last_sleep = result.scalars().first()

        if not last_sleep:
            await message.answer("Не найдено активного сна. Используйте команду /sleep для начала записи.")
            return

        last_sleep.end_time = datetime.now()
        await db_session.commit()

        duration = (last_sleep.end_time -
                    last_sleep.start_time).seconds // 60  # минуты
        await message.answer(f"Сон завершен! Малышка спала {duration} минут.")
    await message.answer(
        "Выберите действие:",
        reply_markup=main_keyboard
    )


@dp.message(lambda message: message.text == "Питание")
async def ask_feed_amount(message: Message):
    """Запрашивает объем молока для записи."""
    await message.answer(
        "Введите объем выпитого молока в мл (например, 120).",
        reply_markup=feed_keyboard  # клавиатура с кнопкой "Отмена"
    )


@dp.message(lambda message: message.text.isdigit())
async def save_feed_amount(message: Message, session: AsyncSession = get_db()):
    """Сохраняет количество молока в базе данных."""
    telegram_id = message.from_user.id
    try:
        feed_amount = int(message.text)

        async for db_session in session:
            result = await db_session.execute(select(User).where(User.telegram_id == telegram_id))
            user = result.scalars().first()

            if not user:
                await message.answer("Ошибка! Вы не зарегистрированы. Отправьте /start.")
                return

            # Создаем запись о кормлении
            feed_record = FeedingRecord(
                user_id=user.id, amount=feed_amount, timestamp=datetime.now(TZ))
            db_session.add(feed_record)
            await db_session.commit()

        await message.answer(
            f"Объем питания: {feed_amount} мл сохранен! Выберите следующее действие.",
            reply_markup=main_keyboard
        )
    except ValueError:
        await message.answer("Ошибка! Введите число, например: 120.")


@dp.message(lambda message: message.text == "Отмена")
async def cancel_feed(message: Message):
    """Отменяет процесс ввода объема молока и возвращает в главное меню."""
    await message.answer(
        "Ввод отменен. Выберите действие:",
        reply_markup=main_keyboard  # возвращаемся к стартовой клавиатуре
    )


async def main() -> None:
    """Запуск бота."""
    logging.basicConfig(level=logging.INFO)
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
