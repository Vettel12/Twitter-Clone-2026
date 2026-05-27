# --- Stage 1: Builder ---
FROM python:3.13-slim as builder

WORKDIR /app

# Устанавливаем системные зависимости для сборки
RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml ./
# Создаем README, чтобы pip не ругался
RUN echo "# Twitter Clone 2026" > README.md

# Копируем весь код перед установкой
COPY . .

# Устанавливаем зависимости
RUN pip install --no-cache-dir -e .

# Перекопируем скрипты чтобы гарантировать обновленную версию
COPY scripts /app/scripts

# --- Stage 2: Runtime ---
FROM python:3.13-slim as runtime

WORKDIR /app

# === Установка bash для запуска скриптов ===
RUN apt-get update && apt-get install -y --no-install-recommends bash && rm -rf /var/lib/apt/lists/*

# === БЕЗОПАСНОСТЬ: Создаем пользователя ===
RUN adduser --disabled-password --gecos '' appuser

# Копируем Python и зависимости
COPY --from=builder /usr/local /usr/local

# Копируем код приложения
COPY --from=builder /app .

# === ПРАВА ДОСТУПА (FIX PERMISSIONS) ===
RUN mkdir -p /app/media && chmod 777 /app/media
RUN chown -R appuser:appuser /app

# Копируем скрипты и исправляем CRLF -> LF
COPY entrypoint.sh .
COPY start.sh .
RUN sed -i 's/\r$//' entrypoint.sh && chmod +x entrypoint.sh
RUN sed -i 's/\r$//' start.sh && chmod +x start.sh

# Переключаемся на пользователя
USER appuser

# Entrypoint + CMD
ENTRYPOINT ["./entrypoint.sh"]
CMD ["./start.sh"]
