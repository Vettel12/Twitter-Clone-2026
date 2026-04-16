#!/bin/bash
set -e

# === Исправляем права на папку media ===
# При bind mount (docker-compose) или PVC (kubernetes) папка может принадлежать root.
# Appuser (uid=1000) должен иметь право писать в /app/media.
if [ -d "/app/media" ]; then
    # Делаем папку записываемой для всех (безопасно внутри контейнера)
    chmod -R 777 /app/media 2>/dev/null || true
fi

# Запускаем переданный command или start.sh
exec "$@"
