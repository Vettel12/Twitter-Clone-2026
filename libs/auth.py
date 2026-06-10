"""
Единый модуль аутентификации.

Содержит зависимость ``get_current_user`` для использования
во всех защищённых эндпоинтах FastAPI через ``Depends()``.
"""

from typing import TYPE_CHECKING, Annotated, Optional

import structlog
from fastapi import Depends, Header, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from libs.database import get_db

if TYPE_CHECKING:
    from services.users.app.models import User

logger = structlog.get_logger(__name__)


async def _get_user_by_api_key(db: AsyncSession, api_key: str) -> "User | None":
    """
    Найти пользователя по API-ключу (ленивый импорт).

    Ленивый импорт необходим для избежания циклических зависимостей:
    ``libs.auth`` импортируется в маршрутах, которые импортируются
    в ``services.users.app``, который может импортировать ``libs.auth``.

    SQL:
        SELECT * FROM users WHERE api_key_hash = :api_key_hash LIMIT 1;

    Args:
        db: Асинхронная сессия базы данных.
        api_key: Открытый API-ключ (будет захеширован).

    Returns:
        Объект User или None.
    """
    from services.users.app.crud import get_user_by_api_key

    return await get_user_by_api_key(db, api_key)


async def get_current_user(
    db: Annotated[AsyncSession, Depends(get_db)],
    api_key: Annotated[Optional[str], Header(alias="api-key")] = None,
) -> "User":
    """
    Зависимость FastAPI для авторизации по API-ключу.

    Извлекает заголовок ``api-key``, хеширует его значение
    и ищет пользователя в базе данных.

    Args:
        db: Асинхронная сессия базы данных (внедряется автоматически).
        api_key: Значение заголовка ``api-key`` (внедряется автоматически).

    Returns:
        Объект User текущего пользователя.

    Raises:
        HTTPException 401: Если заголовок отсутствует или ключ недействителен.
    """
    if not api_key:
        logger.warning("auth_failed", reason="missing_api_key")
        raise HTTPException(status_code=401, detail="Отсутствует API-ключ")

    user = await _get_user_by_api_key(db, api_key)
    if not user:
        logger.warning("auth_failed", reason="invalid_api_key")
        raise HTTPException(status_code=401, detail="Недействительный API-ключ")

    logger.info("user_authenticated", user_id=user.id, name=user.name)
    return user
