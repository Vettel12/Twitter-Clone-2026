import redis.asyncio as redis
import os
from typing import Optional

# Адрес Redis. В Docker это будет сервис 'redis'
REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

redis_client: Optional[redis.Redis] = None

async def get_redis() -> redis.Redis:
    global redis_client
    if redis_client is None:
        redis_client = redis.from_url(REDIS_URL, decode_responses=True)
    return redis_client

async def close_redis():
    global redis_client
    if redis_client:
        await redis_client.close()
