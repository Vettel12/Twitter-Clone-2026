import logging
import uuid
from pathlib import Path
from typing import Any, List, Optional, cast

import aiofiles
from fastapi import UploadFile
from sqlalchemy import delete, desc, or_, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from libs.kafka_conf import TOPIC_TWEETS, broker
from libs.redis_client import get_redis
from libs.schemas import TweetData
from services.users.app.models import Follower

from .models import Like, Media, Tweet

logger = logging.getLogger(__name__)

# === CONSTANTS ===
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB


# === CACHE UTILITIES ===
async def invalidate_cache_keys(keys: List[str]) -> None:
    """Delete cache keys with retry logic."""
    if not keys:
        return
    try:
        r = await get_redis()
        await r.delete(*keys)
        logger.info(f"Cache invalidated: {len(keys)} keys")
    except Exception as e:
        logger.error(f"Cache error: {e}")


async def get_follower_ids(db: AsyncSession, user_id: int) -> List[int]:
    """Get all followers of a user."""
    stmt = select(Follower.follower_id).where(Follower.followed_id == user_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())


# --- MEDIA ---


async def save_media(db: AsyncSession, file: UploadFile) -> int:
    """
    Сохраняет файл на диск с допушенной валидацией.
    ✅ FIXED: Валидация типа, размера, и magic bytes
    """
    logger.info(f"Saving media file: {file.filename}")

    # ✅ Валидация расширения
    if file.filename:
        ext = Path(file.filename).suffix.lower()
        if ext not in ALLOWED_EXTENSIONS:
            logger.warning(f"Invalid file extension: {ext}")
            raise ValueError(f"Invalid file type: {ext}. Allowed: {ALLOWED_EXTENSIONS}")
    else:
        raise ValueError("Filename is required")

    # ✅ Валидация размера и получение контента
    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        logger.warning(f"File too large: {len(content)} bytes")
        raise ValueError(
            f"File too large: {len(content)} bytes. Max: {MAX_FILE_SIZE} bytes"
        )

    if len(content) == 0:
        raise ValueError("File is empty")

    # ✅ Валидация magic bytes (проверка что это действительно изображение)
    valid_image = (
        content.startswith(b"\xff\xd8\xff")  # JPEG
        or content.startswith(b"\x89PNG")  # PNG
        or content.startswith(b"GIF")  # GIF
    )

    if not valid_image:
        logger.warning("Invalid image content (magic bytes check failed)")
        raise ValueError("Invalid image file (magic bytes check failed)")

    # Сохраняем файл
    media_dir = Path("media")
    media_dir.mkdir(exist_ok=True, mode=0o755)
    unique_filename = f"{uuid.uuid4()}{ext}"
    file_path = media_dir / unique_filename

    async with aiofiles.open(file_path, "wb") as out_file:
        await out_file.write(content)

    # Устанавливаем права на чтение для всех
    import os

    os.chmod(file_path, 0o644)

    db_media = Media(file_path=str(file_path))
    db.add(db_media)
    await db.commit()
    await db.refresh(db_media)

    logger.info(f"Media saved safely with ID: {db_media.id}")
    return db_media.id


# --- TWEETS ---


