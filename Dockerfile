# Используем официальный Python образ
FROM python:3.10-slim

# Устанавливаем зависимости
WORKDIR /app
COPY requirements.txt .

RUN pip install --no-cache-dir -r requirements.txt

# Копируем весь проект в контейнер
COPY . .

# Открываем порт 8000 для FastAPI
EXPOSE 8000

# Запускаем приложение
CMD ["python", "bot/bot.py"]
