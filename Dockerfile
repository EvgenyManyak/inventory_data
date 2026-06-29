FROM python:3.10-slim

WORKDIR /app

# Устанавливаем необходимые системные библиотеки
RUN apt-get update && apt-get install -y libpq-dev gcc

# Копируем зависимости
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Код будем запускать из смонтированной папки scripts
CMD ["python", "scripts/main.py"]
