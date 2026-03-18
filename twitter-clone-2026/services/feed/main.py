import asyncio
import logging

# Импортируем брокера и константу топика
from libs.kafka_conf import TOPIC_TWEETS, broker
from libs.schemas import TweetData

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# Подписываемся на топик
@broker.subscriber(TOPIC_TWEETS)
async def handle_tweet_created(event_data: TweetData) -> None:
    """
    Эта функция вызывается автоматически при получении сообщения.
    """
    logger.info(f"Received event for tweet {event_data.tweet_id}")
    # TODO: Логика обновления кеша


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
