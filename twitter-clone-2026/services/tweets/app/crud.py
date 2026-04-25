"""
CRUD-операции для твитов, медиафайлов и лайков.

Каждая функция содержит:
- Описание на русском языке
- SQL-эквивалент для понимания работы с базой данных
- Корректные аннотации типов по PEP 484
"""

import os
import uuid
from pathlib import Path
from typing import Any, List, Optional, Tuple, cast

import aiofiles
import structlog
from fastapi import UploadFile
from sqlalchemy import delete, desc, or_, select, update
from sqlalchemy.engine import CursorResult
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from libs.cache_keys import invalidate_user_and_followers_cache
from libs.kafka_conf import TOPIC_TWEETS, broker
from libs.schemas import TweetCreatedEvent, TweetData
from services.users.app.models import Follower

from .models import Like, Media, Tweet

logger = structlog.get_logger(__name__)

# === КОНСТАНТЫ ===

# Допустимые расширения файлов изображений
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".gif", ".webp"}
# Максимальный размер файла — 10 МБ
MAX_FILE_SIZE = 10 * 1024 * 1024


# === УТИЛИТЫ ===


async def get_follower_ids(db: AsyncSession, user_id: int) -> List[int]:
    """
    Получить идентификаторы всех подписчиков пользователя.

    SQL:
        SELECT follower_id FROM followers WHERE followed_id = :user_id;

    Args:
        db: Асинхронная сессия базы данных.
        user_id: Идентификатор пользователя, чьих подписчиков ищем.

    Returns:
        Список идентификаторов подписчиков.
    """
    stmt = select(Follower.follower_id).where(Follower.followed_id == user_id)
    result = await db.execute(stmt)
    return list(result.scalars().all())


# === МЕДИАФАЙЛЫ ===


