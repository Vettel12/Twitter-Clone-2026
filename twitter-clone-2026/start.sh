#!/bin/bash

# Исправляем права на медиа-папку для nginx/www-data
chmod -R 755 /app/media
chmod -R 644 /app/media/* 2>/dev/null || true

# Запускаем Feed Service (Kafka Consumer) в фоне (&)
# Вывод перенаправляем в основной поток, чтобы видеть логи в docker logs
python -m services.feed.main &

# Запускаем API (основной процесс)
# Если он упадет, контейнер остановится
uvicorn services.gateway.main:app --host 0.0.0.0 --port 8000