async def create_tweet(
    db: AsyncSession,
    author_id: int,
    content: str,
    media_ids: Optional[List[int]] = None,
) -> int:
    """
    Создает твит и привязывает к нему медиа-файлы.
    ✅ FIXED: Инвалидирует кэш для ВСЕХподписчиков автора
    """
    logger.info(f"User {author_id} creating tweet")

    new_tweet = Tweet(content=content, author_id=author_id)
    db.add(new_tweet)
    await db.flush()

    if media_ids:
        stmt = (
            update(Media).where(Media.id.in_(media_ids)).values(tweet_id=new_tweet.id)
        )
        await db.execute(stmt)

    await db.commit()

    # === INVALIDATE CACHE (FIXED) ===
    try:
        cache_keys = [f"feed:{author_id}"]
        # ✅ НОВОЕ: Получаем всех подписчиков и инвалидируем их кэш
        follower_ids = await get_follower_ids(db, author_id)
        if follower_ids:
            cache_keys.extend([f"feed:{fid}" for fid in follower_ids])
        await invalidate_cache_keys(cache_keys)
    except Exception as e:
        logger.error(f"Cache invalidation error: {e}")
    # =================================

    # === FASTSTREAM PRODUCER ===
    try:
        # Создаем объект события (Pydantic модель)
        event_data = TweetData(
            tweet_id=new_tweet.id,
            author_id=author_id,
            content=content,
            media_ids=media_ids or [],
        )

        logger.info(f"Publishing event to Kafka topic '{TOPIC_TWEETS}'")
        await broker.publish(event_data, topic=TOPIC_TWEETS)
        logger.info("Event published successfully")

    except Exception as e:
        logger.error(f"Failed to publish event to Kafka: {e}", exc_info=True)
    # ===========================

    return new_tweet.id


async def delete_tweet(db: AsyncSession, user_id: int, tweet_id: int) -> bool:
    """
    Удаляет твит, если пользователь — автор.
    """
    logger.info(f"User {user_id} attempting to delete tweet {tweet_id}")

    result = await db.execute(select(Tweet).where(Tweet.id == tweet_id))
    tweet = result.scalar_one_or_none()

    if not tweet:
        logger.warning(f"Tweet {tweet_id} not found")
        return False

    if tweet.author_id != user_id:
        logger.warning(f"User {user_id} permission denied for tweet {tweet_id}")
        raise PermissionError("Вы не можете удалить чужой твит")

    await db.delete(tweet)
    await db.commit()
    logger.info(f"Tweet {tweet_id} deleted")
    return True


async def get_feed(db: AsyncSession, user_id: int, limit: int = 100) -> List[Tweet]:
    """
    Получает ленту твитов для пользователя с сортировкой по времени создания.
    """
    logger.info(f"Fetching feed for user {user_id}")

    stmt = (
        select(Tweet)
        .options(
            selectinload(Tweet.author),
            selectinload(Tweet.media),
            selectinload(Tweet.likes).selectinload(Like.user),
        )
        .join(Follower, Follower.followed_id == Tweet.author_id, isouter=True)
        .where(or_(Follower.follower_id == user_id, Tweet.author_id == user_id))
        .order_by(desc(Tweet.created_at))
        .limit(limit)
    )

    result = await db.execute(stmt)
    tweets = result.scalars().unique().all()

    return list(tweets)


async def get_tweet_by_id(db: AsyncSession, tweet_id: int) -> Optional[Tweet]:
    """
    Получает твит по ID со всеми связанными данными (автор, медиа, лайки).
    """
    logger.info(f"Fetching tweet {tweet_id}")

    stmt = (
        select(Tweet)
        .options(
            selectinload(Tweet.author),
            selectinload(Tweet.media),
            selectinload(Tweet.likes).selectinload(Like.user),
        )
        .where(Tweet.id == tweet_id)
    )

    result = await db.execute(stmt)
    tweet = result.scalar_one_or_none()

    return tweet


# --- LIKES ---


async def add_like(db: AsyncSession, user_id: int, tweet_id: int) -> bool:
    logger.info(f"User {user_id} liking tweet {tweet_id}")

    tweet_res = await db.execute(select(Tweet).where(Tweet.id == tweet_id))
    if not tweet_res.scalar_one_or_none():
        return False

    like = Like(user_id=user_id, tweet_id=tweet_id)
    db.add(like)
    try:
        await db.commit()
        return True
    except Exception:
        await db.rollback()
        return False


async def remove_like(db: AsyncSession, user_id: int, tweet_id: int) -> bool:
    logger.info(f"User {user_id} unliking tweet {tweet_id}")

    stmt = delete(Like).where(Like.user_id == user_id, Like.tweet_id == tweet_id)
    result = cast(CursorResult[Any], await db.execute(stmt))
    await db.commit()

    if result.rowcount > 0:
        return True

    return False
