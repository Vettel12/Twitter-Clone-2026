# 🏗 Архитектура — Схемы и принципы работы

> Как устроен Twitter Clone 2026 изнутри.

---

## 📐 Общая схема системы

```
                          ┌─────────────────────────────────────┐
                          │          КЛИЕНТЫ                     │
                          │  Browser / curl / Postman / Vue.js   │
                          └──────────────┬──────────────────────┘
                                         │ HTTP (api-key header)
                                         ▼
                    ┌────────────────────────────────────────────┐
                    │         ТОЧКА ВХОДА                        │
                    │                                            │
                    │  Docker Compose:  localhost:8000           │
                    │  Kubernetes:      Ingress Controller       │
                    │  Local dev:       uvicorn :8000            │
                    └──────────────┬─────────────────────────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              ▼                    ▼                    ▼
    ┌──────────────┐    ┌──────────────┐    ┌──────────────┐
    │  FastAPI     │    │  FastAPI     │    │  FastAPI     │
    │  Pod 1       │    │  Pod 2       │    │  Pod N       │
    │  :8000       │    │  :8000       │    │  :8000       │
    └──────┬───────┘    └──────┬───────┘    └──────┬───────┘
           │                   │                   │
           └─────────┬─────────┴─────────┬─────────┘
                     │                   │
           ┌─────────▼─────────┐ ┌───────▼───────┐ ┌─────▼─────┐
           │   PostgreSQL      │ │    Redis      │ │   Kafka   │
           │   :5432           │ │    :6379      │ │  :29092   │
           │   Данные          │ │    Кэш        │ │  События  │
           └───────────────────┘ └───────────────┘ └───────────┘
```

---

## 🔄 Жизненный цикл запроса

### Сценарий 1: Создание твита

```
Client                          FastAPI                        PostgreSQL        Redis           Kafka
  │                               │                               │                │               │
  │── POST /api/tweets ──────────▶│                                │                │               │
  │   api-key: abc123             │                                │                │               │
  │                               │── 1. Проверка api-key ────────▶│                │               │
  │                               │   (hash(api_key) == hash_db)  │                │               │
  │                               │◀── User найден ───────────────│                │               │
  │                               │                                │                │               │
  │                               │── 2. INSERT INTO tweets ──────▶│                │               │
  │                               │                                │◀── committed ──│               │
  │                               │                                │                │               │
  │                               │── 3. SELECT follower_id ──────▶│                │               │
  │                               │   FROM followers               │                │               │
  │                               │◀── [1, 5, 12] ────────────────│                │               │
  │                               │                                │                │               │
  │                               │── 4. DELETE feed:{author} ──────────────────────▶│               │
  │                               │   DELETE feed:{1,5,12}        │                │               │
  │                               │                                │                │               │
  │                               │── 5. Publish event ─────────────────────────────────────────────▶│
  │                               │   topic: tweets-topic          │                │               │
  │                               │   {tweet_id: 42, author_id: 3} │                │               │
  │                               │                                │                │               │
  │◀── {tweet_id: 42} ───────────│                                │                │               │
  │                               │                                │                │               │
  │                               │                                │                │    ┌──────────▼
  │                               │                                │                │    │Feed Service
  │                               │                                │                │    │(Kafka consumer)
  │                               │                                │                │    │
  │                               │                                │                │    │── Проверка dedup
  │                               │                                │                │    │── invalidate feed:{author}
  │                               │                                │                │    │── Mark processed
  │                               │                                │                │    └──────────┘
```

### Сценарий 2: Получение ленты с кэшированием

```
Client                          FastAPI                        PostgreSQL        Redis
  │                               │                               │                │
  │── GET /api/tweets ──────────▶│                                │                │
  │   api-key: abc123             │                                │                │
  │                               │                                │                │
  │                               │── 1. GET feed:{user_id} ─────────────────────▶│
  │                               │                                │                │
  │            ┌─── CACHE HIT ────┤                                │                │
  │            │                  │◀── JSON данные ────────────────│                │
  │            │                  │                                │                │
  │            │                  │── 2. Вернуть кэш ─────────────▶│                │
  │            ▼                  │                                │                │
  │◀── {tweets: [...]} ──────────│                                │                │
  │                               │                                │                │
  │            ┌─── CACHE MISS ───┤                                │                │
  │            │                  │── 2. SELECT tweets ───────────▶│                │
  │            │                  │   JOIN followers               │                │
  │            │                  │   ORDER BY created_at DESC     │                │
  │            │                  │   LIMIT 100                    │                │
  │            │                  │◀── [Tweet, Tweet, ...] ────────│                │
  │            │                  │                                │                │
  │            │                  │── 3. SET feed:{user_id} ──────────────────────▶│
  │            │                  │   ex=60 (TTL)                  │                │
  │            │                  │                                │                │
  │            │                  │── 4. Вернуть данные ──────────▶│                │
  │            ▼                  │                                │                │
  │◀── {tweets: [...]} ──────────│                                │                │
  │                               │                                │                │
  │            ┌─── REDIS DOWN ──▶│                                │                │
  │            │                  │── 2. Exception caught ─────────│                │
  │            │                  │── 3. SELECT tweets ───────────▶│                │
  │            │                  │   (fallback на БД)             │                │
  │            ▼                  │                                │                │
  │◀── {tweets: [...]} ──────────│                                │                │
  │                               │                                │                │
```

