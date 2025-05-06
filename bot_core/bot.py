import asyncio
import logging
import os

import pytz
from aiogram import Dispatcher

from bot_core.bot_instance import bot
from bot_core.handlers import (feeding_router, plots_router, sleep_router,
                               start_router, stats_router)

dp: Dispatcher = Dispatcher()

TZ = pytz.timezone("Europe/Moscow")


dp.include_router(sleep_router)
dp.include_router(start_router)
dp.include_router(feeding_router)
dp.include_router(stats_router)
dp.include_router(plots_router)


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
