"""
Маршруты API для управления твитами и лайками.

Эндпоинты:
    - POST   /api/medias                          — загрузка медиафайла
    - POST   /api/tweets                          — создание твита
    - DELETE /api/tweets/{tweet_id}               — удаление твита
    - POST   /api/tweets/{tweet_id}/likes         — лайк твита
    - DELETE /api/tweets/{tweet_id}/likes         — отмена лайка
    - GET    /api/tweets                          — лента твитов с кэшированием
"""

from pathlib import Path
from typing import Annotated, Any, List

import structlog
from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from libs.auth import get_current_user
from libs.cache_keys import (
    FEED_TTL_SECONDS,
    CacheKeys,
    cache_hits_total,
    cache_misses_total,
    get_with_lock,
    invalidate_user_and_followers_cache,
    invalidate_user_cache,
)
from libs.database import get_db
from libs.redis_client import get_redis
from services.tweets.app import crud, schemas
from services.users.app.models import User

logger = structlog.get_logger(__name__)

router = APIRouter()


# === МЕДИАФАЙЛЫ ===


@router.post("/api/medias", response_model=schemas.MediaUploadResponse)
async def upload_media(
    file: Annotated[UploadFile, File(...)],
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> schemas.MediaUploadResponse:
    """
    Загрузить изображение на сервер.

    Файл валидируется по расширению, размеру и «магическим байтам».
    Возвращает идентификатор сохранённого медиафайла.
    """
    logger.info("media_upload_start", user_id=user.id, filename=file.filename)

    media_id = await crud.save_media(db, file)
    logger.info("media_upload_success", user_id=user.id, media_id=media_id)

    return schemas.MediaUploadResponse(media_id=media_id)


# === ТВИТЫ ===


@router.post("/api/tweets", response_model=schemas.TweetCreateResponse)
async def create_tweet(
    tweet_data: schemas.TweetCreate,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> schemas.TweetCreateResponse:
    """
    Создать новый твит от имени текущего пользователя.

    После создания инвалидирует кэш ленты автора и его подписчиков,
    а также публикует событие в Kafka.
    """
    logger.info(
        "tweet_create_start",
        user_id=user.id,
        content_preview=tweet_data.tweet_data[:20],
    )

    tweet_id = await crud.create_tweet(
        db,
        author_id=user.id,
        content=tweet_data.tweet_data,
        media_ids=tweet_data.tweet_media_ids,
    )

    # Инвалидация кэша уже выполнена внутри crud.create_tweet()
    logger.info("tweet_create_success", user_id=user.id, tweet_id=tweet_id)

    return schemas.TweetCreateResponse(tweet_id=tweet_id)


@router.delete("/api/tweets/{tweet_id}")
async def delete_tweet(
    tweet_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    """
    Удалить твит текущего пользователя.

    Инвалидирует кэш ленты автора и всех его подписчиков.
    """
    logger.info("tweet_delete_start", user_id=user.id, tweet_id=tweet_id)

    try:
        success, follower_ids = await crud.delete_tweet(db, user.id, tweet_id)
        if not success:
            logger.warning("tweet_delete_not_found", tweet_id=tweet_id)
            return {
                "result": False,
                "error_type": "NotFoundError",
                "error_message": "Твит не найден",
            }

        # Инвалидируем кэш автора и всех его подписчиков
        await invalidate_user_and_followers_cache(user.id, follower_ids)
        logger.info("tweet_delete_success", user_id=user.id, tweet_id=tweet_id)
        return {"result": True}

    except PermissionError as e:
        logger.warning("tweet_delete_permission_denied", user_id=user.id, tweet_id=tweet_id)
        return {
            "result": False,
            "error_type": "PermissionError",
            "error_message": str(e),
        }


# === ЛАЙКИ ===


@router.post("/api/tweets/{tweet_id}/likes")
async def like_tweet(
    tweet_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    """
    Поставить лайк на твит.

    Инвалидирует кэш ленты текущего пользователя и автора твита.
    Возвращает обновлённый объект твита со списком лайков.
    """
    user_id = user.id
    logger.info("like_start", user_id=user_id, tweet_id=tweet_id)

    # --- Добавляем лайк в БД ---
    success = await crud.add_like(db, user_id, tweet_id)
    if not success:
        logger.warning("like_failed", user_id=user_id, tweet_id=tweet_id)
        return {
            "result": False,
            "error_type": "ActionError",
            "error_message": "Не удалось поставить лайк (твит не найден или уже лайкнут)",
        }

    # --- Получаем обновлённый твит ---
    updated_tweet = await crud.get_tweet_by_id(db, tweet_id)

    # --- Инвалидация кэша ---
    try:
        await invalidate_user_cache(user_id)
        if updated_tweet:
            await invalidate_user_cache(updated_tweet.author_id)
            logger.info(
                "like_cache_invalidated",
                user_id=user_id,
                author_id=updated_tweet.author_id,
            )
        else:
            logger.info("like_cache_invalidated_self", user_id=user_id)
    except Exception as e:
        logger.warning("like_cache_invalidation_error", error=str(e))

    # --- Формируем ответ ---
    if updated_tweet and updated_tweet.likes:
        likes_list = [
            schemas.LikeInTweet(user_id=like.user_id, name=like.user.name)
            for like in updated_tweet.likes
        ]
        attachments_list = [
            f"/media/{Path(media.file_path).name}" for media in updated_tweet.media
        ]
        tweet_out = schemas.TweetOut(
            id=updated_tweet.id,
            content=updated_tweet.content,
            created_at=updated_tweet.created_at,
            author=schemas.UserInTweet.model_validate(updated_tweet.author),
            attachments=attachments_list,
            likes=likes_list,
        )
        return {"result": True, "tweet": tweet_out}

    return {"result": True}


@router.delete("/api/tweets/{tweet_id}/likes")
async def unlike_tweet(
    tweet_id: int,
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    """
    Убрать лайк с твита.

    Инвалидирует кэш ленты текущего пользователя и автора твита.
    """
    user_id = user.id
    logger.info("unlike_start", user_id=user_id, tweet_id=tweet_id)

    # --- Удаляем лайк из БД ---
    success = await crud.remove_like(db, user_id, tweet_id)
    if not success:
        logger.warning("unlike_failed", user_id=user_id, tweet_id=tweet_id)
        return {
            "result": False,
            "error_type": "ActionError",
            "error_message": "Не удалось убрать лайк (лайк не найден)",
        }

    # --- Получаем обновлённый твит ---
    updated_tweet = await crud.get_tweet_by_id(db, tweet_id)

    # --- Инвалидация кэша ---
    try:
        await invalidate_user_cache(user_id)
        if updated_tweet:
            await invalidate_user_cache(updated_tweet.author_id)
            logger.info(
                "unlike_cache_invalidated",
                user_id=user_id,
                author_id=updated_tweet.author_id,
            )
        else:
            logger.info("unlike_cache_invalidated_self", user_id=user_id)
    except Exception as e:
        logger.warning("unlike_cache_invalidation_error", error=str(e))

    # --- Формируем ответ ---
    if updated_tweet and updated_tweet.likes is not None:
        likes_list = [
            schemas.LikeInTweet(user_id=like.user_id, name=like.user.name)
            for like in updated_tweet.likes
        ]
        attachments_list = [
            f"/media/{Path(media.file_path).name}" for media in updated_tweet.media
        ]
        tweet_out = schemas.TweetOut(
            id=updated_tweet.id,
            content=updated_tweet.content,
            created_at=updated_tweet.created_at,
            author=schemas.UserInTweet.model_validate(updated_tweet.author),
            attachments=attachments_list,
            likes=likes_list,
        )
        return {"result": True, "tweet": tweet_out}

    return {"result": True}


# === ЛЕНТА ТВИТОВ ===


@router.get("/api/tweets", response_model=schemas.TweetListResponse)
async def get_tweet_feed(
    user: Annotated[User, Depends(get_current_user)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> Any:
    """
    Получить ленту твитов с кэшированием в Redis.

    Стратегия Cache-Aside с защитой от thundering herd (cache-lock).
    TTL кэша — 60 секунд.

    При попадании в кэш (HIT) данные возвращаются мгновенно.
    При промахе (MISS) — запрос к базе с последующей записью в кэш.
    """
    cache_key = CacheKeys.user_feed(user.id)

    # --- Внутренняя функция сериализации твитов в JSON ---
    def _serialize_tweets(tweets_orm: List[Any]) -> str:
        """Сериализовать список ORM-объектов Tweet в JSON-строку."""
        tweets_list = []
        for tweet in tweets_orm:
            likes_list = [
                schemas.LikeInTweet(user_id=like.user_id, name=like.user.name)
                for like in tweet.likes
            ]
            attachments_list = [
                f"/media/{Path(media.file_path).name}" for media in tweet.media
            ]
            tweet_out = schemas.TweetOut(
                id=tweet.id,
                content=tweet.content,
                created_at=tweet.created_at,
                author=schemas.UserInTweet.model_validate(tweet.author),
                attachments=attachments_list,
                likes=likes_list,
            )
            tweets_list.append(tweet_out)
        return schemas.TweetListResponse(tweets=tweets_list).model_dump_json()

    # --- Async-обёртка для get_with_lock ---
    async def _fetch_and_serialize() -> str:
        tweets_orm = await crud.get_feed(db, user.id)
        return _serialize_tweets(tweets_orm)

    # --- Попытка чтения из кэша ---
    try:
        r = await get_redis()
        cached_data = await r.get(cache_key)
        if cached_data:
            cache_hits_total.labels(endpoint="feed").inc()
            logger.info("cache_hit", user_id=user.id)
            return schemas.TweetListResponse.model_validate_json(cached_data)
    except Exception as e:
        logger.warning("cache_read_error", error=str(e))

    cache_misses_total.labels(endpoint="feed").inc()
    logger.info("cache_miss", user_id=user.id)

    # --- Чтение с защитой от thundering herd ---
    try:
        cached_data = await get_with_lock(cache_key, _fetch_and_serialize, FEED_TTL_SECONDS)
        if cached_data:
            return schemas.TweetListResponse.model_validate_json(cached_data)
    except Exception as e:
        logger.warning("cache_write_error", error=str(e))

    # --- Fallback: прямой запрос к базе ---
    tweets_orm = await crud.get_feed(db, user.id)
    return schemas.TweetListResponse.model_validate_json(_serialize_tweets(tweets_orm))
