"""
Маршруты API для управления пользователями.

Эндпоинты:
    - GET  /api/users/me           — профиль текущего пользователя
    - GET  /api/users/{user_id}     — профиль пользователя по ID
    - POST /api/users/{user_id}/follow    — подписка
    - DELETE /api/users/{user_id}/follow  — отписка
"""

from typing import Annotated, Any

import structlog
from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from libs.auth import get_current_user
from libs.database import get_db
from services.users.app import crud, schemas
from services.users.app.models import User

logger = structlog.get_logger(__name__)

router = APIRouter()


@router.get("/api/users/me", response_model=schemas.UserOut)
async def get_me(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> schemas.UserOut:
    """
    Получить профиль текущего авторизованного пользователя.

    Загружает полный профиль с подписчиками и подписками.
    """
    logger.info("user_get_me", user_id=user.id)

    full_user = await crud.get_user_by_id(db, user.id)
    user_response = schemas.UserResponse.model_validate(full_user)

    return schemas.UserOut(user=user_response)


@router.get("/api/users/{user_id}")
async def get_user_profile(
    user_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    """
    Получить публичный профиль пользователя по идентификатору.

    Возвращает стандартную структуру ответа с полем ``result``.
    """
    logger.info("user_get_profile_requested", user_id=user_id)

    user = await crud.get_user_by_id(db, user_id)
    if not user:
        logger.warning("user_profile_not_found", user_id=user_id)
        return {
            "result": False,
            "error_type": "NotFoundError",
            "error_message": "Пользователь не найден",
        }

    user_response = schemas.UserResponse.model_validate(user)
    return schemas.UserOut(user=user_response)


@router.post("/api/users/{user_id}/follow")
async def follow_user(
    user_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    """
    Подписаться на другого пользователя.

    Проверяет:
        - Нельзя подписаться на себя.
        - Нельзя подписаться повторно.
    """
    logger.info("follow_attempt", follower_id=current_user.id, followed_id=user_id)

    success = await crud.follow_user(db, current_user.id, user_id)

    if not success:
        logger.warning(
            "follow_failed",
            follower_id=current_user.id,
            followed_id=user_id,
        )
        return {
            "result": False,
            "error_type": "ActionError",
            "error_message": "Не удалось подписаться (уже подписаны или попытка подписки на себя)",
        }

    logger.info("follow_success", follower_id=current_user.id, followed_id=user_id)
    return {"result": True}


@router.delete("/api/users/{user_id}/follow")
async def unfollow_user(
    user_id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    """
    Отписаться от другого пользователя.

    Возвращает ошибку, если текущий пользователь не был подписан.
    """
    logger.info("unfollow_attempt", follower_id=current_user.id, followed_id=user_id)

    success = await crud.unfollow_user(db, current_user.id, user_id)

    if not success:
        logger.warning(
            "unfollow_not_found",
            follower_id=current_user.id,
            followed_id=user_id,
        )
        return {
            "result": False,
            "error_type": "ActionError",
            "error_message": "Вы не были подписаны на этого пользователя",
        }

    logger.info("unfollow_success", follower_id=current_user.id, followed_id=user_id)
    return {"result": True}
