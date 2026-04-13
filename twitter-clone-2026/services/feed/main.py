import asyncio

import structlog

# Импортируем брокера и константу топика
from libs.kafka_conf import TOPIC_TWEETS, broker
from libs.redis_client import get_redis
from libs.schemas import TweetCreatedEvent

logger = structlog.get_logger(__name__)

# Ключ Redis для deduplication обработанных событий
PROCESSED_EVENTS_KEY = "processed_events"
PROCESSED_EVENTS_TTL = 3600  # хранить 1 час


@broker.subscriber(TOPIC_TWEETS)
async def handle_tweet_created(event: TweetCreatedEvent) -> None:
    """
    Обработчик событий создания твита.
    Реализует deduplication по event_id для предотвращения повторной обработки.
    """
    logger.info(
        f"Received event for tweet {event.data.tweet_id} "
        f"(event_id={event.event_id})"
    )

    # === DEDUPLICATION CHECK ===
    try:
        r = await get_redis()
        event_key = f"tweet:{event.data.tweet_id}"

        # Проверяем, не обрабатывали ли уже это событие
        if await r.sismember(PROCESSED_EVENTS_KEY, event_key):
            logger.info(
                f"Event {event.event_id} for tweet {event.data.tweet_id} "
                f"already processed, skipping"
            )
            return

        # === ЛОГИКА ОБНОВЛЕНИЯ КЭША ===
        # Инвалидируем кэш автора
        await r.delete(f"feed:{event.data.author_id}")
        logger.info(f"Cache invalidated for author {event.data.author_id}")

        # Отмечаем событие как обработанное
        await r.sadd(PROCESSED_EVENTS_KEY, event_key)
        await r.expire(PROCESSED_EVENTS_KEY, PROCESSED_EVENTS_TTL)
        logger.info(
            f"Tweet {event.data.tweet_id} marked as processed "
            f"(event_id={event.event_id})"
        )

    except Exception as e:
        logger.error(
            f"Error processing event {event.event_id} "
            f"for tweet {event.data.tweet_id}: {e}"
        )
        # Не ack'им сообщение — Kafka сделает retry
        raise


async def main() -> None:
    logger.info("Feed Service started.")
    await broker.start()
    try:
        await asyncio.Future()
    finally:
        # ИСПРАВЛЕНО: close() -> stop()
        await broker.stop()


if __name__ == "__main__":
    asyncio.run(main())