### Сценарий 3: Лайк твита

```
Client                          FastAPI                        PostgreSQL        Redis
  │                               │                               │                │
  │── POST /tweets/{id}/likes ──▶│                                │                │
  │                               │                                │                │
  │                               │── 1. Проверка existence ──────▶│                │
  │                               │   SELECT FROM tweets WHERE     │                │
  │                               │   id = :tweet_id               │                │
  │                               │                                │                │
  │                               │── 2. Проверка duplicate ──────▶│                │
  │                               │   SELECT FROM likes WHERE      │                │
  │                               │   user_id = :uid AND           │                │
  │                               │   tweet_id = :tid              │                │
  │                               │                                │                │
  │                               │── 3. INSERT INTO likes ───────▶│                │
  │                               │   (user_id, tweet_id)          │                │
  │                               │   ← составной PK защищает ────▶│                │
  │                               │                                │                │
  │                               │── 4. DELETE feed:{liker} ─────────────────────▶│
  │                               │   DELETE feed:{author} ──────────────────────▶│
  │                               │                                │                │
  │                               │── 5. SELECT tweet (с likes) ─▶│                │
  │                               │   populate_existing=True       │                │
  │                               │                                │                │
  │◀── {result: true, tweet: ..}─│                                │                │
```

---

## 🗄 База данных — ER-схема

```
┌──────────────────┐          ┌──────────────────┐
│     users        │          │    followers     │
├──────────────────┤          ├──────────────────┤
│ 🔑 id (PK)       │◄──┐  ┌──│ 🔑 follower_id   │
│    name (50)     │   │  │   │    (FK→users)    │
│    api_key_hash  │   │  │   │ 🔑 followed_id   │
│    (64, UQ)      │   │  │   │    (FK→users)    │
└────────┬─────────┘   │  │   └──────────────────┘
         │             │  │
         │             └──┼── Many-to-Many ────────────────────┐
         │                │                                     │
         ▼                ▼                                     │
┌──────────────────┐          ┌──────────────────┐              │
│     tweets       │          │      likes       │              │
├──────────────────┤          ├──────────────────┤              │
│ 🔑 id (PK)       │◄──┐  ┌──│ 🔑 user_id       │              │
│    content (Text)│   │  │   │    (FK→users)    │              │
│    author_id     │   │  │   │ 🔑 tweet_id      │              │
│    (FK→users)    │   │  │   │    (FK→tweets)   │              │
│    created_at    │   │  │   │    (composite PK)│              │
│    updated_at    │   │  │   └──────────────────┘              │
└────────┬─────────┘   │  │                                      │
         │             │  │                                      │
         │             └──┼── One-to-Many ───────────────────┐   │
         │                │                                  │   │
         ▼                ▼                                  │   │
┌──────────────────┐                                         │   │
│      media       │                                         │   │
├──────────────────┤         ┌──────────────────────────┐    │   │
│ 🔑 id (PK)       │         │      Relationships       │    │   │
│    file_path     │         ├──────────────────────────┤    │   │
│    tweet_id (FK) │         │ users 1──N tweets        │    │   │
│    (nullable)    │         │ users N──M users (follow)│◄───┘   │
└──────────────────┘         │ tweets 1──N likes        │        │
                             │ users 1──N likes         │        │
                             │ tweets 1──N media        │        │
                             └──────────────────────────┘        │
```

---

## 🧩 Компоненты системы

### 1. FastAPI Gateway (`services/gateway/main.py`)

**Роль:** Точка входа для всех HTTP-запросов. Modular Monolith — единое приложение с роутерами.

**Компоненты:**
```
gateway/main.py
├── lifespan()          — инициализация Kafka, shutdown Redis
├── CORS middleware     — настройка CORS
├── Security headers    — X-Frame-Options, HSTS и т.д.
├── Correlation ID      — сквозной ID для трейсинга
├── Prometheus          — /metrics endpoint
├── Users router        — /api/users/*
├── Tweets router       — /api/tweets/*
├── Static files        — /media/*
└── Healthcheck         — /api/healthcheck
```

### 2. Users Service (`services/users/`)

**Роль:** Управление пользователями и подписками.

| Файл | Назначение |
|------|-----------|
| `models.py` | SQLAlchemy модели: User, Follower |
| `crud.py` | CRUD-операции с SQL и комментариями |
| `schemas.py` | Pydantic схемы для валидации |
| `api/routes.py` | HTTP endpoint'ы |

### 3. Tweets Service (`services/tweets/`)

**Роль:** Твиты, медиафайлы, лайки, кэширование.

| Файл | Назначение |
|------|-----------|
| `models.py` | SQLAlchemy модели: Tweet, Media, Like |
| `crud.py` | CRUD + инвалидация кэша + Kafka publish |
| `schemas.py` | Pydantic схемы |
| `api/routes.py` | HTTP endpoint'ы с cache-aside |

