from datetime import datetime, timedelta

import pytz
from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.types import Message
from sqlalchemy.future import select

from bot_core.bot_instance import CHAT_ID
from bot_core.keyboards import (
    date_choice_keyboard,
    main_keyboard,
    sleep_actions_keyboard,
    sleep_keyboard,
)
from bot_core.states import ManualEndSleepState, ManualSleepStartState
from bot_core.utils import format_minutes
from db.database import get_db
from db.models import SleepRecord, User

TZ = pytz.timezone("Europe/Moscow")
router = Router()


@router.message(lambda m: m.text == "Сон")
async def ask_sleep_time(message: Message):
    now = datetime.now(TZ).strftime("%H:%M")
    await message.answer(
        f"Текущее время сна: {now}\n"
        "Нажмите '✅ Подтвердить' для записи или '✏ Изменить время' для ввода вручную.",
        reply_markup=sleep_keyboard,
    )


@router.message(lambda m: m.text == "✅ Подтвердить")
async def confirm_sleep_time(message: Message):
    now = datetime.now(TZ).astimezone(pytz.utc)
    async for db in get_db():
        user = await db.scalar(select(User).where(User.chat_id == message.chat.id))
        if not user:
            return await message.answer("Вы не зарегистрированы.")
        db.add(SleepRecord(chat_id=user.chat_id, start_time=now))
        await db.commit()

    await message.answer("Сон зафиксирован.", reply_markup=sleep_actions_keyboard)


@router.message(lambda m: m.text == "✏ Изменить время")
async def change_sleep_time(message: Message, state: FSMContext):
    await message.answer("Введите время начала сна (HH:MM):")
    await state.set_state(ManualSleepStartState.waiting_for_time)


@router.message(ManualSleepStartState.waiting_for_time)
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


@router.message(ManualEndSleepState.waiting_for_time)
async def manual_wake_up_time_input(message: Message, state: FSMContext):
    """Сохраняем введенное время и запрашиваем дату."""
    try:
        custom_time = datetime.strptime(message.text, "%H:%M").time()
        await state.update_data(custom_time=custom_time)
        await state.set_state(ManualEndSleepState.waiting_for_date_choice)

        await message.answer("Выберите дату:", reply_markup=date_choice_keyboard)
    except ValueError:
        await message.answer("Ошибка! Введите время в формате HH:MM.")


@router.message(lambda message: message.text == "Завершить сон вручную")
async def manual_wake_up_start(message: Message, state: FSMContext):
    """Запрашиваем время завершения сна вручную."""
    await message.answer("Введите время завершения сна в формате HH:MM.")
    await state.set_state(ManualEndSleepState.waiting_for_time)


@router.message(ManualSleepStartState.waiting_for_date_choice)
async def manual_sleep_date_choice(message: Message, state: FSMContext):
    data = await state.get_data()
    date = datetime.today().date()
    if message.text == "Вчера":
        date -= timedelta(days=1)
    dt = datetime.combine(date, data["custom_time"])
    dt = TZ.localize(dt).astimezone(pytz.utc)

    async for db in get_db():
        user = await db.scalar(select(User).where(User.chat_id == message.chat.id))
        if not user:
            return await message.answer("Вы не зарегистрированы.")
        db.add(SleepRecord(chat_id=user.chat_id, start_time=dt))
        await db.commit()

    await state.clear()
    await message.answer("Сон зафиксирован!", reply_markup=sleep_actions_keyboard)


@router.message(ManualEndSleepState.waiting_for_date_choice)
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
            f"Сон завершён вручную! Продолжительность: {format_minutes(duration)}",
            reply_markup=main_keyboard,
        )

    await state.clear()


@router.message(lambda m: m.text == "Завершить сон")
async def wake_up(message: Message):
    now = datetime.now(TZ).astimezone(pytz.utc)
    async for db in get_db():
        user = await db.scalar(select(User).where(User.chat_id == message.chat.id))
        if not user:
            return await message.answer("Вы не зарегистрированы.")

        result = await db.execute(
            select(SleepRecord)
            .where(SleepRecord.chat_id == user.chat_id, SleepRecord.end_time.is_(None))
            .order_by(SleepRecord.start_time.desc())
        )
        sleep = result.scalars().first()
        if not sleep:
            return await message.answer("Активный сон не найден.")

        sleep.end_time = now
        await db.commit()

        minutes = int((sleep.end_time - sleep.start_time).total_seconds() // 60)
        await message.answer(
            f"Сон завершён! Продолжительность: {format_minutes(minutes)}",
            reply_markup=main_keyboard,
        )
