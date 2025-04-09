from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

date_choice_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Сегодня"), KeyboardButton(text="Вчера")],
        [KeyboardButton(text="Отмена")],
    ],
    resize_keyboard=True,
)

# Основная клавиатура
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="Сон"), KeyboardButton(text="Питание")],
        [KeyboardButton(text="Статистика")],
    ],
    resize_keyboard=True,
)

# Клавиатура для сна
sleep_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="✅ Подтвердить"), KeyboardButton(text="✏ Изменить время")]
    ],
    resize_keyboard=True,
)

# Клавиатура для записи сна
sleep_actions_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [
            KeyboardButton(text="Завершить сон"),
            KeyboardButton(text="Завершить сон вручную"),
        ],
        [KeyboardButton(text="Питание")],
    ],
    resize_keyboard=True,
)

# Клавиатура для ввода объема питания
feed_keyboard = ReplyKeyboardMarkup(
    keyboard=[[KeyboardButton(text="Отмена")]], resize_keyboard=True
)