### 4. Feed Service (`services/feed/main.py`)

**Роль:** Kafka-потребитель для асинхронной обработки событий.

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│  Kafka       │────▶│  Consumer    │────▶│  Redis       │
│  tweets-topic │     │  handle_tweet│     │  invalidate  │
└──────────────┘     └──────────────┘     └──────────────┘
                           │
                           ▼
                     ┌──────────────┐
                     │  Dedup check │
                     │  processed_  │
                     │  events set  │
                     └──────────────┘
```

---

## 🔑 Стратегия кэширования

### Cache-Aside (Lazy Loading)

```
Чтение:                    Запись:
┌─────────┐               ┌─────────┐
│  Cache  │               │  Cache  │
│  HIT?   │─── YES ──▶ Return      │
│         │               │         │
│   NO    │               │  DB     │
└────┬────┘               │  write  │
     │                    └────┬────┘
     ▼                         │
┌─────────┐                    │
│   DB    │                    ▼
│  query  │               ┌─────────┐
└────┬────┘               │ DELETE  │
     │                    │ cache   │
     ▼                    └─────────┘
┌─────────┐
│  SET    │
│  cache  │
│  TTL=60 │
└────┬────┘
     │
     ▼
  Return
```

### Ключи Redis

| Паттерн | Пример | TTL | Описание |
|---------|--------|-----|----------|
| `feed:{user_id}` | `feed:42` | 60s | Лента пользователя (JSON) |
| `feed:{user_id}:lock` | `feed:42:lock` | 5s | Lock от thundering herd |
| `feed:{user_id}:version` | `feed:42:version` | 5s | Счётчик версии кэша |
| `processed_events` | Redis Set | 3600s | Deduplication Kafka |

### Метрики Prometheus

| Метрика | Тип | Описание |
|---------|-----|----------|
| `cache_hits_total` | Counter | Попадания в кэш |
| `cache_misses_total` | Counter | Промахи кэша |
| `cache_invalidations_total` | Counter | Операции инвалидации |
| `cache_invalidation_errors_total` | Counter | Ошибки инвалидации |
| `cache_errors_total` | Counter | Все ошибки кэша |
| `cache_lock_acquisitions_total` | Counter | Попытки получения lock |
| `cache_write_duration_seconds` | Histogram | Время записи в кэш |

---

## 🔐 Аутентификация

```
Client                    FastAPI                    PostgreSQL
  │                         │                           │
  │── api-key: abc123 ─────▶│                           │
  │                         │── hash_api_key("abc123")  │
  │                         │   → sha256 hash           │
  │                         │                           │
  │                         │── SELECT * FROM users ───▶│
  │                         │   WHERE api_key_hash =    │
  │                         │   :hash                   │
  │                         │                           │
  │                         │◀── User {id: 1, name: ..} │
  │                         │                           │
  │◀── 200 OK ─────────────│                           │
  │                         │                           │
  │── (нет api-key) ──────▶│                           │
  │◀── 401 Unauthorized ───│                           │
```

---

## 📡 Взаимодействие сервисов

### Docker Compose

```
                    ┌─────────────────────────────────────┐
                    │         Docker Network               │
                    │         (app-network)                │
                    │                                     │
                    │  Service names = DNS names:          │
                    │  • postgres → 172.x.x.2             │
                    │  • redis    → 172.x.x.3             │
                    │  • kafka    → 172.x.x.4             │
                    │  • app      → 172.x.x.5             │
                    └─────────────────────────────────────┘

  app ────────────────▶ postgres:5432    (SQLAlchemy asyncpg)
  app ────────────────▶ redis:6379       (redis.asyncio)
  app ────────────────▶ kafka:29092      (FastStream/aiokafka)
  feed (внутри app) ◀── kafka:29092      (FastStream subscriber)
```

### Kubernetes

```
                    ┌─────────────────────────────────────┐
                    │     Kubernetes Cluster                │
                    │     Namespace: twitter-clone         │
                    │                                     │
                    │  Services (ClusterIP = DNS):         │
                    │  • postgres-service → Pod postgres  │
                    │  • redis-service    → Pod redis     │
                    │  • kafka-service    → Pod kafka     │
                    │  • backend-service  → Pod backend×N │
                    └─────────────────────────────────────┘

  backend Pod ────────▶ postgres-service:5432
  backend Pod ────────▶ redis-service:6379
  backend Pod ────────▶ kafka-service:29092
  Ingress ───────────▶ backend-service:8000
  Prometheus ───────▶ backend-service:8000/metrics
```

---

## 🚀 Развёртывание

| Способ | Команда | Для чего |
|--------|---------|----------|
| **Docker Compose** | `docker-compose up -d` | Локальная разработка |
| **Kubernetes** | `kubectl apply -f deploy/k8s/` | Production |
| **Local dev** | `uvicorn services.gateway.main:app --reload` | Отладка кода |
| **С Frontend** | Docker Compose + Nginx | Полный стек |

Подробные инструкции — в [README.md](README.md).
