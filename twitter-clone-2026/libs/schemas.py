from datetime import UTC, datetime
from typing import List
from uuid import uuid4

from pydantic import BaseModel, Field


class TweetCreatedEvent(BaseModel):
    """Событие: Твит создан."""

    event_id: str = Field(default_factory=lambda: str(uuid4()))
    event_time: datetime = Field(default_factory=lambda: datetime.now(UTC))
    producer: str = "tweets-service"
    data: "TweetData"


class TweetData(BaseModel):
    tweet_id: int
    author_id: int
    content: str
    media_ids: List[int] = []


# Обновляем forward references (Pydantic v2)
TweetCreatedEvent.model_rebuild()
