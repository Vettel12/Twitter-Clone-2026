import asyncio
import os
import sys
from typing import AsyncGenerator, Generator

# === ВАЖНО: Переопределяем хосты для локального запуска тестов ===
# Это нужно сделать ДО импорта settings
os.environ["POSTGRES_HOST"] = "localhost"
os.environ["POSTGRES_PORT"] = "5433"  # Порт, который мы пробросили в docker-compose
os.environ["REDIS_URL"] = "redis://localhost:6379/0"
os.environ["KAFKA_BOOTSTRAP_SERVERS"] = "localhost:9092"
# ==============================================================

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import Session, SessionTransaction
from sqlalchemy.pool import NullPool

from libs.config import settings
from libs.database import Base, get_db
from services.gateway.main import app
from services.users.app.models import User

# --- FIX FOR WINDOWS PYTHON 3.13 ---
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
# -----------------------------------

# Генерируем URL тестовой БД
TEST_DB_NAME = settings.postgres_db + "_test"
TEST_DATABASE_URL = settings.sqlalchemy_database_url.replace(
    settings.postgres_db, TEST_DB_NAME
)


# --- 1. SETUP DATABASE (Once per Session) ---
@pytest.fixture(scope="session", autouse=True)
def setup_test_database() -> Generator[None, None, None]:
    """
    Синхронная фикстура (scope="session").
    Запускает асинхронный код через asyncio.run.
    Создает БД один раз перед всеми тестами и удаляет после.
    """

    async def _create_db() -> None:
        admin_url = settings.sqlalchemy_database_url.replace(
            settings.postgres_db, "postgres"
        )
        engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")

        async with engine.connect() as conn:
            # Удаляем старую БД, если есть
            await conn.execute(
                text(f"DROP DATABASE IF EXISTS {TEST_DB_NAME} WITH (FORCE)")
            )
            await conn.execute(text(f"CREATE DATABASE {TEST_DB_NAME}"))
        await engine.dispose()

        # Создаем таблицы
        test_engine = create_async_engine(TEST_DATABASE_URL)
        async with test_engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        await test_engine.dispose()

    async def _drop_db() -> None:
        admin_url = settings.sqlalchemy_database_url.replace(
            settings.postgres_db, "postgres"
        )
        engine = create_async_engine(admin_url, isolation_level="AUTOCOMMIT")
        async with engine.connect() as conn:
            await conn.execute(
                text(f"DROP DATABASE IF EXISTS {TEST_DB_NAME} WITH (FORCE)")
            )
        await engine.dispose()

    # --- RUN SETUP ---
    asyncio.run(_create_db())

    yield  # Здесь выполняются все тесты

    # --- RUN TEARDOWN ---
    asyncio.run(_drop_db())


# --- 2. DB SESSION (Per Test) ---
@pytest.fixture(scope="function")
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    engine = create_async_engine(TEST_DATABASE_URL, poolclass=NullPool)

    async with engine.connect() as connection:
        # 1. Начинаем внешнюю транзакцию
        trans = await connection.begin()

        # 2. Создаем сессию, привязанную к этому соединению
        session = AsyncSession(bind=connection, expire_on_commit=False)

        # 3. Начинаем вложенную транзакцию (SAVEPOINT)
        await connection.begin_nested()

        from sqlalchemy import event

        # Исправленный обработчик событий
        @event.listens_for(session.sync_session, "after_transaction_end")
        def restart_savepoint(
            session_obj: Session, transaction_obj: SessionTransaction
        ) -> None:
            # Проверяем, что завершилась именно вложенная транзакция (SAVEPOINT)
            # и сессия все еще активна (не закрыта)
            if transaction_obj.nested and session_obj.is_active:
                session_obj.begin_nested()

        # Seed Data
        user = User(name="TestUser", api_key="test")
        session.add(user)
        await session.flush()

        yield session

        # Закрываем сессию и откатываем внешнюю транзакцию
        await session.close()
        await trans.rollback()

    await engine.dispose()


# --- 3. CLIENT (Per Test) ---
@pytest.fixture(scope="function")
async def client(db_session: AsyncSession) -> AsyncGenerator[AsyncClient, None]:
    """
    Клиент с подменой БД.
    """

    async def override_get_db() -> AsyncGenerator[AsyncSession, None]:
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()
