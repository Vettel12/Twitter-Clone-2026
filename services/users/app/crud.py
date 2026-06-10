"""
CRUD-операции для пользователей и подписок.

Каждая функция содержит:
- Описание на русском языке
- SQL-эквивалент для понимания работы с базой данных
- Корректные аннотации типов по PEP 484
"""

from typing import Any, Optional, cast

import structlog
from sqlalchemy import delete, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from libs.cache_keys import invalidate_user_cache

from .models import Follower, User

logger = structlog.get_logger(__name__)


# === АВТОРИЗАЦИЯ ===


async def get_user_by_api_key(db: AsyncSession, api_key: str) -> Optional[User]:
    """
    Найти пользователя по API-ключу для аутентификации.

    Ключ хешируется алгоритмом SHA-256 перед сравнением.

    SQL:
        SELECT * FROM users
        WHERE api_key_hash = :api_key_hash
        LIMIT 1;

    Args:
        db: Асинхронная сессия базы данных.
        api_key: Открытый API-ключ (будет захеширован).

    Returns:
        Объект User или None, если ключ не найден.
    """
    api_key_hash = User.hash_api_key(api_key)
    stmt = select(User).where(User.api_key_hash == api_key_hash)
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


# === ПРОФИЛЬ ПОЛЬЗОВАТЕЛЯ ===


async def get_user_by_id(db: AsyncSession, user_id: int) -> Optional[User]:
    """
    Получить профиль пользователя по идентификатору.

    Загружает связанные данные (подписчики и подписки) одним запросом
    через ``selectinload``, чтобы избежать N+1.

    SQL:
        SELECT users.*, followers.*, following.*
        FROM users
        LEFT OUTER JOIN followers ON users.id = followers.followed_id
        LEFT OUTER JOIN followers AS following ON users.id = following.follower_id
        WHERE users.id = :user_id
        LIMIT 1;

    Args:
        db: Асинхронная сессия базы данных.
        user_id: Идентификатор пользователя.

    Returns:
        Объект User или None, если пользователь не найден.
    """
    stmt = (
        select(User)
        .options(
            selectinload(User.followers),
            selectinload(User.following),
        )
        .where(User.id == user_id)
    )
    result = await db.execute(stmt)
    return result.scalar_one_or_none()


# === ПОДПИСКИ ===


async def follow_user(db: AsyncSession, follower_id: int, followed_id: int) -> bool:
    """
    Подписать одного пользователя на другого.

    Проверки:
        1. Нельзя подписаться на себя.
        2. Нельзя подписаться повторно.

    SQL (проверка):
        SELECT * FROM followers
        WHERE follower_id = :follower_id AND followed_id = :followed_id
        LIMIT 1;

    SQL (вставка):
        INSERT INTO followers (follower_id, followed_id)
        VALUES (:follower_id, :followed_id);

    После успешной подписки инвалидирует кэш ленты подписчика.

    Args:
        db: Асинхронная сессия базы данных.
        follower_id: Идентификатор подписчика.
        followed_id: Идентификатор пользователя, на которого подписываются.

    Returns:
        True при успешной подписке; False при подписке на себя или повторной.
    """
    # Нельзя подписаться на себя
    if follower_id == followed_id:
        return False

    # Проверка на повторную подписку
    existing = await db.execute(
        select(Follower).where(
            Follower.follower_id == follower_id,
            Follower.followed_id == followed_id,
        )
    )
    if existing.scalar_one_or_none():
        return False

    # Вставка записи
    new_follow = Follower(follower_id=follower_id, followed_id=followed_id)
    db.add(new_follow)
    await db.commit()

    # Инвалидация кэша ленты подписчика
    await invalidate_user_cache(follower_id)
    logger.info("follow_success", follower_id=follower_id, followed_id=followed_id)

    return True


async def unfollow_user(db: AsyncSession, follower_id: int, followed_id: int) -> bool:
    """
    Отписать пользователя от другого пользователя.

    SQL (удаление):
        DELETE FROM followers
        WHERE follower_id = :follower_id AND followed_id = :followed_id;

    После успешной отписки инвалидирует кэш ленты отписавшегося.

    Args:
        db: Асинхронная сессия базы данных.
        follower_id: Идентификатор отписывающегося пользователя.
        followed_id: Идентификатор пользователя, от которого отписываются.

    Returns:
        True при успешной отписке; False — если связи не существовало.
    """
    stmt = delete(Follower).where(
        Follower.follower_id == follower_id,
        Follower.followed_id == followed_id,
    )
    result = cast("CursorResult[Any]", await db.execute(stmt))
    await db.commit()

    success = result.rowcount > 0

    if success:
        # Инвалидация кэша ленты отписавшегося
        await invalidate_user_cache(follower_id)
        logger.info(
            "unfollow_success",
            follower_id=follower_id,
            followed_id=followed_id,
        )
    else:
        logger.warning(
            "unfollow_not_found",
            follower_id=follower_id,
            followed_id=followed_id,
        )

    return success
