import os
from typing import TYPE_CHECKING, Optional

import redis.asyncio as redis

# Если мы в режиме проверки типов (mypy), импортируем с Generic
if TYPE_CHECKING:
    from redis.asyncio import Redis
else:
    # В рантайме используем обычный класс без поддержки [str]
    from redis.asyncio import Redis

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

# Для mypy это Redis[str], для Python это просто Redis
redis_client: Optional["Redis[str]"] = None


async def get_redis() -> "Redis[str]":
    global redis_client
    if redis_client is None:
        redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    return redis_client


async def close_redis() -> None:
    global redis_client
    if redis_client:
        await redis_client.close()
