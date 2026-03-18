from datetime import datetime
from typing import List

from pydantic import BaseModel


class TweetCreatedEvent(BaseModel):
    """Событие: Твит создан."""

    event_id: str
    event_time: datetime
    producer: str = "tweets-service"
    data: "TweetData"


class TweetData(BaseModel):
    tweet_id: int
    author_id: int
    content: str
    media_ids: List[int] = []


# Обновляем forward references (Pydantic v2)
TweetCreatedEvent.model_rebuild()
