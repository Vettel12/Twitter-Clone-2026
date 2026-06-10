# 🔧 Troubleshooting — Проблемы и решения

> Частые ошибки при развёртывании и способы их устранения.

---

## 🐳 Docker Compose

### 1. Контейнеры не запускаются: «Address already in use»

**Симптом:**
```
ERROR: for postgres  Cannot start service postgres: port is already allocated
```

**Причина:** Порты 5433, 6379, 9092 заняты другими процессами.

**Решение:**
```bash
# Найти процесс на порту
netstat -ano | findstr :5433   # Windows
lsof -i :5433                   # Linux/macOS

# Остановить или изменить порт в docker-compose.yml
```

### 2. Kafka не запускается

**Симптом:**
```
kafka_1 | [2026-04-13 12:00:00] ERROR Fatal error during KafkaServer startup
```

**Причина:** Zookeeper ещё не готов, либо конфликт listener'ов.

**Решение:**
```bash
# Перезапустить Kafka после Zookeeper
docker-compose restart kafka

# Проверить логи
docker-compose logs kafka | tail -50

# Полная пересборка
docker-compose down -v
docker-compose up -d --build
```

### 3. «Connection refused» к PostgreSQL из приложения

**Симптом:** Приложение не может подключиться к БД.

**Причина:** `POSTGRES_HOST=postgres` в `.env`, но сервис называется иначе.

**Решение:** Убедитесь, что в `.env`:
```env
POSTGRES_HOST=postgres     # Docker Compose (имя сервиса)
```

### 4. Миграции не применяются

**Симптом:** `alembic upgrade head` падает с ошибкой.

**Решение:**
```bash
# Проверить текущую ревизию
docker-compose exec app alembic current

# Сбросить и применить заново
docker-compose exec app alembic downgrade base
docker-compose exec app alembic upgrade head
```

### 5. Медиафайлы не сохраняются

**Симптом:** Загрузка картинки успешна, но файл не доступен.

**Причина:** Нет volume для `media/` или права доступа.

**Решение:**
```bash
# Проверить volume
docker-compose exec app ls -la /app/media

# Исправить права
docker-compose exec app chmod -R 755 /app/media
```

---

## ☸️ Kubernetes

### 1. Pod'ы в состоянии Pending

**Симптом:**
```
$ kubectl get pods -n twitter-clone
NAME                        READY   STATUS    RESTARTS   AGE
backend-6d4f5b8c7-x2k9m     0/1     Pending   0          5m
```

**Причина:** Нет ресурсов (CPU/Memory) или PV не привязан.

**Решение:**
```bash
# Узнать причину
kubectl describe pod backend-6d4f5b8c7-x2k9m -n twitter-clone

# Проверить PV/PVC
kubectl get pvc -n twitter-clone
kubectl get pv

# Если PV не привязан — создать StorageClass
kubectl apply -f - <<EOF
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: hostpath
provisioner: kubernetes.io/no-provisioner
volumeBindingMode: WaitForFirstConsumer
EOF
```

### 2. Init Container завис на «wait-for-infrastructure»

**Симптом:** Init Container бесконечно ждёт Kafka/Postgres.

**Причина:** Сервисы ещё не запустились или имя сервиса неверно.

**Решение:**
```bash
# Проверить инфраструктуру
kubectl get pods -n twitter-clone -l app=postgres
kubectl get pods -n twitter-clone -l app=kafka
kubectl get pods -n twitter-clone -l app=redis

# Проверить Services
kubectl get svc -n twitter-clone

# Если сервисы не нашли — проверить селекторы
kubectl describe svc kafka-service -n twitter-clone
```

### 3. Ошибка Secrets

**Симптом:**
```
Error: secret "db-credentials" not found
```

**Причина:** Файл `02-secrets.yaml` не применён.

**Решение:**
```bash
# Применить Secrets
kubectl apply -f deploy/k8s/02-secrets.yaml

# Проверить
kubectl get secret db-credentials -n twitter-clone
```

### 4. CrashLoopBackOff

**Симптом:** Pod перезапускается циклически.

**Причина:** Ошибка приложения (нет подключения к БД, миграции не применены и т.д.).

