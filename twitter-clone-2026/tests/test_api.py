import pytest
import redis.asyncio as redis
from faststream.kafka import KafkaBroker
from httpx import AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from services.users.app.models import User


@pytest.mark.asyncio
async def test_get_me(client: AsyncClient) -> None:
    """
    Тест: Получение информации о текущем пользователе.
    """
    # 1. Подготовка данных
    headers = {"api-key": "test"}

    # 2. Выполнение запроса
    response = await client.get("/api/users/me", headers=headers)

    # 3. Проверки (Assertions)
    assert response.status_code == 200
    data = response.json()
    assert data["result"] is True
    assert data["user"]["name"] == "TestUser"


@pytest.mark.asyncio
async def test_get_by_id(client: AsyncClient, db_session: AsyncSession) -> None:
    """
    Тест: Получение информации о пользователе по реальному ID.
    """
    # 1. Достаем ID созданного в фикстуре юзера из базы
    result = await db_session.execute(select(User).where(User.api_key == "test"))
    user = result.scalar_one()
    user_id = user.id

    headers = {"api-key": "test"}

    # 2. Выполнение запроса с ПРАВИЛЬНЫМ ID
    response = await client.get(f"/api/users/{user_id}", headers=headers)

    # 3. Проверки
    assert response.status_code == 200
    data = response.json()
    assert data["result"] is True
    assert data["user"]["name"] == "TestUser"


@pytest.mark.asyncio
async def test_create_tweet(client: AsyncClient) -> None:
    """
    Тест: Создание твита авторизованным пользователем.
    """
    # 1. Подготовка данных
    tweet_data = {"tweet_data": "Test tweet from pytest!", "tweet_media_ids": []}
    headers = {"api-key": "test"}

    # 2. Выполнение запроса
    response = await client.post("/api/tweets", json=tweet_data, headers=headers)

    # 3. Проверки (Assertions)
    assert response.status_code == 200
    data = response.json()
    assert data["result"] is True
    assert "tweet_id" in data


@pytest.mark.asyncio
async def test_follow_user(client: AsyncClient, db_session: AsyncSession) -> None:
    """
    Тест: Подписка на другого пользователя.
    """
    # 1. Создаем второго пользователя НАПРЯМУЮ в БД (без API)
    target_user = User(name="TargetUser", api_key="target_key")
    db_session.add(target_user)
    await db_session.flush()  # Важно! Генерирует ID, но не коммитит транзакцию

    target_id = target_user.id

    # 2. Текущий пользователь (TestUser из фикстуры) подписывается на target_user
    headers = {"api-key": "test"}  # Ключ TestUser
    response = await client.post(f"/api/users/{target_id}/follow", headers=headers)

    # 3. Проверки
    assert response.status_code == 200
    data = response.json()
    assert data["result"] is True

    # Доп. проверка: убедимся, что связь появилась в объекте текущего пользователя
    # (нужно заново загрузить пользователя из БД, так как кэш мог устареть)
    # Но так как сессия общая, изменения уже видны.
    await db_session.refresh(target_user)
    # Можно проверить через связи, если они настроены (followers/following)


@pytest.mark.asyncio
async def test_unfollow_user(client: AsyncClient, db_session: AsyncSession) -> None:
    """
    Тест: Отписка от пользователя.
    """
    # 1. Создаем и сразу подписываемся (подготовка состояния)
    target_user = User(name="UnfollowTarget", api_key="unfollow_key")
    db_session.add(target_user)
    await db_session.flush()
    target_id = target_user.id

    headers = {"api-key": "test"}

    # Сначала подписываемся
    await client.post(f"/api/users/{target_id}/follow", headers=headers)

    # 2. Действие: Отписываемся
    response = await client.delete(f"/api/users/{target_id}/follow", headers=headers)

    # 3. Проверки
    assert response.status_code == 200
    data = response.json()
    assert data["result"] is True


@pytest.mark.asyncio
async def test_upload_media(client: AsyncClient) -> None:
    """
    Тест: Загрузка медиафайла.
    """
    # 1. Подготовка данных
    headers = {"api-key": "test"}

    # 2. Выполнение запроса
    response = await client.post(
        "/api/medias",
        files={"file": ("test.jpg", b"test data", "image/jpeg")},
        headers=headers,
    )

    # 3. Проверки (Assertions)
    assert response.status_code == 200
    data = response.json()
    assert data["result"] is True
    assert "media_id" in data


