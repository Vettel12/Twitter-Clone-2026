# --- Stage 1: Builder ---
FROM python:3.13-slim as builder

WORKDIR /app

# Устанавливаем системные зависимости для сборки (psycopg)
RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev && rm -rf /var/lib/apt/lists/*

# Копируем файл зависимостей
COPY pyproject.toml ./

# === ВАЖНО: Создаем README.md ДО установки зависимостей ===
RUN echo "# Twitter Clone 2026" > README.md

# Устанавливаем зависимости
RUN pip install --no-cache-dir -e .

# Копируем остальной код
COPY . .

# --- Stage 2: Runtime ---
FROM python:3.13-slim as runtime

WORKDIR /app

# === ИСПРАВЛЕНИЕ: Копируем ВСЮ папку usr/local ===
# Это захватывает и lib (библиотеки), и bin (исполняемые файлы uvicorn, alembic)
COPY --from=builder /usr/local /usr/local

# Копируем код приложения
COPY --from=builder /app .

# Создаем папку для медиа
RUN mkdir -p /app/media

# Команда запуска
CMD ["uvicorn", "services.gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]
