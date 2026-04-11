from datetime import datetime
from typing import List

from pydantic import BaseModel, ConfigDict, Field

# --- Вспомогательные схемы (для вложенности) ---


class UserInTweet(BaseModel):
    """Схема автора твита или того, кто поставил лайк."""

    id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class LikeInTweet(BaseModel):
    """Схема лайка внутри твита (по ТЗ)."""

    user_id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


# --- Основные схемы ---


class TweetCreate(BaseModel):
    """
    Входящие данные при создании твита (POST /api/tweets).
    ✅ FIXED: Добавлены ограничения на размер
    """

    # Имена полей строго по ТЗ
    tweet_data: str = Field(
        ..., min_length=1, max_length=280, description="Tweet text (1-280 characters)"
    )
    tweet_media_ids: List[int] = Field(
        default_factory=list, max_length=4, description="List of media IDs (0-4 items)"
    )


class MediaUploadResponse(BaseModel):
    """Ответ при загрузке картинки (POST /api/medias)."""

    result: bool = True
    media_id: int


class TweetCreateResponse(BaseModel):
    """Ответ при создании твита."""

    result: bool = True
    tweet_id: int


class TweetOut(BaseModel):
    """
    Схема одного твита для выдачи в ленте (GET /api/tweets).
    Структура строго по ТЗ.
    """

    id: int
    content: str
    created_at: datetime
    author: UserInTweet
    attachments: List[str] = Field(default_factory=list)
    likes: List[LikeInTweet] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class TweetListResponse(BaseModel):
    """Обертка для списка твитов."""

    result: bool = True
    tweets: List[TweetOut]