**Решение:**
```bash
# Логи контейнера
kubectl logs deploy/backend -n twitter-clone --tail=100

# Логи предыдущего контейнера (упавшего)
kubectl logs deploy/backend -n twitter-clone --previous --tail=100

# Проверить env
kubectl exec deploy/backend -n twitter-clone -- env | grep POSTGRES
```

### 5. Backend не видит Kafka

**Симптом:** В логах `Failed to connect to kafka-service:29092`.

**Причина:** Kafka ещё не готова или listener настроен неправильно.

**Решение:**
```bash
# Проверить Kafka
kubectl logs deploy/kafka -n twitter-clone --tail=50

# Проверить advertised listeners
kubectl exec deploy/kafka -n twitter-clone -- \
  kafka-configs.sh --bootstrap-server localhost:29092 --describe

# Убедиться что KAFKA_ADVERTISED_LISTENERS=PLAINTEXT://kafka-service:29092
```

---

## 💻 Локальная разработка

### 1. Тесты падают с «Connection refused»

**Симптом:**
```
E   asyncpg.exceptions.CannotConnectNowError: could not connect to server
```

**Причина:** PostgreSQL не запущен или порт не проброшен.

**Решение:**
```bash
# Запустить инфраструктуру
docker-compose up -d postgres redis kafka

# Проверить порты
docker-compose ps

# Запустить тесты
python -m pytest tests/ -v
```

### 2. Alembic не находит модели

**Симптом:**
```
Target database is not up to date.
```

**Причина:** Alembic не видит модели из других пакетов.

**Решение:** Проверить `env.py`:
```python
# migrations/env.py
from services.users.app.models import User  # noqa
from services.tweets.app.models import Tweet, Media, Like  # noqa
```

### 3. Redis singleton и event loop

**Симптом:**
```
RuntimeError: Event loop is closed
```

**Причина:** Redis singleton сохраняется между тестами.

**Решение:** Уже реализовано в `conftest.py`:
```python
def reset_redis_singleton():
    from libs import redis_client as redis_module
    redis_module.redis_client = None
```

---

## 📊 Мониторинг

### 1. Prometheus не скрейпит метрики

**Симптом:** Target `backend` в статусе DOWN.

**Решение:**
```bash
# Проверить endpoint
curl http://backend-service:8000/metrics

# Проверить ServiceMonitor
kubectl get servicemonitor -n twitter-clone
kubectl describe servicemonitor backend-monitor -n twitter-clone

# Проверить аннотации Pod
kubectl get pod -l app=backend -o jsonpath='{.items[0].metadata.annotations}'
```

### 2. Grafana не показывает данные

**Симптом:** Пустые графики.

**Решение:**
```bash
# Проверить Data Source
curl http://localhost:3000/api/datasources -u admin:admin

# Перезапустить Grafana
kubectl rollout restart deploy/grafana -n twitter-clone
```

---

## 🧪 Тесты

### 1. Тесты не находят пользователя «TestUser»

**Симптом:**
```
assert data["user"]["name"] == "TestUser"
AssertionError
```

**Причина:** Фикстура `conftest.py` создаёт пользователя, но сессия не коммитит.

**Решение:** Убедитесь что тест использует фикстуру `db_session`:
```python
async def test_something(db_session: AsyncSession, client: AsyncClient):
    ...
```

### 2. Kafka в тестах блокирует выполнение

**Симптом:** Тест зависает на `await broker.publish()`.

**Решение:** Kafka mocked в `conftest.py`:
```python
with patch("libs.kafka_conf.broker.publish", new_callable=AsyncMock):
    ...
```

---

## 🚨 Быстрые команды

```bash
# Полная пересборка с нуля
docker-compose down -v
docker-compose up -d --build

# Логи всех сервисов
docker-compose logs -f

# Логи только приложения
docker-compose logs -f app

# Войти в контейнер
docker-compose exec app bash

# Проверить здоровье
curl http://localhost:8000/api/healthcheck

# Проверить API
curl -H "api-key: test" http://localhost:8000/api/users/me

# Проверить Swagger
open http://localhost:8000/api/docs

# Запустить тесты
python -m pytest tests/ -v --tb=short

# Проверить линтером
ruff check .
mypy .

# Проверить безопасность
bandit -r services/ libs/

# Нагрузочное тестирование
locust -f locustfile.py --host=http://localhost:8000
```
