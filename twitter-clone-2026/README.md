# Twitter Clone 2026

Полнофункциональный клон Twitter с микросервисной архитектурой, развернутый в Kubernetes. Проект демонстрирует современные практики DevOps: контейнеризацию, оркестрацию, мониторинг, безопасность и CI/CD готовность.

---

## 📖 Содержание
- [Архитектура](#-архитектура)
- [Технологии и Библиотеки](#-технологии-и-библиотеки)
- [Предварительные требования](#-предварительные-требования)
- [Установка Окружения](#-установка-окружения-docker--kubernetes--helm)
- [Запуск проекта](#-запуск-проекта)
  - [Вариант А: Локально через Docker Compose](#вариант-а-локально-через-docker-compose)
  - [Вариант Б: В Kubernetes (Production-like)](#вариант-б-в-kubernetes-production-like)
- [Мониторинг (Prometheus + Grafana)](#-мониторинг-prometheus--grafana)
- [Проверка работоспособности](#-проверка-работоспособности)
- [Нагрузочное тестирование](#-нагрузочное-тестирование)
- [Безопасность](#-безопасность)
- [Устранение неполадок (Troubleshooting)](#-устранение-неполадок-troubleshooting)

---

## 🏗 Архитектура

Проект построен на микросервисной архитектуре:

*   **API Gateway / Backend:** Основное FastAPI приложение, обрабатывающее REST запросы.
*   **Frontend:** React приложение, раздается через Nginx.
*   **Database:** PostgreSQL (хранение пользователей, твитов).
*   **Cache:** Redis (кэширование ленты).
*   **Queue:** Apache Kafka (асинхронная обработка событий).
*   **Monitoring:** Prometheus (метрики), Grafana (визуализация), Loki (логи).

**Структура репозитория:**
```
├── deploy/k8s/          # Манифесты Kubernetes
├── services/
│   ├── frontend/        # React + Nginx
│   └── tweets/          # FastAPI Backend
├── libs/                # Общие модули (config, database, redis)
├── scripts/             # Скрипты инициализации БД
├── Dockerfile           # Сборка Backend
├── Dockerfile.frontend  # Сборка Frontend
└── docker-compose.yml   # Локальный запуск
```

---

## 🛠 Технологии и Библиотеки

**Backend:**
*   **Python 3.13**
*   **FastAPI** — асинхронный веб-фреймворк.
*   **SQLAlchemy 2.0** — ORM с поддержкой `async`.
*   **Alembic** — миграции базы данных.
*   **Aiokafka** — асинхронный продюсер/консьюмер для Kafka.
*   **Pydantic** — валидация данных.
*   **Prometheus FastAPI Instrumentator** — экспорт метрик.

**Frontend:**
*   **React** — клиентская часть.
*   **Nginx** — раздача статики и проксирование API.

**Infrastructure:**
*   **Docker & Kubernetes** — контейнеризация и оркестрация.
*   **Helm** — пакетный менеджер для Kubernetes.
*   **PostgreSQL**, **Redis**, **Kafka**.

---

## 💻 Предварительные требования

1.  **OS:** Windows 10/11 (или macOS/Linux).
2.  **Docker Desktop:** Последняя версия.
3.  **Git:** Система контроля версий.

---

## ⚙️ Установка Окружения (Docker + Kubernetes + Helm)

### 1. Docker Desktop
1.  Скачайте и установите [Docker Desktop](https://www.docker.com/products/docker-desktop).
2.  Запустите приложение.

### 2. Включение Kubernetes
1.  Откройте настройки Docker Desktop (значок шестеренки).
2.  Перейдите в раздел **Kubernetes**.
3.  Поставьте галочку **Enable Kubernetes**.
4.  Нажмите **Apply & Restart**.
5.  Дождитесь появления зеленой надписи `Kubernetes is running` внизу окна.

### 3. Установка Helm (Windows)
Откройте **PowerShell от имени Администратора** и выполните:
```powershell
winget install Helm.Helm
```
*После установки перезапустите терминал, чтобы команда `helm` стала доступна.*

---

## 🚀 Запуск проекта

### Вариант А: Локально через Docker Compose
Для быстрой проверки без Kubernetes.

```bash
# 1. Сборка и запуск
docker-compose up --build -d

# 2. Проверка
docker-compose ps
```
API будет доступен на `http://localhost:8000/api/docs`.

---

### Вариант Б: В Kubernetes (Production-like)
Полноценное развертывание в кластере.

#### Шаг 1: Сборка Docker-образов
Образы должны быть собраны локально, чтобы Kubernetes мог их использовать.

```bash
# Сборка Backend
docker build -t twitter-clone-2026:latest .

# Сборка Frontend (из корня проекта!)
docker build -f Dockerfile.frontend -t twitter-clone-frontend:latest .
```

#### Шаг 2: Установка Ingress Controller
```bash
helm repo add ingress-nginx https://kubernetes.github.io/ingress-nginx
helm repo update
helm install ingress-nginx ingress-nginx/ingress-nginx -n twitter-clone --create-namespace --set controller.service.type=LoadBalancer
```

#### Шаг 3: Развертывание Базы Данных и Сервисов
```bash
# Конфигурация
kubectl apply -f deploy/k8s/00-namespace.yaml
kubectl apply -f deploy/k8s/01-configmap.yaml
kubectl apply -f deploy/k8s/02-secrets.yaml

# Инфраструктура (Postgres, Redis, Kafka)
kubectl apply -f deploy/k8s/03-postgres.yaml
kubectl apply -f deploy/k8s/04-redis.yaml
kubectl apply -f deploy/k8s/05-kafka.yaml
```

#### Шаг 4: Инициализация Базы Данных
Ждем ~1 минуту, пока Postgres перейдет в статус `Running`.

```bash
# Создаем роль postgres (для Alembic)
kubectl exec -it deploy/postgres -n twitter-clone -- psql -U skillbox -d twitter_clone_db -c "CREATE USER postgres WITH SUPERUSER PASSWORD 'skillbox_password';"

# Генерируем тестовые данные (пользователь Valera, api-key: test)
kubectl exec -it deploy/backend -n twitter-clone -- python scripts/seed_db.py
```

#### Шаг 5: Запуск Приложения
```bash
kubectl apply -f deploy/k8s/10-media-pvc.yaml
kubectl apply -f deploy/k8s/07-backend.yaml
kubectl apply -f deploy/k8s/09-frontend.yaml
kubectl apply -f deploy/k8s/11-ingress.yaml
```

#### Шаг 6: Установка Мониторинга (Prometheus + Grafana)
```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo add grafana https://grafana.github.io/helm-charts
helm repo update

helm install prometheus prometheus-community/kube-prometheus-stack -n twitter-clone --set prometheus-node-exporter.enabled=false

# ServiceMonitor для сбора метрик с Backend
kubectl apply -f deploy/k8s/12-service-monitor.yaml
```

---

## 📊 Мониторинг (Prometheus + Grafana)

### Доступ к Grafana
1.  Проброс порта:
    ```bash
    kubectl port-forward svc/prometheus-grafana -n twitter-clone 3000:80
    ```
2.  Открыть в браузере: [http://localhost:3000](http://localhost:3000)
3.  **Логин:** `admin`
4.  **Пароль:** `prom-operator`

### Настройка Dashboard
В Grafana создайте новый Dashboard и используйте запрос:
```
http_request_duration_seconds_count{namespace="twitter-clone"}
```

---

## ✅ Проверка работоспособности

### 1. Проверка Статуса Подов
Все поды должны быть в статусе `Running`.
```bash
kubectl get pods -n twitter-clone
```
Ожидаемый вывод:
```
NAME                       READY   STATUS    RESTARTS   AGE
backend-xxx                 1/1     Running   0          5m
postgres-xxx                1/1     Running   0          6m
frontend-xxx                1/1     Running   0          5m
```

### 2. Проверка Backend (API)
```bash
# Проброс порта (в отдельном окне)
kubectl port-forward svc/backend-service -n twitter-clone 8000:8000
```
Откройте Swagger UI: [http://localhost:8000/api/docs](http://localhost:8000/api/docs).
Авторизация: **API Key** `test`.

### 3. Проверка Frontend
Откройте [http://localhost](http://localhost) (или `twitter.local`, если прописали hosts).
Вы должны увидеть ленту твитов.
*   **Логин:** Valera
*   **API Key:** test

---

## 🚄 Нагрузочное тестирование

В проекте используется библиотека **Locust** (см. `locustfile.py`).

### Запуск тестов
1.  Установите Locust: `pip install locust`.
2.  Запустите (при запущенном API):
    ```bash
    locust -f locustfile.py
    ```
3.  Откройте веб-интерфейс Locust ([http://localhost:8089](http://localhost:8089)) и задайте количество пользователей.

### Простой тест (через Curl)
Для проверки метрик в Grafana:
```bash
while true; do curl -s http://localhost:8000/api/tweets -H "api-key: test" > /dev/null; sleep 0.1; done
```

---

## 🛡 Безопасность

В проекте реализованы практики безопасного развертывания:

1.  **Non-root пользователи:** Backend запускается от пользователя `appuser` (UID 1000), а не от `root`.
    ```yaml
    # deploy/k8s/07-backend.yaml
    securityContext:
      runAsUser: 1000
      fsGroup: 1000
    ```
2.  **Secrets:** Пароли и ключи хранятся в Kubernetes Secrets, а не в открытом виде в коде.
    ```bash
    kubectl get secrets -n twitter-clone
    ```
3.  **Read-only Filesystem (Опционально):** Можно включить для предотвращения изменений бинарников контейнера во время выполнения.

---

## 🔧 Устранение неполадок (Troubleshooting)

### 1. Ошибка `CrashLoopBackOff` у Backend
**Причина:** Нет соединения с БД или не пройдены миграции.
**Решение:**
*   Проверьте логи: `kubectl logs deploy/backend -n twitter-clone`.
*   Убедитесь, что Postgres запущен.
*   Проверьте, что пользователь `postgres` создан (см. Шаг 4 установки).

### 2. Frontend возвращает `502 Bad Gateway`
**Причина:** Nginx не может подключиться к Backend или порты не совпадают.
**Решение:**
*   Проверьте `nginx.conf`: API должен проксироваться на `http://backend-service:8000`.
*   Проверьте `targetPort` в сервиссе Frontend (обычно 80 для Nginx).

### 3. Grafana падает после установки
**Причина:** Конфликт DataSource (Prometheus и Loki оба "Default").
**Решение:**
```bash
kubectl delete configmap loki-loki-stack -n twitter-clone
kubectl rollout restart deployment/prometheus-grafana -n twitter-clone
```

### 4. Prometheus не видит метрики (Target Down)
**Причина:** Отсутствует `ServiceMonitor` или лейблы.
**Решение:**
Убедитесь, что у сервиса Backend есть лейбл `app: backend`, а в `ServiceMonitor` правильный селектор.

### 5. Ошибка `ImagePullBackOff`
**Причина:** Kubernetes не нашел образ локально.
**Решение:** Пересоберите образы (`docker build...`) и убедитесь, что используете `imagePullPolicy: IfNotPresent` в манифестах.
```

### Команды для отправки в Git

```bash
git add README.md
git commit -m "Docs: Finalize comprehensive README with installation, security and troubleshooting sections"
git push origin master
```