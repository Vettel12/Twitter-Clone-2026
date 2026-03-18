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
    """Входящие данные при создании твита (POST /api/tweets)."""

    # Имена полей строго по ТЗ
    tweet_data: str = Field(..., description="Текст твита")
    tweet_media_ids: List[int] = Field(
        default_factory=list, description="Список ID загруженных картинок"
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
    content: str = Field(
        ..., serialization_alias="tweet_data", validation_alias="content"
    )
    created_at: datetime  # Добавляем дату
    author: UserInTweet
    attachments: List[str] = Field(default_factory=list)
    likes: List[LikeInTweet] = Field(default_factory=list)

    model_config = ConfigDict(from_attributes=True, populate_by_name=True)


class TweetListResponse(BaseModel):
    """Обертка для списка твитов."""

    result: bool = True
    tweets: List[TweetOut]
