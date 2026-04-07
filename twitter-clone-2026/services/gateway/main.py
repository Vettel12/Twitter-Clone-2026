import logging
import os
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator

import uvicorn
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

# Импортируем брокера и роутеры
from libs.database import get_db
from libs.kafka_conf import broker

# 1. Подключаем настройку логирования (ПЕРВЫМ ДЕЛОМ)
from libs.logging_config import setup_logging
from libs.redis_client import close_redis
from services.tweets.app import router as tweets_router
from services.users.app import router as users_router

setup_logging()

DbSession = Depends(get_db)

# 2. Создаем логгер для этого файла


logger = logging.getLogger(__name__)


# Lifespan context manager для FastAPI
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Starting Kafka Broker connection...")
    try:
        await broker.start()
        logger.info("Kafka Broker connected.")
    except Exception:
        logger.error("Failed to connect to Kafka", exc_info=True)
        # Можно решить, стоит ли падать приложению, если Kafka недоступна
        # raise e

    yield  # Приложение работает

    logger.info("Stopping Kafka Broker connection...")
    await broker.stop()
    await close_redis()
    logger.info("Kafka Broker stopped.")


# Создаем экземпляр приложения
app = FastAPI(
    title="Twitter Clone 2026",
    description="Микросервисный клон Twitter (Modular Monolith)",
    version="1.0.0",
    docs_url="/api/docs",
    lifespan=lifespan,
)


# Глобальный обработчик ошибок
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    # Structlog сам добавит traceback, если настроен processor StackInfoRenderer
    logger.error(f"Unhandled error: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "result": False,
            "error_type": "InternalServerError",
            "error_message": "An unexpected error occurred.",
        },
    )


# Настройка CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Подключаем роутеры
app.include_router(users_router)
app.include_router(tweets_router)

Instrumentator().instrument(app).expose(app)


@app.get("/api/healthcheck", tags=["Healthcheck"])
async def healthcheck(db: AsyncSession = DbSession) -> dict[str, Any]:
    try:
        result = await db.execute(text("SELECT 1"))
        if result.scalar_one() == 1:
            return {"status": "ok", "database": "ok"}
        return {"status": "error", "database": "error"}
    except Exception as e:
        logger.exception("Database connection error in healthcheck")
        return {"status": "error", "database": "error", "details": str(e)}


@app.get("/", tags=["Root"])
async def root() -> dict[str, str]:
    """Корневой эндпоинт для проверки, что сервер жив."""
    return {"message": "Twitter Clone API is running"}


if __name__ == "__main__":
    host = os.getenv("APP_HOST", "127.0.0.1")
    port = int(os.getenv("APP_PORT", 8000))

    uvicorn.run("services.gateway.main:app", host=host, port=port, reload=True)
