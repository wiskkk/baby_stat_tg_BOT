# Используем официальный Python образ
FROM python:3.10-slim

# Устанавливаем рабочую директорию
WORKDIR /app

# Копируем файл зависимостей и устанавливаем их
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь проект в контейнер
COPY . .

# Убедимся, что папка bot_core является пакетом Python
RUN touch bot_core/__init__.py

# Устанавливаем переменную окружения PYTHONPATH, чтобы указать путь для Python
ENV PYTHONPATH=/app

# Открываем порт 8000 для FastAPI (если нужно)
EXPOSE 8000

# Запускаем приложение
CMD ["python", "bot_core/bot.py"]
