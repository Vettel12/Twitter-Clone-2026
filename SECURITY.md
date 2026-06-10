# 🔐 Безопасность — Анализ проекта

> Детальный аудит безопасности Twitter Clone 2026.

---

## 📊 Сводка

| Категория | Статус | Детали |
|-----------|--------|--------|
| **Bandit scan** | ✅ 0 issues | Статический анализ не выявил уязвимостей |
| **SQL-инъекции** | ✅ Защищено | SQLAlchemy ORM с параметризированными запросами |
| **XSS** | ✅ Защищено | JSON API, фронтенд экранирует данные |
| **Security Headers** | ✅ Реализовано | X-Content-Type-Options, X-Frame-Options, HSTS |
| **API-ключи** | ✅ Хешируются | SHA-256 (см. недостатки ниже) |
| **Секреты** | ⚠️ Требует внимания | `.env` в `.gitignore`, но `.env` уже в истории коммитов |
| **HTTPS/TLS** | 🔴 Не настроено | Ingress без TLS |
| **Rate Limiting** | 🟢 Nginx | Можно реализовать через Nginx Ingress (`limit-rps`) или SlowAPI |
| **PostgreSQL** | ✅ Обычный пользователь | Пользователь `skillbox` без SUPERUSER прав (безопасно) |
| **Kubernetes Secrets** | ⚠️ Base64 ≠ шифрование | `02-secrets.yaml` содержит реальные значения |

---

## ✅ Реализовано правильно

### 1. Хеширование API-ключей
Ключи не хранятся в открытом виде. При аутентификации хешируется входящий ключ и сравнивается с хешем в БД.

### 2. Non-root контейнеры
```yaml
securityContext:
  runAsUser: 1000
  allowPrivilegeEscalation: false
```
Контейнеры работают от непривилегированного пользователя `appuser`.

### 3. Валидация загружаемых файлов
- Проверка расширения (`.jpg`, `.png`, `.gif`, `.webp`)
- Проверка размера (макс. 10 МБ)
- Проверка «магических байтов» (JPEG/PNG/GIF signatures)
- Уникальное имя файла (UUID v4)

### 4. CORS с конфигурируемыми ограничениями
```python
allow_origins = ["http://localhost:3000"]  # Не "*"
allow_credentials = False
```

### 5. Защита от N+1 запросов
`selectinload` в SQLAlchemy — все связи загружаются отдельными запросами, а не в цикле.

### 6. Обработка ошибок
Глобальный exception handler не раскрывает детали клиенту:
```json
{"result": false, "error_type": "InternalServerError", "error_message": "An unexpected error occurred."}
```

### 7. Security Headers (Nginx + FastAPI)
| Заголовок | Значение | Назначение |
|-----------|----------|------------|
| `X-Content-Type-Options` | `nosniff` | Запрет MIME-sniffing |
| `X-Frame-Options` | `DENY` | Защита от clickjacking |
| `X-XSS-Protection` | `1; mode=block` | Фильтр XSS в браузере |
| `Strict-Transport-Security` | `max-age=31536000` | Принудительный HTTPS |

---

## ⚠️ Недостатки и риски

### 1. SHA-256 без соли для API-ключей 🔴 HIGH

```python
# Текущая реализация
def hash_api_key(api_key: str) -> str:
    return sha256(api_key.encode()).hexdigest()  # Без соли, 1 раунд
```

**Риск:** Rainbow table атака. При утечке БД злоумышленник может подобрать ключи.

**Рекомендация:** PBKDF2 или bcrypt с солью и ≥100,000 раундов.

### 2. Секреты в Git-истории 🔴 CRITICAL

Файл `.env` был закоммичен и удалён через `git rm --cached`, но **остался в истории**.

**Рекомендация:**
```bash
# Очистка истории
git filter-repo --invert-paths --path .env --path deploy/k8s/02-secrets.yaml
# + ротация всех паролей
```

### 3. Нет Rate Limiting 🔴 HIGH

Нет защиты от:
- Подбора API-ключей (brute-force)
- Спам-запросов к `/api/tweets`
- Массовых лайков/подписок

**Рекомендация:** `slowapi` или Nginx `limit_req_zone`.

### 4. Нет HTTPS/TLS 🟡 MEDIUM

Ingress не содержит TLS-конфигурации. API-ключи передаются открытым текстом.

**Рекомендация:** cert-manager + Let's Encrypt.

### 5. Redis без аутентификации 🟡 MEDIUM

```yaml
image: redis:7-alpine
# Нет --requirepass
```

Любой pod в кластере может читать/писать все ключи Redis.

### 6. Kafka PLAINTEXT 🟡 MEDIUM

```yaml
KAFKA_LISTENER_SECURITY_PROTOCOL_MAP: "PLAINTEXT:PLAINTEXT"
```

События (создание твитов) передаются без шифрования.

### 7. Rate Limiting — можно реализовать в Nginx 🟢 LOW

Rate Limiting можно настроить на уровне Nginx (Ingress Controller) в Kubernetes:
```yaml
# В Ingress аннотациях
nginx.ingress.kubernetes.io/limit-rps: "10"
```

Для Docker Compose — добавить Nginx reverse proxy с `limit_req_zone`.

**Рекомендация:** Реализовать на уровне Nginx для простоты, либо `slowapi` для granular контроля.

---

## 🛠️ Рекомендации по приоритету

| Приоритет | Действие | Сложность |
|-----------|----------|-----------|
| 1 | Ротация всех секретов + очистка git-истории | Средняя |
| 2 | Добавить TLS в Ingress | Низкая |
| 3 | PBKDF2 для API-ключей | Средняя |
| 4 | Redis `--requirepass` | Низкая |
| 5 | Rate Limiting через Nginx/SlowAPI | Низкая |
| 6 | Kafka SASL_SSL | Высокая |
