import logging
import uuid
from pathlib import Path
from typing import Any, List, Optional, cast

import aiofiles
from fastapi import UploadFile
from sqlalchemy import delete, desc, func, or_, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from libs.kafka_conf import TOPIC_TWEETS, broker
from libs.redis_client import get_redis
from libs.schemas import TweetData
from services.users.app.models import Follower

from .models import Like, Media, Tweet

# Инициализация логгера для этого модуля
logger = logging.getLogger(__name__)

# --- MEDIA ---


async def save_media(db: AsyncSession, file: UploadFile) -> int:
    """
    Сохраняет файл на диск и создает запись в БД.
    """
    logger.info(f"Saving media file: {file.filename}")
    media_dir = Path("media")
    media_dir.mkdir(exist_ok=True)

    if file.filename:
        file_ext = Path(file.filename).suffix
    else:
        file_ext = ""
    unique_filename = f"{uuid.uuid4()}{file_ext}"
    file_path = media_dir / unique_filename

    content = await file.read()
    async with aiofiles.open(file_path, "wb") as out_file:
        await out_file.write(content)

    db_media = Media(file_path=str(file_path))
    db.add(db_media)
    await db.commit()
    await db.refresh(db_media)

    logger.info(f"Media saved with ID: {db_media.id}")
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

    # === INVALIDATE CACHE ===

    try:
        r = await get_redis()
        await r.delete(f"feed:{author_id}")
        logger.info(f"Cache invalidated for user {author_id}")
    except Exception as e:
        logger.error(f"Redis error: {e}")
    # =========================

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
    Получает ленту твитов для пользователя с комплексной сортировкой.
    """
    logger.info(f"Fetching feed for user {user_id}")

    likes_count = (
        select(Like.tweet_id, func.count(Like.user_id).label("count"))
        .group_by(Like.tweet_id)
        .subquery()
    )

    stmt = (
        select(Tweet)
        .options(
            selectinload(Tweet.author),
            selectinload(Tweet.media),
            selectinload(Tweet.likes).selectinload(Like.user),
        )
        .join(Follower, Follower.followed_id == Tweet.author_id, isouter=True)
        .outerjoin(likes_count, likes_count.c.tweet_id == Tweet.id)
        .where(or_(Follower.follower_id == user_id, Tweet.author_id == user_id))
        .order_by(desc(likes_count.c.count), desc(Tweet.created_at))
        .limit(limit)
    )

    result = await db.execute(stmt)
    tweets = result.scalars().unique().all()

    return list(tweets)


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

        # === СБРОС КЭША (НОВОЕ) ===
        try:
            r = await get_redis()
            await r.delete(f"feed:{user_id}")
            logger.info(f"Cache invalidated for user {user_id} after like")
        except Exception as e:
            logger.error(f"Redis error: {e}")
        # =========================

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
        # === СБРОС КЭША (НОВОЕ) ===
        try:
            r = await get_redis()
            await r.delete(f"feed:{user_id}")
            logger.info(f"Cache invalidated for user {user_id} after unlike")
        except Exception as e:
            logger.error(f"Redis error: {e}")
        # =========================
        return True

    return False