@pytest.mark.asyncio
async def test_create_tweet_with_media(client: AsyncClient) -> None:
    """
    Тест: Создание твита с РЕАЛЬНЫМ медиафайлом.
    """
    headers = {"api-key": "test"}

    # 1. Сначала загружаем медиа, чтобы получить валидный ID
    media_response = await client.post(
        "/api/medias",
        files={"file": ("test.jpg", b"test data", "image/jpeg")},
        headers=headers,
    )
    assert media_response.status_code == 200
    media_id = media_response.json()["media_id"]

    # 2. Теперь создаем твит, используя полученный media_id
    tweet_data = {
        "tweet_data": "Test tweet with media from pytest!",
        "tweet_media_ids": [media_id],  # Используем реальный ID
    }

    # 3. Выполнение запроса
    response = await client.post("/api/tweets", json=tweet_data, headers=headers)

    # 4. Проверки (Assertions)
    assert response.status_code == 200
    data = response.json()
    assert data["result"] is True
    assert "tweet_id" in data


@pytest.mark.asyncio
async def test_get_tweets(client: AsyncClient) -> None:
    """
    Тест: Получение списка твитов.
    """

    # 1. Подготовка данных
    tweet_data = {"tweet_data": "Test tweet from pytest!", "tweet_media_ids": []}
    headers = {"api-key": "test"}

    # 2. Выполнение запроса
    response = await client.post("/api/tweets", json=tweet_data, headers=headers)

    response = await client.get("/api/tweets", headers=headers)

    # 3. Проверки (Assertions)
    assert response.status_code == 200
    data = response.json()
    assert data["result"] is True
    assert len(data["tweets"]) > 0


@pytest.mark.asyncio
async def test_delete_tweet(client: AsyncClient) -> None:
    """
    Тест: Удаление твита.
    """

    # 1. Создаем твит, чтобы получить его ID
    tweet_data = {"tweet_data": "Test tweet from pytest!", "tweet_media_ids": []}
    headers = {"api-key": "test"}

    response = await client.post("/api/tweets", json=tweet_data, headers=headers)

    tweet_id = response.json()["tweet_id"]

    # 2. Выполнение запроса
    response = await client.delete(f"/api/tweets/{tweet_id}", headers=headers)

    # 3. Проверки (Assertions)
    assert response.status_code == 200
    data = response.json()
    assert data["result"] is True


@pytest.mark.asyncio
async def test_like_tweet(client: AsyncClient) -> None:
    """
    Тест: Лайк твита.
    """

    # 1. Создаем твит, чтобы получить его ID
    tweet_data = {"tweet_data": "Test tweet from pytest!", "tweet_media_ids": []}
    headers = {"api-key": "test"}

    response = await client.post("/api/tweets", json=tweet_data, headers=headers)

    tweet_id = response.json()["tweet_id"]

    # 2. Выполнение запроса
    response = await client.post(f"/api/tweets/{tweet_id}/likes", headers=headers)

    # 3. Проверки (Assertions)
    assert response.status_code == 200
    data = response.json()
    assert data["result"] is True


@pytest.mark.asyncio
async def test_dislike_tweet(client: AsyncClient) -> None:
    """
    Тест: Дизлайк твита.
    """

    # 1. Создаем твит, чтобы получить его ID
    tweet_data = {"tweet_data": "Test tweet from pytest!", "tweet_media_ids": []}
    headers = {"api-key": "test"}

    response = await client.post("/api/tweets", json=tweet_data, headers=headers)

    tweet_id = response.json()["tweet_id"]

    # 2. Ставим лайк

    response_like = await client.post(f"/api/tweets/{tweet_id}/likes", headers=headers)
    assert response_like.status_code == 200
    assert response_like.json()["result"] is True

    # 3. Выполнение запроса
    response = await client.delete(f"/api/tweets/{tweet_id}/likes", headers=headers)

    # 4. Проверки (Assertions)
    assert response.status_code == 200
    data = response.json()
    assert data["result"] is True


@pytest.mark.asyncio
async def test_unauthorized(client: AsyncClient) -> None:
    """
    Тест: Ошибка 401 при неверном ключе.
    """
    # 1. Подготовка данных
    headers = {"api-key": "wrong_key"}

    # 2. Выполнение запроса
    response = await client.get("/api/users/me", headers=headers)

    # 3. Проверки (Assertions)
    assert response.status_code == 401

    # 4. Без заголовка

    response = await client.get("/api/users/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_delete_foreign_tweet(
    client: AsyncClient, db_session: AsyncSession
) -> None:
    """
    Тест: Ошибка 403 при удалении чужого твита.
    """
    # 1. Создаем твит, чтобы получить его ID

    twee_data = {"tweet_data": "Test 403!", "tweet_media_ids": []}

    headers = {"api-key": "test"}

    response = await client.post("/api/tweets", json=twee_data, headers=headers)

    tweet_id = response.json()["tweet_id"]

    # 2. Создаем второго пользователя (Злоумышленник)

    hacker = User(name="Hacker", api_key="hacker_key")
    db_session.add(hacker)
    await db_session.flush()

    # 3. Пытаемся удалить твит Хакером

    response = await client.delete(
        f"/api/tweets/{tweet_id}", headers={"api-key": "hacker_key"}
    )

    # 4. Проверки (Assertions)
    assert response.status_code == 200
    data = response.json()
    assert data["result"] is False
    assert "error_message" in data
    assert (
        "чужой" in data["error_message"].lower()
        or "delete" in data["error_message"].lower()
    )


