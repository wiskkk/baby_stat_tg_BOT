from aiogram import Router
from aiogram.types import Message
from sqlalchemy.future import select

from bot_core.keyboards import (feed_keyboard, main_keyboard,
                                sleep_actions_keyboard)
from db.database import get_db
from db.models import FeedingRecord, SleepRecord

router = Router()


@router.message(lambda m: m.text == "Питание")
async def ask_feed_amount(message: Message):
    await message.answer("Введите объем молока в мл.", reply_markup=feed_keyboard)


@router.message(lambda m: m.text and m.text.isdigit())
async def save_feed_amount(message: Message):
    amount = int(message.text)
    chat_id = message.chat.id

    async for db in get_db():
        db.add(FeedingRecord(chat_id=chat_id, amount=amount))
        await db.commit()

        result = await db.execute(
            select(SleepRecord).where(
                SleepRecord.chat_id == chat_id, SleepRecord.end_time.is_(None)
            )
        )
        active_sleep = result.scalars().first()

    markup = sleep_actions_keyboard if active_sleep else main_keyboard
    await message.answer(f"Сохранено: {amount} мл", reply_markup=markup)


@router.message(lambda m: m.text == "Отмена")
async def cancel_feed(message: Message):
    await message.answer("Отмена. Выберите действие:", reply_markup=main_keyboard)
