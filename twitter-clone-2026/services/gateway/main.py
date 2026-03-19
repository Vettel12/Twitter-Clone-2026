import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# Импортируем брокера
from libs.kafka_conf import broker
from libs.redis_client import close_redis

# Импортируем роутеры
from services.tweets.app import router as tweets_router
from services.users.app import router as users_router

# Настройка логирования
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# Lifespan context manager для FastAPI
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Starting Kafka Broker connection...")
    await broker.start()
    logger.info("Kafka Broker connected.")

    yield  # Приложение работает

    logger.info("Stopping Kafka Broker connection...")
    # ИСПРАВЛЕНО: close() -> stop()
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


@app.get("/", tags=["Root"])
async def root() -> dict[str, str]:
    """
    Корневой эндпоинт для проверки, что сервер жив.
    """
    return {"message": "Twitter Clone API is running"}


if __name__ == "__main__":
    uvicorn.run("services.gateway.main:app", host="0.0.0.0", port=8000, reload=True)