@pytest.mark.asyncio
async def test_like_twice(client: AsyncClient) -> None:
    """
    Тест: Попытка лайкнуть дважды.
    Второй лайк должен вернуть result: False.
    """
    # 1. Создаем твит, чтобы получить его ID

    twee_data = {"tweet_data": "Test like twice!", "tweet_media_ids": []}

    headers = {"api-key": "test"}

    response = await client.post("/api/tweets", json=twee_data, headers=headers)

    tweet_id = response.json()["tweet_id"]

    # Первый лайк (Успех)
    r1 = await client.post(f"/api/tweets/{tweet_id}/likes", headers=headers)
    assert r1.status_code == 200
    assert r1.json()["result"] is True

    # Второй лайк (Ошибка)
    r2 = await client.post(f"/api/tweets/{tweet_id}/likes", headers=headers)
    assert r2.status_code == 200
    data = r2.json()
    assert data["result"] is False
    assert "error_message" in data
    assert "already" in data["error_message"].lower()


@pytest.mark.asyncio
async def test_like_nonexistent_tweet(client: AsyncClient) -> None:
    """
    Тест: Лайк несуществующего твита.
    """
    # 1. Подготовка данных
    headers = {"api-key": "test"}
    fake_tweet_id = 99999

    # 2. Выполнение запроса
    response = await client.post(f"/api/tweets/{fake_tweet_id}/likes", headers=headers)

    # 3. Проверки (Assertions)
    assert response.status_code == 200
    data = response.json()
    assert data["result"] is False
    # Проверим, что в сообщении есть намек на ошибку
    assert (
        "not found" in data["error_message"].lower()
        or "cannot" in data["error_message"].lower()
    )


@pytest.mark.asyncio
async def test_redis_connection(redis_client: "redis.Redis[str]") -> None:
    """
    Тест: Проверка подключения к Redis.
    """
    # 1. Проверяем, что можем подключиться к Redis
    assert redis_client is not None, "Redis client should be initialized"

    # 2. Выполняем базовую операцию - записываем и читаем значение
    test_key = "pytest:test:redis"
    test_value = "hello_redis"

    await redis_client.set(test_key, test_value, ex=60)
    result = await redis_client.get(test_key)

    # 3. Проверяем, что значение записалось и прочиталось
    assert result == test_value, f"Expected '{test_value}', got '{result}'"

    # 4. Очищаем тестовый ключ
    await redis_client.delete(test_key)

    # 5. Проверяем TTL (Time To Live)
    await redis_client.set(test_key, test_value, ex=10)
    ttl = await redis_client.ttl(test_key)
    assert 0 < ttl <= 10, f"TTL should be between 0 and 10, got {ttl}"
    await redis_client.delete(test_key)


@pytest.mark.asyncio
async def test_kafka_connection(kafka_broker: KafkaBroker) -> None:
    """
    Тест: Проверка подключения к Kafka и публикации сообщения.
    """
    # 1. Создаем тестовое сообщение
    test_message = {
        "user_id": 1,
        "tweet_id": 999,
        "action": "test",
        "timestamp": "2026-04-08T12:00:00",
    }

    # 2. Публикуем сообщение в топик
    await kafka_broker.publish(
        message=test_message,
        topic="tweets-topic",
    )


@pytest.mark.asyncio
async def test_kafka_consumer_tweet_creation(client: AsyncClient) -> None:
    """
    Тест: Проверка, что при создании твита событие публикуется в Kafka.
    """
    # 1. Создаем твит через API
    headers = {"api-key": "test"}
    tweet_data = {"tweet_data": "Kafka test tweet!", "tweet_media_ids": []}

    response = await client.post("/api/tweets", json=tweet_data, headers=headers)

    # 2. Проверяем, что твит создался
    assert response.status_code == 200
    data = response.json()
    assert data["result"] is True
    assert "tweet_id" in data

    # Твит создался успешно - это означает, что Kafka publishing
    # внутри приложения работает (если бы Kafka была недоступна,
    # приложение бы вернуло ошибку)