async def save_media(db: AsyncSession, file: UploadFile) -> int:
    """
    Сохранить файл изображения на диск с валидацией.

    Выполняет:
        1. Проверку расширения файла.
        2. Проверку размера (макс. 10 МБ).
        3. Проверку «магических байтов» (JPEG, PNG, GIF).
        4. Сохранение с уникальным именем.
        5. Запись метаданных в таблицу ``media``.

    SQL (вставка):
        INSERT INTO media (file_path) VALUES (:file_path);

    Args:
        db: Асинхронная сессия базы данных.
        file: Загруженный файл изображения.

    Returns:
        Идентификатор сохранённого медиафайла.

    Raises:
        ValueError: Если файл не проходит валидацию.
    """
    logger.info("media_save_start", filename=file.filename)

    # --- Валидация расширения ---
    if not file.filename:
        raise ValueError("Имя файла обязательно")

    ext = Path(file.filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        logger.warning("media_invalid_extension", extension=ext)
        raise ValueError(
            f"Недопустимый тип файла: {ext}. Разрешены: {ALLOWED_EXTENSIONS}"
        )

    # --- Валидация размера и чтение содержимого ---
    content = await file.read()
    if len(content) == 0:
        raise ValueError("Файл пустой")

    if len(content) > MAX_FILE_SIZE:
        logger.warning("media_file_too_large", size=len(content))
        raise ValueError(
            f"Файл слишком большой: {len(content)} байт. Максимум: {MAX_FILE_SIZE}"
        )

    # --- Проверка «магических байтов» ---
    valid_image = (
        content.startswith(b"\xff\xd8\xff")  # JPEG
        or content.startswith(b"\x89PNG")  # PNG
        or content.startswith(b"GIF")  # GIF
        or (
            content.startswith(b"RIFF")
            and len(content) >= 12
            and content[8:12] == b"WEBP"
        )  # WebP
    )
    if not valid_image:
        logger.warning("media_invalid_magic_bytes")
        raise ValueError("Недопустимый файл изображения (проверка магических байтов)")

    # --- Сохранение на диск ---
    # Используем переменную окружения MEDIA_DIR для гибкости (Docker, K8s, тесты)
    media_base = Path(os.environ.get("MEDIA_DIR", "/app/media"))
    media_base.mkdir(parents=True, exist_ok=True, mode=0o777)
    unique_filename = f"{uuid.uuid4()}{ext}"
    file_path = media_base / unique_filename

    async with aiofiles.open(file_path, "wb") as out_file:
        await out_file.write(content)

    # Права на чтение для всех (может не работать с bind mount, игнорируем ошибку)
    try:
        os.chmod(file_path, 0o644)
    except OSError:
        pass

    # --- Запись метаданных в базу ---
    db_media = Media(file_path=str(file_path))
    db.add(db_media)
    await db.commit()
    await db.refresh(db_media)

    logger.info("media_save_success", media_id=db_media.id)
    return db_media.id


# === ТВИТЫ ===


async def create_tweet(
    db: AsyncSession,
    author_id: int,
    content: str,
    media_ids: Optional[List[int]] = None,
) -> int:
    """
    Создать новый твит и привязать к нему медиафайлы.

    SQL (вставка):
        INSERT INTO tweets (content, author_id, created_at, updated_at)
        VALUES (:content, :author_id, NOW(), NOW())
        RETURNING id;

    SQL (обновление медиа):
        UPDATE media SET tweet_id = :tweet_id WHERE id IN (:media_ids);

    После создания твита:
        1. Инвалидирует кэш ленты автора и всех его подписчиков.
        2. Публикует событие в Kafka для асинхронной обработки.

    Args:
        db: Асинхронная сессия базы данных.
        author_id: Идентификатор автора твита.
        content: Текст твита.
        media_ids: Необязательный список идентификаторов медиафайлов.

    Returns:
        Идентификатор созданного твита.
    """
    logger.info("tweet_create_start", author_id=author_id)

    # --- Вставка твита ---
    new_tweet = Tweet(content=content, author_id=author_id)
    db.add(new_tweet)
    await db.flush()

    # --- Привязка медиафайлов ---
    if media_ids:
        stmt = (
            update(Media).where(Media.id.in_(media_ids)).values(tweet_id=new_tweet.id)
        )
        await db.execute(stmt)

    await db.commit()

    # --- Инвалидация кэша ---
    try:
        follower_ids = await get_follower_ids(db, author_id)
        await invalidate_user_and_followers_cache(author_id, follower_ids)
    except Exception as e:
        logger.error("tweet_cache_invalidation_error", error=str(e))

    # --- Публикация события в Kafka ---
    try:
        event = TweetCreatedEvent(
            data=TweetData(
                tweet_id=new_tweet.id,
                author_id=author_id,
                content=content,
                media_ids=media_ids or [],
            )
        )
        logger.info(
            "kafka_publish_start",
            topic=TOPIC_TWEETS,
            event_id=event.event_id,
        )
        await broker.publish(event.model_dump(), topic=TOPIC_TWEETS)
        logger.info("kafka_publish_success", event_id=event.event_id)
    except Exception as e:
        logger.error("kafka_publish_error", error=str(e), exc_info=True)

    return new_tweet.id


async def delete_tweet(
    db: AsyncSession, user_id: int, tweet_id: int
) -> Tuple[bool, List[int]]:
    """
    Удалить твит, если текущий пользователь является его автором.

    SQL (поиск):
        SELECT * FROM tweets WHERE id = :tweet_id LIMIT 1;

    SQL (удаление):
        DELETE FROM tweets WHERE id = :tweet_id;

    Args:
        db: Асинхронная сессия базы данных.
        user_id: Идентификатор текущего пользователя.
        tweet_id: Идентификатор удаляемого твита.

    Returns:
        Кортеж (успех, список идентификаторов подписчиков автора).

    Raises:
        PermissionError: Если пользователь не является автором твита.
    """
    logger.info("tweet_delete_attempt", user_id=user_id, tweet_id=tweet_id)

    # --- Поиск твита ---
    result = await db.execute(select(Tweet).where(Tweet.id == tweet_id))
    tweet = result.scalar_one_or_none()

    if not tweet:
        logger.warning("tweet_delete_not_found", tweet_id=tweet_id)
        return False, []

    if tweet.author_id != user_id:
        logger.warning(
            "tweet_delete_permission_denied", user_id=user_id, tweet_id=tweet_id
        )
        raise PermissionError("Вы не можете удалить чужой твит")

    # --- Удаление ---
    author_id = tweet.author_id
    await db.delete(tweet)
    await db.commit()
    logger.info("tweet_delete_success", tweet_id=tweet_id)

    # --- Подписчики автора для инвалидации кэша ---
    follower_ids = await get_follower_ids(db, author_id)
    return True, follower_ids


async def get_feed(db: AsyncSession, user_id: int, limit: int = 100) -> List[Tweet]:
    """
    Получить ленту твитов для пользователя.

    Включает твиты авторов, на которых подписан пользователь,
    а также собственные твиты пользователя.

    SQL:
        SELECT tweets.*, users.*, media.*, likes.*, users_likes.*
        FROM tweets
        LEFT OUTER JOIN followers ON followers.followed_id = tweets.author_id
        LEFT OUTER JOIN users AS users ON tweets.author_id = users.id
        LEFT OUTER JOIN media ON media.tweet_id = tweets.id
        LEFT OUTER JOIN likes ON likes.tweet_id = tweets.id
        LEFT OUTER JOIN users AS users_likes ON likes.user_id = users_likes.id
        WHERE followers.follower_id = :user_id OR tweets.author_id = :user_id
        ORDER BY tweets.created_at DESC
        LIMIT :limit;

    Args:
        db: Асинхронная сессия базы данных.
        user_id: Идентификатор пользователя.
        limit: Максимальное количество твитов (по умолчанию 100).

    Returns:
        Список объектов Tweet, отсортированных по дате создания.
    """
    logger.info("feed_fetch_start", user_id=user_id)

    stmt = (
        select(Tweet)
        .options(
            selectinload(Tweet.author),
            selectinload(Tweet.media),
            selectinload(Tweet.likes).selectinload(Like.user),
        )
        .join(Follower, Follower.followed_id == Tweet.author_id, isouter=True)
        .where(
            or_(
                Follower.follower_id == user_id,
                Tweet.author_id == user_id,
            )
        )
        .order_by(desc(Tweet.created_at))
        .limit(limit)
    )

    result = await db.execute(stmt)
    tweets = result.scalars().unique().all()

    logger.info("feed_fetch_success", user_id=user_id, tweet_count=len(tweets))
    return list(tweets)


async def get_tweet_by_id(db: AsyncSession, tweet_id: int) -> Optional[Tweet]:
    """
    Получить твит по идентификатору со всеми связанными данными.

    SQL:
        SELECT tweets.*, users.*, media.*, likes.*, users_likes.*
        FROM tweets
        LEFT OUTER JOIN users ON tweets.author_id = users.id
        LEFT OUTER JOIN media ON media.tweet_id = tweets.id
        LEFT OUTER JOIN likes ON likes.tweet_id = tweets.id
        LEFT OUTER JOIN users AS users_likes ON likes.user_id = users_likes.id
        WHERE tweets.id = :tweet_id;

    Параметр ``populate_existing=True`` заставляет SQLAlchemy перечитать
    объект из базы, даже если он уже присутствует в ``identity_map``.
    Это важно после операций like/unlike.

    Args:
        db: Асинхронная сессия базы данных.
        tweet_id: Идентификатор твита.

    Returns:
        Объект Tweet или None, если твит не найден.
    """
    logger.info("tweet_fetch_by_id", tweet_id=tweet_id)

    stmt = (
        select(Tweet)
        .options(
            selectinload(Tweet.author),
            selectinload(Tweet.media),
            selectinload(Tweet.likes).selectinload(Like.user),
        )
        .where(Tweet.id == tweet_id)
        .execution_options(populate_existing=True)
    )

    result = await db.execute(stmt)
    return result.scalar_one_or_none()


# === ЛАЙКИ ===


async def add_like(db: AsyncSession, user_id: int, tweet_id: int) -> bool:
    """
    Добавить лайк к твиту.

    Перед вставкой проверяет:
        1. Существование твита.
        2. Отсутствие повторного лайка (составной первичный ключ).

    SQL (проверка твита):
        SELECT * FROM tweets WHERE id = :tweet_id LIMIT 1;

    SQL (проверка лайка):
        SELECT * FROM likes WHERE user_id = :user_id AND tweet_id = :tweet_id LIMIT 1;

    SQL (вставка):
        INSERT INTO likes (user_id, tweet_id) VALUES (:user_id, :tweet_id);

    Args:
        db: Асинхронная сессия базы данных.
        user_id: Идентификатор пользователя, ставящего лайк.
        tweet_id: Идентификатор твита.

    Returns:
        True, если лайк успешно добавлен; False — если твит не найден или уже лайкнут.
    """
    logger.info("like_add_start", user_id=user_id, tweet_id=tweet_id)

    # --- Проверка существования твита ---
    tweet_res = await db.execute(select(Tweet).where(Tweet.id == tweet_id))
    if not tweet_res.scalar_one_or_none():
        logger.warning("like_add_failed", reason="tweet_not_found", tweet_id=tweet_id)
        return False

    # --- Проверка на повторный лайк ---
    existing = await db.execute(
        select(Like).where(
            Like.user_id == user_id,
            Like.tweet_id == tweet_id,
        )
    )
    if existing.scalar_one_or_none():
        logger.warning(
            "like_add_failed",
            reason="already_liked",
            user_id=user_id,
            tweet_id=tweet_id,
        )
        return False

    # --- Вставка лайка ---
    like = Like(user_id=user_id, tweet_id=tweet_id)
    db.add(like)
    await db.commit()

    logger.info("like_add_success", user_id=user_id, tweet_id=tweet_id)
    return True


async def remove_like(db: AsyncSession, user_id: int, tweet_id: int) -> bool:
    """
    Удалить лайк с твита.

    SQL (удаление):
        DELETE FROM likes
        WHERE user_id = :user_id AND tweet_id = :tweet_id;

    Args:
        db: Асинхронная сессия базы данных.
        user_id: Идентификатор пользователя.
        tweet_id: Идентификатор твита.

    Returns:
        True, если лайк удалён; False — если лайк не найден.
    """
    logger.info("like_remove_start", user_id=user_id, tweet_id=tweet_id)

    stmt = delete(Like).where(
        Like.user_id == user_id,
        Like.tweet_id == tweet_id,
    )
    result = cast("CursorResult[Any]", await db.execute(stmt))
    await db.commit()

    success = result.rowcount > 0
    logger.info(
        "like_remove_result",
        user_id=user_id,
        tweet_id=tweet_id,
        deleted=success,
    )
    return success
