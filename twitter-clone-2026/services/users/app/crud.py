import logging
from typing import Any, cast

from sqlalchemy import delete, select
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from libs.redis_client import get_redis  # <--- Добавить импорт

from .models import Follower, User

logger = logging.getLogger(__name__)


# 1. Получение информации о свем профиле
async def get_user_by_api_key(db: AsyncSession, api_key: str) -> User | None:
    """
    Получает пользователя по API-ключу.
    Используется для аутентификации.
    ✅ FIXED: Сравнивает хеш ключа, а не plain text
    """
    from .models import User

    api_key_hash = User.hash_api_key(api_key)
    query = select(User).where(User.api_key_hash == api_key_hash)
    result = await db.execute(query)
    return result.scalar_one_or_none()


# 2. Получение информации о о пользователе по id
async def get_user_by_id(db: AsyncSession, user_id: int) -> User | None:
    """
    Получает профиль пользователя по ID с загрузкой подписчиков.
    selectinload нужен, чтобы сразу вытащить related objects (followers/following)
    и не спамить базу лишними запросами при сериализации.
    SELECT * FROM users WHERE id = :user_id
    """
    query = (
        select(User)
        .options(selectinload(User.followers), selectinload(User.following))
        .where(User.id == user_id)
    )
    result = await db.execute(query)
    return result.scalar_one_or_none()


# 3. Подписка на другого пользователя по id
async def follow_user(db: AsyncSession, follower_id: int, followed_id: int) -> bool:
    if follower_id == followed_id:
        return False

    existing = await db.execute(
        select(Follower).where(
            Follower.follower_id == follower_id, Follower.followed_id == followed_id
        )
    )
    if existing.scalar_one_or_none():
        return False

    new_follow = Follower(follower_id=follower_id, followed_id=followed_id)
    db.add(new_follow)
    await db.commit()

    # === СБРОС КЭША (НОВОЕ) ===
    try:
        r = await get_redis()
        # Сбрасываем кэш того, кто подписался (чтобы он увидел новые твиты)
        await r.delete(f"feed:{follower_id}")
        logger.info(f"Cache invalidated for user {follower_id} after follow")
    except Exception as e:
        logger.error(f"Redis error: {e}")
    # =========================

    return True


# 4. Отписка от другого пользователя по id
async def unfollow_user(db: AsyncSession, follower_id: int, followed_id: int) -> bool:
    stmt = delete(Follower).where(
        Follower.follower_id == follower_id, Follower.followed_id == followed_id
    )
    result = cast(CursorResult[Any], await db.execute(stmt))
    await db.commit()

    # === СБРОС КЭША (НОВОЕ) ===
    if result.rowcount > 0:
        try:
            r = await get_redis()
            await r.delete(f"feed:{follower_id}")
            logger.info(f"Cache invalidated for user {follower_id} after unfollow")
        except Exception as e:
            logger.error(f"Redis error: {e}")
    # =========================

    return result.rowcount > 0
