from aiogram import Router
from aiogram.types import Message

from bot_core.keyboards import main_keyboard
from bot_core.statistics import build_statistics_text

router = Router()


@router.message(lambda m: m.text == "Статистика")
async def send_statistics(message: Message):
    chat_id = message.chat.id
    text = await build_statistics_text(chat_id)
    await message.answer(text, parse_mode="HTML", reply_markup=main_keyboard)
