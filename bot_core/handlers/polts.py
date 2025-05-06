from aiogram import Router
from aiogram.types import (BufferedInputFile, KeyboardButton, Message,
                           ReplyKeyboardMarkup)

from bot_core.keyboards import main_keyboard
from bot_core.plots import generate_feeding_plot, generate_sleep_plot

router = Router()

# Клавиатура выбора типа диаграммы
diagram_type_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🍼 Кормление"), KeyboardButton(text="😴 Сон")],
        [KeyboardButton(text="🔙 Назад")],
    ],
    resize_keyboard=True,
)

# Клавиатура выбора периода
plot_period_kb = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="📊 За 7 дней")],
        [KeyboardButton(text="📊 За 30 дней")],
        [KeyboardButton(text="📊 За всё время")],
        [KeyboardButton(text="🔙 Назад")],
    ],
    resize_keyboard=True,
)

# Хранилище текущего выбора типа (можно заменить на FSM при необходимости)
user_plot_type = {}


@router.message(lambda m: m.text == "Диаграммы")
async def show_plot_options(message: Message):
    await message.answer("Что вы хотите посмотреть?", reply_markup=diagram_type_kb)


@router.message(lambda m: m.text in {"🍼 Кормление", "😴 Сон"})
async def choose_plot_type(message: Message):
    user_plot_type[message.chat.id] = (
        "feeding" if message.text == "🍼 Кормление" else "sleep"
    )
    await message.answer("Выберите период:", reply_markup=plot_period_kb)


@router.message(
    lambda m: m.text in {"📊 За 7 дней", "📊 За 30 дней", "📊 За всё время"}
)
async def send_plot_by_period(message: Message):
    chat_id = int(message.chat.id)
    period_map = {
        "📊 За 7 дней": "7d",
        "📊 За 30 дней": "30d",
        "📊 За всё время": "all",
    }
    period = period_map.get(message.text, "7d")

    plot_type = user_plot_type.get(chat_id)
    if plot_type == "feeding":
        buffer = await generate_feeding_plot(chat_id, period=period)
        caption = f"🍼 Кормления ({message.text})"
    elif plot_type == "sleep":
        buffer = await generate_sleep_plot(chat_id, period=period)
        caption = f"😴 Сон ({message.text})"
    else:
        await message.answer("Ошибка: не выбран тип диаграммы.")
        return

    image = BufferedInputFile(buffer.read(), filename="plot.png")
    await message.answer_photo(photo=image, caption=caption)


@router.message(lambda m: m.text == "🔙 Назад")
async def back_to_main_menu(message: Message):

    await message.answer("Главное меню:", reply_markup=main_keyboard)
