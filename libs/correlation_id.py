"""
Correlation ID middleware для сквозного трейсинга запросов.

Генерирует уникальный ID для каждого HTTP-запроса, привязывает его
к контексту логирования (structlog contextvars) и прокидывает в:
- Заголовки ответа (X-Request-ID)
- Логи всех сервисов
- Kafka сообщения (через get_correlation_id())
"""

import uuid
from contextvars import ContextVar
from typing import Awaitable, Callable

import structlog
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

# ContextVar для хранения текущего correlation_id
_correlation_id: ContextVar[str] = ContextVar("correlation_id", default="")

HEADER_NAME = "X-Request-ID"


def get_correlation_id() -> str:
    """
    Получить текущий correlation_id из контекста.
    Используется в любом месте кода для логирования или проброса в Kafka.
    """
    return _correlation_id.get() or "no-correlation-id"


def set_correlation_id(correlation_id: str) -> None:
    """Установить correlation_id в текущий контекст."""
    _correlation_id.set(correlation_id)


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """
    Middleware для генерации/прокидывания correlation_id.

    Если клиент прислал X-Request-ID — используем его.
    Иначе генерируем новый UUID.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        # Берём из заголовка или генерируем новый
        correlation_id = request.headers.get(HEADER_NAME) or str(uuid.uuid4())

        # Биндим в structlog contextvars — все логи получат correlation_id
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(correlation_id=correlation_id)

        # Сохраняем в ContextVar для программного доступа
        set_correlation_id(correlation_id)

        # Обрабатываем запрос
        response = await call_next(request)

        # Добавляем correlation_id в заголовок ответа
        response.headers[HEADER_NAME] = correlation_id

        return response
