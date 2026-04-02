# --- Stage 1: Builder ---
FROM python:3.13-slim as builder

WORKDIR /app

# Устанавливаем системные зависимости для сборки
RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
# Создаем README, чтобы pip не ругался
RUN echo "# Twitter Clone 2026" > README.md

# Устанавливаем зависимости
RUN pip install --no-cache-dir -e .

COPY . .

# --- Stage 2: Runtime ---
FROM python:3.13-slim as runtime

WORKDIR /app

# === БЕЗОПАСНОСТЬ: Создаем пользователя ===
# Это лучшая практика (Non-root container)
RUN adduser --disabled-password --gecos '' appuser

# Копируем Python и зависимости
COPY --from=builder /usr/local /usr/local

# Копируем код приложения
COPY --from=builder /app .

# === ПРАВА ДОСТУПА (FIX PERMISSIONS) ===
# 1. Создаем папку медиа
RUN mkdir -p /app/media
# 2. Даем права пользователю appuser (UID 1000) на всю папку приложения
RUN chown -R appuser:appuser /app

# Копируем скрипт запуска
COPY start.sh .
RUN chmod +x start.sh

# Переключаемся на пользователя
USER appuser

# Команда запуска
CMD ["./start.sh"]
