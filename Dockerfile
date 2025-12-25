FROM python:3.14-slim

WORKDIR /app

# Установка системных зависимостей
RUN DEBIAN_FRONTEND=noninteractive apt-get update && apt-get install -y --no-install-recommends \
    curl \
    build-essential \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# Копируем зависимости
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Копируем код
COPY backend/ ./backend/
COPY shared/ ./shared/
COPY frontend/ ./frontend/
COPY frontend-v2.5/ ./frontend-v2.5/
COPY frontend-v2.6/ ./frontend-v2.6/
COPY frontend-v2.7/ ./frontend-v2.7/

WORKDIR /app/backend

# Добавляем /app в PYTHONPATH для импорта модулей из shared
ENV PYTHONPATH=/app

EXPOSE 8000

# Добавляем healthcheck для проверки работоспособности
# Используем Python для проверки, так как он уже установлен
HEALTHCHECK --interval=5s --timeout=3s --start-period=90s --retries=5 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000/health').read()" || exit 1

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--timeout-keep-alive", "5", "--workers", "1", "--log-level", "info"]

