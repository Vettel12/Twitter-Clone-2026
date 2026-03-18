import os

from faststream.kafka import KafkaBroker

# Адрес Kafka из переменных окружения или дефолт
KAFKA_SERVER = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "kafka:29092")

# Создаем экземпляр брокера
# Он будет общаться с Kafka
broker = KafkaBroker(KAFKA_SERVER)

# Имена топиков
TOPIC_TWEETS = "tweets-topic"
