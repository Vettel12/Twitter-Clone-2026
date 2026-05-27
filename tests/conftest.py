# ==============================================================================
# conftest.py — Глобальные фикстуры pytest для асинхронного тестирования
# ==============================================================================

# ------------------------------------------------------------------------------
# 1. ИМПОРТЫ: ГРУППА 1 — Стандартная библиотека и сторонние пакеты
# ------------------------------------------------------------------------------
# Эти модули не зависят от переменных окружения вашего проекта,
# поэтому их можно смело импортировать в самом верху (требование PEP 8 / E402).
# ------------------------------------------------------------------------------
import asyncio
import os
import shutil
import sys
import tempfile
from typing import Any, AsyncGenerator, Generator
from unittest.mock import AsyncMock, patch

import pytest
import redis.asyncio as redis
from faststream.kafka import KafkaBroker
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, text
from sqlalchemy.engine import URL
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import Session, SessionTransaction
from sqlalchemy.pool import NullPool

# ------------------------------------------------------------------------------
# 2. НАСТРОЙКА ОКРУЖЕНИЯ (ПЕРЕД ИМПОРТОМ ВАШИХ МОДУЛЕЙ!)
# ------------------------------------------------------------------------------
# ВАЖНО: Устанавливаем переменные СЕЙЧАС, чтобы при импорте
# libs.config и других модулей ниже они уже подхватили правильные значения.
# Определяем окружение: CI или локальная разработка
# ------------------------------------------------------------------------------

IS_CI = os.getenv("CI", "false").lower() == "true"

if IS_CI:
    # В GitHub Actions используем порты сервисов напрямую
    os.environ["POSTGRES_HOST"] = "localhost"
    os.environ["POSTGRES_PORT"] = "5432"  # Стандартный порт в CI
    os.environ["REDIS_URL"] = "redis://localhost:6379/0"
    os.environ["KAFKA_BOOTSTRAP_SERVERS"] = "localhost:9092"
else:
    # Локально используем порты из docker-compose
    os.environ["POSTGRES_HOST"] = "localhost"
    os.environ["POSTGRES_PORT"] = "5433"  # Порт из docker-compose для тестов
    os.environ["REDIS_URL"] = "redis://localhost:6379/0"
    os.environ["KAFKA_BOOTSTRAP_SERVERS"] = "localhost:9092"

# Создаём временную директорию для медиа-файлов тестов
TEST_MEDIA_DIR = tempfile.mkdtemp(prefix="twitter_test_media_")
os.environ["MEDIA_DIR"] = TEST_MEDIA_DIR

# Глобальная переменная для Kafka (используется в фикстурах)
kafka_url = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")

# Настройка event loop для Windows (должна быть до любых асинхронных операций)
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


# ------------------------------------------------------------------------------
# 3. ИМПОРТЫ: ГРУППА 2 — Модули вашего проекта
# ------------------------------------------------------------------------------
# Эти модули читают настройки при импорте, поэтому импортируем их
# ПОСЛЕ установки os.environ выше.
# Добавляем # noqa: E402, чтобы линтер не ругался на порядок импортов.
# ------------------------------------------------------------------------------
# fmt: off
from libs import redis_client as redis_module  # noqa: E402
from libs.config import settings  # noqa: E402
from libs.database import Base, get_db  # noqa: E402
from services.gateway.main import app  # noqa: E402
from services.users.app.models import User  # noqa: E402

# fmt: on

# ------------------------------------------------------------------------------
# 4. ПРОВЕРКА И ВСПОМОГАТЕЛЬНЫЙ КОД
# ------------------------------------------------------------------------------

# Отладочный вывод: убеждаемся, что settings подхватил наши переменные
# Если здесь видите 'postgres' вместо 'localhost' — значит, settings
# был импортирован раньше времени (проверьте, нет ли циклических импортов).
print(f"✓ [DEBUG] settings.postgres_host = {settings.postgres_host}")
print(f"✓ [DEBUG] settings.postgres_port = {settings.postgres_port}")
print(
    f"✓ [DEBUG] TEST_DATABASE_URL будет сформирован на основе: {settings.sqlalchemy_database_url}"
)


def get_test_db_url(base_url: str, db_name: str) -> str:
    """
    Безопасно формирует URL тестовой БД, заменяя только имя базы данных.
    Избегает ошибок при использовании .replace(), который может заменить
    часть строки в неожиданном месте.
    """
    # Парсим исходный URL
    url_obj = URL.create(
        drivername=base_url.split("://")[0],  # postgresql+asyncpg
        username=settings.postgres_user,
        password=settings.postgres_password,
        host=settings.postgres_host,
        port=settings.postgres_port,
        database=db_name,  # Подставляем нужное имя БД
    )
    return str(url_obj.render_as_string(hide_password=False))


# Имя тестовой БД и её URL
TEST_DB_NAME = f"{settings.postgres_db}_test"
TEST_DATABASE_URL = get_test_db_url(settings.sqlalchemy_database_url, TEST_DB_NAME)


async def mock_kafka_publish(*args: Any, **kwargs: Any) -> None:
    """Заглушка для Kafka: предотвращает реальные отправки сообщений в тестах."""
    pass


def reset_redis_singleton() -> None:
    """
    Сбрасывает глобальный синглтон Redis-клиента.
    Нужно, чтобы избежать конфликта event loop между тестами.
    """
    redis_module.redis_client = None


# ------------------------------------------------------------------------------
# 5. ФИКСТУРЫ
# ------------------------------------------------------------------------------


