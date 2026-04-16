import asyncio
import os
from contextlib import asynccontextmanager
from typing import Any, AsyncGenerator, Awaitable, Callable

import structlog
import uvicorn
from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from prometheus_fastapi_instrumentator import Instrumentator
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

# Импортируем брокера и роутеры
from libs.config import settings
from libs.correlation_id import CorrelationIdMiddleware
from libs.database import get_db
from libs.kafka_conf import broker

# 1. Подключаем настройку логирования (ПЕРВЫМ ДЕЛОМ)
from libs.logging_config import setup_logging
from libs.redis_client import close_redis
from services.tweets.app import router as tweets_router
from services.users.app import router as users_router

setup_logging()

DbSession = Depends(get_db)

logger = structlog.get_logger(__name__)


# ✅ NEW: Security Headers Middleware
async def add_security_headers(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Add security headers to all responses."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = (
        "max-age=31536000; includeSubDomains"
    )
    return response


# Lifespan context manager для FastAPI
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info("Starting Kafka Broker connection...")

    max_retries = 10
    retry_delay = 5

    for attempt in range(max_retries):
        try:
            await broker.start()
            logger.info("✅ Kafka Broker connected.")
            break
        except Exception as e:
            logger.warning(
                f"Kafka connection attempt {attempt + 1}/{max_retries} failed: {e}"
            )
            if attempt < max_retries - 1:
                await asyncio.sleep(retry_delay)
            else:
                logger.error("❌ Failed to connect to Kafka after maximum retries.")
                # Опционально: raise RuntimeError("Kafka connection failed") from e

    yield  # Приложение работает

    # === Graceful shutdown ===
    logger.info("🛑 Stopping services...")

    # Закрываем Kafka (с безопасной обработкой ошибок)
    try:
        await broker.close()  # ← правильный метод
        logger.info("✅ Kafka Broker closed.")
    except Exception as e:
        logger.warning(f"Error closing Kafka broker: {e}", exc_info=True)

    # Закрываем Redis
    await close_redis()
    logger.info("✅ All services stopped.")


# Создаем экземпляр приложения
app = FastAPI(
    title="Twitter Clone 2026",
    description="Микросервисный клон Twitter (Modular Monolith)",
    version="1.0.0",
    docs_url="/api/docs",  # ← Swagger UI
    openapi_url="/api/openapi.json",  # ← Схема API (ОБЯЗАТЕЛЬНО!)
    redoc_url="/api/redoc",  # ← Опционально
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


# Настройка CORS (✅ FIXED: Ограничено до конкретных origins)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=settings.cors_allow_credentials,
    allow_methods=settings.cors_methods_list,
    allow_headers=settings.cors_headers_list,
    max_age=settings.cors_max_age,
)

# ✅ NEW: Добавляем security headers middleware
app.add_middleware(BaseHTTPMiddleware, dispatch=add_security_headers)

# ✅ Correlation ID middleware для сквозного трейсинга
app.add_middleware(CorrelationIdMiddleware)

# Подключаем роутеры (API endpoints)
app.include_router(users_router)
app.include_router(tweets_router)

Instrumentator().instrument(app).expose(app)

# Монтируем статические файлы для фронтенда
# Важно: монтируем на /static, чтобы не перекрыть /api/*
frontend_path = os.path.join(os.path.dirname(__file__), "..", "..", "frontend")
if os.path.exists(frontend_path):
    app.mount("/static", StaticFiles(directory=frontend_path), name="frontend-static")

    # Создаём redirect с / на /static/index.html
    @app.get("/")
    async def serve_index() -> RedirectResponse:
        return RedirectResponse(url="/static/index.html")


# Монтируем статические файлы для медиа
# Используем переменную окружения MEDIA_DIR для единообразия (Docker, K8s, тесты)
media_path = os.environ.get("MEDIA_DIR", os.path.join(os.path.dirname(__file__), "..", "..", "media"))
if os.path.exists(media_path):
    app.mount("/media", StaticFiles(directory=media_path), name="media")


# Переопределяем функцию получения OpenAPI schema с правильной версией
def get_openapi_schema() -> dict[str, Any]:
    """Получить OpenAPI schema с правильной версией."""
    # Всегда генерируем новую схему (не используем кеш)
    logger.info("Generating OpenAPI schema...")

    # Используем встроенный метод FastAPI для генерации путей
    generated_schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
    )

    # Убеждаемся что версия правильная
    if generated_schema:
        generated_schema["openapi"] = "3.0.3"
        logger.info(f"OpenAPI version set to: {generated_schema.get('openapi')}")
        logger.info(f"Swagger docs_url: {app.docs_url}")
    else:
        logger.error("Failed to generate OpenAPI schema")

    app.openapi_schema = generated_schema
    return app.openapi_schema


@app.get("/openapi.json", include_in_schema=False)
async def get_openapi_endpoint() -> dict[str, Any]:
    """Эндпоинт для получения OpenAPI schema."""
    return get_openapi_schema()


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


@app.get("/api", tags=["Root"])
async def api_root() -> dict[str, str]:
    """Корневой API эндпоинт для проверки, что сервер жив."""
    return {"message": "Twitter Clone API is running"}


if __name__ == "__main__":
    host = os.getenv("APP_HOST", "127.0.0.1")
    port = int(os.getenv("APP_PORT", 8000))

    uvicorn.run("services.gateway.main:app", host=host, port=port, reload=True)
