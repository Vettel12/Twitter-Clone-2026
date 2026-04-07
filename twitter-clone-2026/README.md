# 🐦 Twitter Clone 2026 — Микросервисный Backend

> **Полнофункциональный клон Twitter** с микросервисной архитектурой, контейнеризацией и оркестрацией в Kubernetes. Проект демонстрирует современные практики DevOps, разработки и эксплуатации: асинхронный FastAPI, Kafka, Redis, PostgreSQL, Prometheus, Grafana, CI/CD готовность и нагрузочное тестирование.

---

## 📖 Содержание

- [О Проекте](#-о-проекте)
- [Архитектура](#-архитектура)
- [Технологический Стек](#-технологический-стек)
- [API Endpoints](#-api-endpoints)
- [Предварительные Требования](#-предварительные-требования)
- [Быстрый Старт (Docker Compose)](#-быстрый-старт-docker-compose)
- [Production Развертывание (Kubernetes)](#-production-развертывание-kubernetes)
- [Мониторинг и Наблюдаемость](#-мониторинг-и-наблюдаемость)
- [Нагрузочное Тестирование](#-нагрузочное-тестирование)
- [Безопасность](#-безопасность)
- [CI/CD и Качество Кода](#-cicd-и-качество-кода)
- [Устранение Неполадок](#-устранение-неполадок)
- [Структура Проекта](#-структура-проекта)
- [Для Работодателей](#-для-работодателей)

---

## 🎯 О Проекте

Этот проект — **полноценный backend для клона Twitter**, разработанный как дипломная работа курса "Python Advanced" от Skillbox. Он демонстрирует:

| Навык | Реализация |
|-------|------------|
| **Микросервисная архитектура** | Разделение на сервисы пользователей, твитов и лент |
| **Асинхронность** | FastAPI + asyncpg + aioredis |
| **Очереди сообщений** | Apache Kafka для асинхронной обработки событий |
| **Кэширование** | Redis для ускорения отдачи ленты |
| **Контейнеризация** | Multi-stage Docker builds |
| **Оркестрация** | Kubernetes манифесты + Helm |
| **Мониторинг** | Prometheus + Grafana + ServiceMonitor |
| **Нагрузочное тестирование** | Locust сценарии |
| **Безопасность** | Non-root контейнеры, Secrets, SecurityContext |
| **Качество кода** | Ruff, MyPy, Pytest, Bandit |

---

## 🏗 Архитектура

```
┌─────────────────────────────────────────────────────────────────┐
│                        Kubernetes Cluster                        │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────────────┐  │
│  │  Frontend   │    │   Ingress   │    │   API Gateway       │  │
│  │  (React +   │───▶│  (Nginx)    │───▶│   (FastAPI)         │  │
│  │   Nginx)    │    │             │    │   Port: 8000        │  │
│  └─────────────┘    └─────────────┘    └─────────┬───────────┘  │
│                                                   │              │
│                    ┌──────────────────────────────┼──────────┐  │
│                    │                              │          │  │
│  ┌─────────────┐   │  ┌─────────────┐   ┌────────▼───────┐  │  │
│  │ PostgreSQL  │◄──┘  │   Redis     │   │   Apache Kafka │  │  │
│  │ (Users,     │      │  (Cache)    │   │   (Events)     │  │  │
│  │  Tweets)    │      │  Port:6379  │   │   Port: 29092  │  │  │
│  └─────────────┘      └─────────────┘   └────────────────┘  │  │
│                                                              │  │
│  ┌─────────────────────────────────────────────────────────┐ │  │
│  │              Monitoring Stack                           │ │  │
│  │  Prometheus ◄── ServiceMonitor ◄── /metrics endpoint    │ │  │
│  │  Grafana    ◄── Dashboards & Alerts                     │ │  │
│  └─────────────────────────────────────────────────────────┘ │  │
└─────────────────────────────────────────────────────────────────┘
```

### Ключевые компоненты:

| Компонент | Назначение |
|-----------|------------|
| **API Gateway** | Единая точка входа, маршрутизация, аутентификация |
| **Users Service** | Управление пользователями, подписки, профили |
| **Tweets Service** | CRUD твитов, лайки, медиа-вложения |
| **Feed Service** | Формирование персональной ленты с кэшированием |
| **PostgreSQL** | Реляционная БД для пользователей, твитов, лайков |
| **Redis** | Кэш ленты (TTL 60 сек), сессии |
| **Kafka** | Асинхронная обработка событий (новые твиты, лайки) |

---

## 🛠 Технологический Стек

### Backend
| Технология | Версия | Назначение |
|------------|--------|------------|
| **Python** | 3.13 | Основной язык |
| **FastAPI** | ≥0.115 | Асинхронный веб-фреймворк |
| **SQLAlchemy 2.0** | ≥2.0 | ORM с async поддержкой |
| **Alembic** | ≥1.13 | Миграции БД |
| **Pydantic** | ≥2.9 | Валидация и сериализация |
| **asyncpg** | ≥0.30 | Асинхронный драйвер PostgreSQL |
| **FastStream** | ≥0.5 | Интеграция с Kafka |
| **Redis** | ≥5.2 | Кэширование |
| **Structlog** | ≥25.0 | Структурированное логирование |
| **Prometheus Instrumentator** | ≥7.1 | Экспорт метрик |

### DevOps & Infrastructure
| Технология | Назначение |
|------------|------------|
| **Docker** | Контейнеризация (multi-stage builds) |
| **Kubernetes** | Оркестрация (Deployments, Services, HPA) |
| **Helm** | Пакетный менеджер K8s |
| **Nginx Ingress** | Маршрутизация внешнего трафика |
| **Prometheus** | Сбор и хранение метрик |
| **Grafana** | Визуализация и дашборды |
| **Locust** | Нагрузочное тестирование |

### Качество кода и безопасность
| Инструмент | Назначение |
|------------|------------|
| **Ruff** | Линтер и форматтер (замена flake8 + black) |
| **MyPy** | Статическая проверка типов |
| **Pytest** | Фреймворк для тестирования |
| **Bandit** | Поиск уязвимостей в коде |
| **Safety** | Проверка зависимостей на CVE |

---

## 🔌 API Endpoints

### Аутентификация
Все запросы требуют заголовок `api-key` в заголовке:
```
api-key: test
```

### Users Service
| Метод | Endpoint | Описание |
|-------|----------|----------|
| `GET` | `/api/users/me` | Получить текущий профиль |
| `GET` | `/api/users/{user_id}` | Получить профиль пользователя |
| `POST` | `/api/users/{user_id}/follow` | Подписаться на пользователя |
| `DELETE` | `/api/users/{user_id}/follow` | Отписаться от пользователя |

### Tweets Service
| Метод | Endpoint | Описание |
|-------|----------|----------|
| `GET` | `/api/tweets` | Получить ленту твитов (с кэшированием) |
| `POST` | `/api/tweets` | Создать твит |
| `DELETE` | `/api/tweets/{tweet_id}` | Удалить твит |
| `POST` | `/api/tweets/{tweet_id}/likes` | Лайкнуть твит |
| `DELETE` | `/api/tweets/{tweet_id}/likes` | Убрать лайк |
| `POST` | `/api/medias` | Загрузить медиа (изображение) |

### Swagger UI
Полная интерактивная документация доступна по адресу:
```
http://localhost:8000/api/docs
```

---

## 💻 Предварительные Требования

### Минимальные требования
| Компонент | Требование |
|-----------|------------|
| **ОС** | Windows 10/11, macOS, Linux |
| **RAM** | Минимум 4 ГБ (8 ГБ рекомендуется) |
| **Диск** | 10 ГБ свободного места |
| **CPU** | 2+ ядра |

### Необходимое ПО

#### 1. Docker Desktop
1. Скачайте с [docker.com/products/docker-desktop](https://www.docker.com/products/docker-desktop)
2. Установите и запустите
3. Убедитесь, что Docker работает:
   ```bash
   docker --version
   docker ps
   ```

#### 2. Kubernetes (встроен в Docker Desktop)
1. Откройте **Docker Desktop Settings** (шестеренка в трее)
2. Перейдите в раздел **Kubernetes**
3. Поставьте галочку **Enable Kubernetes**
4. Нажмите **Apply & Restart**
5. Дождитесь зелёного индикатора `Kubernetes is running`
6. Проверйте:
   ```bash
   kubectl cluster-info
   kubectl get nodes
   ```

#### 3. Helm (пакетный менеджер для K8s)
**Windows (PowerShell от администратора):**
```powershell
winget install Helm.Helm
```

**macOS:**
```bash
brew install helm
```

**Linux:**
```bash
curl https://raw.githubusercontent.com/helm/helm/main/scripts/get-helm-3 | bash
```

Проверьте установку:
```bash
helm version
```

#### 4. kubectl (если не установлен с Docker Desktop)
**Windows:**
```powershell
winget install Kubernetes.kubectl
```

---

## 🚀 Быстрый Старт (Docker Compose)

Идеально для локальной разработки и быстрого тестирования.

### Шаг 1: Клонирование репозитория
```bash
git clone <URL_ВАШЕГО_РЕПОЗИТОРИЯ>
cd twitter-clone-2026
```

### Шаг 2: Настройка переменных окружения
```bash
# Скопируйте пример .env файла
cp .env.example .env

# При необходимости отредактируйте
# .env
```

Содержимое `.env`:
```env
# Database
POSTGRES_DB=twitter_clone_db
POSTGRES_USER=skillbox
POSTGRES_PASSWORD=skillbox_password
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

# Security
SECRET_KEY=super_secret_key_change_me_in_production
```

### Шаг 3: Запуск всех сервисов
```bash
# Сборка и запуск
docker-compose -f deploy/docker-compose.yml up --build -d

# Проверка статуса
docker-compose -f deploy/docker-compose.yml ps
```

### Шаг 4: Инициализация базы данных
```bash
# Запуск миграций
docker-compose -f deploy/docker-compose.yml exec app alembic upgrade head

# Заполнение тестовыми данными
docker-compose -f deploy/docker-compose.yml exec app python scripts/seed_db.py
```

### Шаг 5: Проверка работы
```bash
# Swagger UI
# Откройте: http://localhost:8000/api/docs

# Проверка API через curl
curl -H "api-key: test" http://localhost:8000/api/tweets

# Kafdrop (UI для Kafka)
# Откройте: http://localhost:9000
```

### Шаг 6: Остановка
```bash
docker-compose -f deploy/docker-compose.yml down
# С удалением volumes (очистка данных):
docker-compose -f deploy/docker-compose.yml down -v
```

---

## 🏗 Production Развертывание (Kubernetes)

### Шаг 1: Сборка Docker-образов
```bash
# Backend
docker build -t twitter-clone-2026:latest .

# Frontend
docker build -f Dockerfile.frontend -t twitter-clone-frontend:latest .
```

### Шаг 2: Создание Namespace и конфигурации
```bash
# Создание namespace
kubectl apply -f deploy/k8s/00-namespace.yaml

# ConfigMap и Secrets
kubectl apply -f deploy/k8s/01-configmap.yaml
kubectl apply -f deploy/k8s/02-secrets.yaml
```

### Шаг 3: Развертывание инфраструктуры
```bash
# PostgreSQL
kubectl apply -f deploy/k8s/03-postgres.yaml

# Redis
kubectl apply -f deploy/k8s/04-redis.yaml

# Kafka
kubectl apply -f deploy/k8s/05-kafka.yaml

# Проверка
kubectl get pods -n twitter-clone
```

### Шаг 4: Инициализация БД
```bash
# Создание суперпользователя для Alembic
kubectl exec -it deploy/postgres -n twitter-clone -- \
  psql -U skillbox -d twitter_clone_db \
  -c "CREATE USER postgres WITH SUPERUSER PASSWORD 'skillbox_password';"

# Запуск миграций
kubectl exec -it deploy/backend -n twitter-clone -- alembic upgrade head

# Заполнение тестовыми данными
kubectl exec -it deploy/backend -n twitter-clone -- python scripts/seed_db.py
```

### Шаг 5: Развертывание приложения
```bash
# PVC для медиа
kubectl apply -f deploy/k8s/10-media-pvc.yaml

# Backend
kubectl apply -f deploy/k8s/07-backend.yaml

# Frontend
kubectl apply -f deploy/k8s/09-frontend.yaml

# Ingress
kubectl apply -f deploy/k8s/11-ingress.yaml
```

### Шаг 6: Установка Ingress Controller
```bash
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update
helm install ingress-nginx ingress-nginx/ingress-nginx \
  -n twitter-clone --create-namespace \
  --set controller.service.type=LoadBalancer
```

### Шаг 7: Проверка
```bash
# Все поды должны быть Running
kubectl get pods -n twitter-clone

# Проброс порта для тестирования
kubectl port-forward svc/backend-service -n twitter-clone 8000:8000

# Откройте Swagger UI
# http://localhost:8000/api/docs
```

---

## 📊 Мониторинг и Наблюдаемость

### Установка Prometheus + Grafana
```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

helm install prometheus prometheus-community/kube-prometheus-stack \
  -n twitter-clone \
  --set prometheus-node-exporter.enabled=false

# ServiceMonitor для сбора метрик с Backend
kubectl apply -f deploy/k8s/12-service-monitor.yaml
```

### Доступ к Grafana
```bash
# Проброс порта
kubectl port-forward svc/prometheus-grafana -n twitter-clone 3000:80
```

Откройте [http://localhost:3000](http://localhost:3000):
- **Логин:** `admin`
- **Пароль:** `prom-operator`

### Доступ к Prometheus
```bash
kubectl port-forward svc/prometheus-kube-prometheus-prometheus -n twitter-clone 9090:9090
```

Откройте [http://localhost:9090](http://localhost:9090)

### Полезные запросы в Prometheus
```promql
# Количество запросов в секунду
rate(http_request_duration_seconds_count{namespace="twitter-clone"}[5m])

# Среднее время ответа
rate(http_request_duration_seconds_sum{namespace="twitter-clone"}[5m]) / 
rate(http_request_duration_seconds_count{namespace="twitter-clone"}[5m])

# Количество ошибок 5xx
rate(http_requests_total{status=~"5..", namespace="twitter-clone"}[5m])
```

---

## 🏃 Нагрузочное Тестирование

### Установка Locust
```bash
pip install locust
```

### Запуск веб-интерфейса
```bash
locust -f locustfile.py --host=http://localhost:8000
```

Откройте [http://localhost:8089](http://localhost:8089):
- **Users:** 100
- **Spawn rate:** 10

### Сценарии тестирования
| Сценарий | Вес | Описание |
|----------|-----|----------|
| Просмотр ленты | 3 | GET /api/tweets (самый частый) |
| Создание твита | 1 | POST /api/tweets |
| Просмотр профиля | 2 | GET /api/users/me |

### Быстрый тест через curl
```bash
# Генерация нагрузки для проверки метрик
while true; do 
  curl -s http://localhost:8000/api/tweets -H "api-key: test" > /dev/null
  sleep 0.1
done
```

---

## 🛡 Безопасность

### Реализованные практики

| Практика | Описание |
|----------|----------|
| **Non-root контейнеры** | Backend запускается от `appuser` (UID 1000) |
| **Kubernetes Secrets** | Пароли хранятся в зашифрованных Secrets |
| **SecurityContext** | `allowPrivilegeEscalation: false` |
| **Resource Limits** | Ограничения CPU и памяти для каждого пода |
| **Init Containers** | Проверка готовности инфраструктуры перед запуском |
| **API Key аутентификация** | Простая, но эффективная для демо |

### Пример SecurityContext
```yaml
securityContext:
  runAsUser: 1000
  fsGroup: 1000
  allowPrivilegeEscalation: false
```

### Проверка зависимостей на уязвимости
```bash
# Bandit — поиск уязвимостей в коде
bandit -r . -ll

# Safety — проверка зависимостей
safety check
```

---

## 🔧 CI/CD и Качество Кода

### Линтинг и форматирование
```bash
# Ruff — проверка
ruff check .

# Ruff — автоисправление
ruff check . --fix

# Ruff — форматирование
ruff format .
```

### Проверка типов
```bash
mypy .
```

### Тесты
```bash
# Запуск всех тестов
pytest

# С покрытием
pytest --cov=. --cov-report=html

# Асинхронные тесты
pytest -v
```

### Структура тестов
```
tests/
├── conftest.py      # Фикстуры и конфигурация
└── test_api.py      # Интеграционные тесты API
```

---

## 🔧 Устранение Неполадок

### 1. Backend в `CrashLoopBackOff`
**Причина:** Нет соединения с БД или не пройдены миграции.

**Решение:**
```bash
# Проверка логов
kubectl logs deploy/backend -n twitter-clone

# Проверка статуса Postgres
kubectl get pods -n twitter-clone | grep postgres

# Создание пользователя postgres
kubectl exec -it deploy/postgres -n twitter-clone -- \
  psql -U skillbox -d twitter_clone_db \
  -c "CREATE USER postgres WITH SUPERUSER PASSWORD 'skillbox_password';"
```

### 2. Frontend возвращает `502 Bad Gateway`
**Причина:** Nginx не может подключиться к Backend.

**Решение:**
```bash
# Проверка nginx.conf
# API должен проксироваться на http://backend-service:8000

# Проверка сервиса
kubectl get svc -n twitter-clone
```

### 3. Prometheus не видит метрики
**Причина:** Отсутствует ServiceMonitor или неправильные лейблы.

**Решение:**
```bash
# Проверка ServiceMonitor
kubectl get servicemonitor -n twitter-clone

# Проверка лейблов сервиса
kubectl get svc backend-service -n twitter-clone -o yaml
```

### 4. Ошибка `ImagePullBackOff`
**Причина:** Kubernetes не нашёл образ локально.

**Решение:**
```bash
# Пересборка образов
docker build -t twitter-clone-2026:latest .
docker build -f Dockerfile.frontend -t twitter-clone-frontend:latest .

# Проверка imagePullPolicy в манифестах
# Должно быть: imagePullPolicy: IfNotPresent
```

### 5. Grafana падает после установки
**Причина:** Конфликт DataSource.

**Решение:**
```bash
kubectl delete configmap loki-loki-stack -n twitter-clone
kubectl rollout restart deployment/prometheus-grafana -n twitter-clone
```

### 6. Очистка всего и перезапуск
```bash
# Удаление namespace
kubectl delete namespace twitter-clone

# Удаление Helm релизов
helm uninstall prometheus -n twitter-clone
helm uninstall ingress-nginx -n twitter-clone

# Остановка Docker Compose
docker-compose -f deploy/docker-compose.yml down -v
```

---

## 📁 Структура Проекта

```
twitter-clone-2026/
├── deploy/
│   ├── docker-compose.yml          # Локальный запуск
│   ├── docker-compose.prod.yml     # Production конфигурация
│   └── k8s/                        # Kubernetes манифесты
│       ├── 00-namespace.yaml       # Namespace
│       ├── 01-configmap.yaml       # ConfigMap
│       ├── 02-secrets.yaml         # Secrets
│       ├── 03-postgres.yaml        # PostgreSQL Deployment
│       ├── 04-redis.yaml           # Redis Deployment
│       ├── 05-kafka.yaml           # Kafka Deployment
│       ├── 07-backend.yaml         # Backend + HPA
│       ├── 09-frontend.yaml        # Frontend Deployment
│       ├── 10-media-pvc.yaml       # PVC для медиа
│       ├── 11-ingress.yaml         # Ingress правила
│       └── 12-service-monitor.yaml # Prometheus ServiceMonitor
├── services/
│   ├── gateway/                    # API Gateway сервис
│   ├── tweets/                     # Сервис твитов
│   │   ├── app/
│   │   │   ├── api/routes.py       # API endpoints
│   │   │   ├── crud.py             # Бизнес-логика
│   │   │   ├── models.py           # SQLAlchemy модели
│   │   │   └── schemas.py          # Pydantic схемы
│   │   └── Dockerfile
│   ├── users/                      # Сервис пользователей
│   │   ├── app/
│   │   │   ├── api/routes.py       # API endpoints
│   │   │   ├── crud.py             # Бизнес-логика
│   │   │   ├── models.py           # SQLAlchemy модели
│   │   │   └── schemas.py          # Pydantic схемы
│   │   └── Dockerfile
│   └── feed/                       # Сервис ленты
├── libs/                           # Общие модули
│   ├── config.py                   # Конфигурация
│   ├── database.py                 # Подключение к БД
│   ├── redis_client.py             # Redis клиент
│   ├── kafka_conf.py               # Kafka конфигурация
│   ├── logging_config.py           # Настройка логирования
│   └── schemas.py                  # Общие схемы
├── migrations/                     # Alembic миграции
├── scripts/
│   └── seed_db.py                  # Скрипт заполнения БД
├── frontend/                       # Собранный frontend
├── tests/                          # Тесты
│   ├── conftest.py
│   └── test_api.py
├── Dockerfile                      # Backend образ
├── Dockerfile.frontend             # Frontend образ
├── pyproject.toml                  # Зависимости и настройки
├── locustfile.py                   # Нагрузочные тесты
├── .env.example                    # Пример переменных окружения
├── nginx.conf                      # Nginx конфигурация
└── start.sh                        # Скрипт запуска
```

---

## 👔 Для Работодателей

### Что демонстрирует этот проект

| Компетенция | Подтверждение |
|-------------|---------------|
| **Python (Advanced)** | Асинхронность, типизация, паттерны проектирования |
| **FastAPI** | REST API, middleware, dependency injection |
| **SQLAlchemy 2.0** | Async ORM, relationships, migrations |
| **Docker** | Multi-stage builds, non-root containers |
| **Kubernetes** | Deployments, Services, HPA, InitContainers, PVC |
| **Helm** | Установка Prometheus, Ingress |
| **Message Brokers** | Kafka + FastStream |
| **Caching** | Redis с TTL |
| **Monitoring** | Prometheus + Grafana + ServiceMonitor |
| **Load Testing** | Locust сценарии |
| **Security** | SecurityContext, Secrets, non-root |
| **CI/CD Ready** | GitLab CI конфигурация |
| **Code Quality** | Ruff, MyPy, Pytest, Bandit |

### Как проверить проект с нуля

#### 1. Минимальная проверка (5 минут)
```bash
# Клонировать репозиторий
git clone <URL>
cd twitter-clone-2026

# Запустить Docker Compose
docker-compose -f deploy/docker-compose.yml up --build -d

# Открыть Swagger UI
# http://localhost:8000/api/docs
```

#### 2. Полная проверка API (10 минут)
```bash
# 1. Проброс порта (если в K8s)
kubectl port-forward svc/backend-service -n twitter-clone 8000:8000

# 2. Получить ленту
curl -H "api-key: test" http://localhost:8000/api/tweets

# 3. Создать твит
curl -X POST http://localhost:8000/api/tweets \
  -H "api-key: test" \
  -H "Content-Type: application/json" \
  -d '{"tweet_data": "Hello from API!", "tweet_media_ids": []}'

# 4. Получить профиль
curl -H "api-key: test" http://localhost:8000/api/users/me

# 5. Подписаться на пользователя
curl -X POST http://localhost:8000/api/users/1/follow \
  -H "api-key: test"
```

#### 3. Проверка мониторинга (15 минут)
```bash
# Установить Prometheus + Grafana
helm install prometheus prometheus-community/kube-prometheus-stack \
  -n twitter-clone --set prometheus-node-exporter.enabled=false

# Проброс порта Grafana
kubectl port-forward svc/prometheus-grafana -n twitter-clone 3000:80

# Открыть http://localhost:3000
# Логин: admin, Пароль: prom-operator
```

#### 4. Нагрузочное тестирование (10 минут)
```bash
pip install locust
locust -f locustfile.py --host=http://localhost:8000
# Открыть http://localhost:8089
```

### Ключевые файлы для ревью

| Файл | Что показывает |
|------|----------------|
| [`Dockerfile`](Dockerfile:1) | Multi-stage build, security best practices |
| [`deploy/k8s/07-backend.yaml`](deploy/k8s/07-backend.yaml:1) | K8s Deployment, HPA, Probes, SecurityContext |
| [`services/tweets/app/api/routes.py`](services/tweets/app/api/routes.py:1) | FastAPI async endpoints, caching |
| [`libs/database.py`](libs/database.py:1) | Async SQLAlchemy setup |
| [`pyproject.toml`](pyproject.toml:1) | Modern Python packaging, dev dependencies |
| [`locustfile.py`](locustfile.py:1) | Load testing scenarios |

---

## 📝 Лицензия

MIT License — см. [LICENSE](LICENSE) для подробностей.

---

## 📞 Контакты

**Автор:** Valera  
**Курс:** Python Advanced — Skillbox  
**Год:** 2026

---

> ⭐ Если проект был полезен — поставьте звезду на репозитории!