# === 5.1. Создание/удаление тестовой БД (один раз на всю сессию тестов) ===
@pytest.fixture(scope="session", autouse=True)
def setup_test_database() -> Generator[None, None, None]:
    """
    Создаёт тестовую БД перед запуском всех тестов и удаляет после.
    Использует отдельное подключение к БД 'postgres' для управления другими БД.
    """

    async def _create_db() -> None:
        # URL для подключения к системной БД 'postgres' (чтобы создавать/удалять другие)
        admin_url = get_test_db_url(settings.sqlalchemy_database_url, "postgres")
        engine = create_async_engine(
            admin_url, isolation_level="AUTOCOMMIT", poolclass=NullPool
        )

        async with engine.connect() as conn:
            # Удаляем старую тестовую БД, если осталась после прошлого запуска
            await conn.execute(
                text(f'DROP DATABASE IF EXISTS "{TEST_DB_NAME}" WITH (FORCE)')
            )
            # Создаём чистую тестовую БД
            await conn.execute(text(f'CREATE DATABASE "{TEST_DB_NAME}"'))
        await engine.dispose()

        # Создаём таблицы в новой тестовой БД
        test_engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await test_engine.dispose()

    async def _drop_db() -> None:
        """Удаляет тестовую БД после завершения всех тестов."""
        admin_url = get_test_db_url(settings.sqlalchemy_database_url, "postgres")
        engine = create_async_engine(
            admin_url, isolation_level="AUTOCOMMIT", poolclass=NullPool
        )
        async with engine.connect() as conn:
            await conn.execute(
                text(f'DROP DATABASE IF EXISTS "{TEST_DB_NAME}" WITH (FORCE)')
            )
        await engine.dispose()

    # --- EXECUTE SETUP ---
    asyncio.run(_create_db())
    yield  # <-- Здесь выполняются все тесты
    # --- EXECUTE TEARDOWN ---
    asyncio.run(_drop_db())

    # Очищаем временную папку с медиа
    if os.path.exists(TEST_MEDIA_DIR):
        shutil.rmtree(TEST_MEDIA_DIR, ignore_errors=True)


# === 5.2. Сессия БД для каждого теста (изоляция через транзакции) ===
@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Создаёт изолированную сессию БД для каждого теста.
    Использует вложенные транзакции (SAVEPOINT): после каждого теста
    всё откатывается, БД остаётся чистой.
    """
    reset_redis_singleton()  # Сбрасываем Redis перед тестом

    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)

    async with engine.connect() as connection:
        # Начинаем внешнюю транзакцию
        trans = await connection.begin()
        # Создаём сессию, привязанную к этому соединению
        session = AsyncSession(bind=connection, expire_on_commit=False)
        # Начинаем вложенную транзакцию (точка сохранения)
        await connection.begin_nested()

        # Слушатель события: после завершения каждой вложенной транзакции
        # автоматически создаём новую, чтобы можно было делать несколько
        # commit/rollback внутри одного теста без реального сохранения.
        @event.listens_for(session.sync_session, "after_transaction_end", once=True)
        def restart_savepoint(
            session_obj: Session, transaction_obj: SessionTransaction
        ) -> None:
            if transaction_obj.nested and session_obj.is_active:
                session_obj.begin_nested()

        # === Seed Data: создаём тестового пользователя ===
        user = User(name="TestUser", api_key_hash=User.hash_api_key("test"))
        session.add(user)
        await session.flush()  # Фиксируем в БД, но не коммитим (внутри SAVEPOINT)

        yield session  # <-- Тест получает сессию здесь

        # После теста: закрываем сессию и откатываем ВСЕ изменения
        await session.close()
        await trans.rollback()  # Откатывает и внешнюю, и все вложенные транзакции

    await engine.dispose()
    reset_redis_singleton()  # Сбрасываем Redis после теста


# === 5.3. HTTP-клиент для тестов ===
@pytest.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    AsyncClient для тестирования API.
    Подменяет зависимость get_db на нашу тестовую сессию.
    Мокает публикацию в Kafka, чтобы не было сетевых вызовов.
    """

    # Подмена зависимости FastAPI: вместо реальной БД — наша тестовая сессия
    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    # Мокаем Kafka: заменяем реальный publish на заглушку
    # ВАЖНО: путь "libs.kafka_conf.broker.publish" должен совпадать с тем,
    # где функция ФАКТИЧЕСКИ используется (импортирована), а не где определена.
    with patch("libs.kafka_conf.broker.publish", new_callable=AsyncMock) as mock_pub:
        mock_pub.side_effect = mock_kafka_publish

        async with AsyncClient(
            transport=ASGITransport(app=app),
            base_url="http://test",
        ) as ac:
            yield ac

    # Очистка
    app.dependency_overrides.clear()


# === 5.4. Redis-клиент для тестов ===
@pytest.fixture(scope="function")
async def redis_client() -> AsyncGenerator["redis.Redis[str]", None]:
    """
    Изолированный клиент Redis для тестов.
    Подключается к реальному Redis на localhost:6379.
    """
    reset_redis_singleton()

    redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    client = redis.from_url(redis_url, decode_responses=True)

    yield client

    await client.close()
    reset_redis_singleton()


# === 5.5. Kafka-брокер для тестов (если нужен реальный коннект) ===
@pytest.fixture(scope="function")
async def kafka_broker() -> AsyncGenerator[KafkaBroker, None]:
    """
    Экземпляр KafkaBroker для тестов.
    Если используете моки — эта фикстура может не понадобиться.
    """
    broker = KafkaBroker(kafka_url)
    await broker.start()
    yield broker
    await broker.stop()
