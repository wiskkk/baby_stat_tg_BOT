from aiogram import Router
from aiogram.filters import Command
from aiogram.types import Message
from sqlalchemy.future import select

from bot_core.keyboards import main_keyboard
from db.database import get_db
from db.models import User

router = Router()


@router.message(Command("start"))
async def start_handler(message: Message):
    chat_id = message.chat.id
    name = message.from_user.full_name

    async for session in get_db():
        result = await session.execute(select(User).where(User.chat_id == chat_id))
        user = result.scalars().first()

        if not user:
            session.add(User(chat_id=chat_id, name=name))
            await session.commit()

    await message.answer("Выберите действие:", reply_markup=main_keyboard)
