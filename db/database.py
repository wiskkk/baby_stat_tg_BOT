import os

from dotenv import load_dotenv
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

# Загружаем переменные окружения
load_dotenv()

# Формируем URL для подключения к PostgreSQL
DB_URL: str = (
    f"postgresql+asyncpg://{os.getenv('DB_USER')}:{os.getenv('DB_PASS')}"
    f"@{os.getenv('DB_HOST', 'postgres')}:{os.getenv('DB_PORT')}/{os.getenv('DB_NAME')}"
)

# Создаем асинхронный движок SQLAlchemy
engine = create_async_engine(DB_URL, echo=True)

# Создаем фабрику сессий
AsyncSessionLocal = sessionmaker(
    bind=engine, class_=AsyncSession, expire_on_commit=False, autocommit=False
)


async def get_db():
    session = AsyncSessionLocal()
    try:
        yield session
    finally:
        await session.close()  # Гарантированное закрытие соединения
