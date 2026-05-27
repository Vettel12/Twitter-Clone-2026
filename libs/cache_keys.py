"""
Централизованное управление ключами Redis и логикой инвалидации кэша.

Модуль предоставляет:
    - Единообразную генерацию ключей кэша (класс ``CacheKeys``).
    - Атомарную пакетную инвалидацию с обработкой ошибок.
    - Механизм cache-lock для предотвращения thundering herd.
    - Версионирование кэша для борьбы с race conditions.
    - Набор Prometheus-метрик для мониторинга.
"""

import asyncio
from typing import Awaitable, Callable, List, Optional

import structlog
from prometheus_client import Counter, Histogram

from libs.redis_client import get_redis

logger = structlog.get_logger(__name__)

# === КОНСТАНТЫ ===

# Время жизни кэша ленты в секундах (10 секунд)
FEED_TTL_SECONDS = 10

# Время жизни блокировки кэша в секундах (защита от thundering herd)
CACHE_LOCK_TTL_SECONDS = 5

# === METRICS PROMETHEUS ===

cache_hits_total = Counter(
    "cache_hits_total",
    "Общее количество попаданий в кэш",
    ["endpoint"],
)

cache_misses_total = Counter(
    "cache_misses_total",
    "Общее количество промахов кэша",
    ["endpoint"],
)

cache_invalidations_total = Counter(
    "cache_invalidations_total",
    "Общее количество операций инвалидации кэша",
    ["operation"],
)

cache_invalidation_errors_total = Counter(
    "cache_invalidation_errors_total",
    "Общее количество ошибок при инвалидации кэша",
    ["operation"],
)

cache_errors_total = Counter(
    "cache_errors_total",
    "Общее количество ошибок операций с кэшем",
    ["operation"],
)

cache_lock_acquisitions_total = Counter(
    "cache_lock_acquisitions_total",
    "Общее количество попыток получения блокировки кэша",
    ["status"],  # "acquired" — получена, "failed" — не получена
)

cache_write_duration = Histogram(
    "cache_write_duration_seconds",
    "Время записи данных в кэш",
    ["endpoint"],
    buckets=(0.001, 0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0),
)


class CacheKeys:
    """Генерация ключей Redis для кэширования."""

    @staticmethod
    def user_feed(user_id: int) -> str:
        """
        Сформировать ключ кэша для ленты пользователя.

        Формат: ``feed:{user_id}``

        Args:
            user_id: Идентификатор пользователя.

        Returns:
            Строка ключа Redis.
        """
        return f"feed:{user_id}"

    @staticmethod
    def user_feeds(user_ids: List[int]) -> List[str]:
        """
        Сформировать список ключей для нескольких пользователей.

        Args:
            user_ids: Список идентификаторов пользователей.

        Returns:
            Список строк ключей Redis.
        """
        return [CacheKeys.user_feed(uid) for uid in user_ids]

    @staticmethod
    def lock(key: str) -> str:
        """
        Сформировать ключ блокировки для предотвращения thundering herd.

        Формат: ``{original_key}:lock``

        Args:
            key: Исходный ключ кэша.

        Returns:
            Строка ключа блокировки.
        """
        return f"{key}:lock"

    @staticmethod
    def version(key: str) -> str:
        """
        Сформировать ключ версии кэша для предотвращения race conditions.

        Формат: ``{original_key}:version``

        Args:
            key: Исходный ключ кэша.

        Returns:
            Строка ключа версии.
        """
        return f"{key}:version"


# === ИНВАЛИДАЦИЯ ===


async def invalidate_cache_keys(keys: List[str]) -> None:
    """
    Удалить список ключей из Redis одной атомарной операцией.

    При ошибке соединения логирует предупреждение и продолжает работу
    (кэш останется устаревшим до истечения TTL).

    Args:
        keys: Список ключей для удаления.
    """
    if not keys:
        return
    try:
        r = await get_redis()
        await r.ping()
        await r.delete(*keys)
        cache_invalidations_total.labels(operation="batch_delete").inc()
        logger.info("cache_invalidation_success", keys_count=len(keys))
    except ConnectionError:
        cache_invalidation_errors_total.labels(operation="batch_delete").inc()
        logger.warning("cache_invalidation_connection_lost")
    except Exception as e:
        cache_invalidation_errors_total.labels(operation="batch_delete").inc()
        logger.error("cache_invalidation_error", error=str(e))


async def invalidate_user_cache(user_id: int) -> None:
    """
    Инвалидировать кэш ленты конкретного пользователя.

    Args:
        user_id: Идентификатор пользователя.
    """
    await invalidate_cache_keys([CacheKeys.user_feed(user_id)])


async def invalidate_user_and_followers_cache(
    author_id: int,
    follower_ids: List[int],
) -> None:
    """
    Инвалидировать кэш ленты автора и всех его подписчиков.

    SQL (для получения подписчиков):
        SELECT follower_id FROM followers WHERE followed_id = :author_id;

    Args:
        author_id: Идентификатор автора.
        follower_ids: Список идентификаторов подписчиков.
    """
    keys = [CacheKeys.user_feed(author_id)]
    if follower_ids:
        keys.extend(CacheKeys.user_feeds(follower_ids))
    await invalidate_cache_keys(keys)


# === БЛОКИРОВКА КЭША (THUNDERING HERD) ===


async def acquire_cache_lock(cache_key: str) -> bool:
    """
    Попытаться получить блокировку кэша (SET NX с TTL).

    Блокировка предотвращает одновременные запросы к базе
    при промахе кэша (thundering herd).

    Args:
        cache_key: Ключ кэша, для которого нужна блокировка.

    Returns:
        True, если блокировка получена; False — если уже занята.
    """
    try:
        r = await get_redis()
        lock_key = CacheKeys.lock(cache_key)
        # SET NX — установить только если ключ не существует
        acquired = await r.set(lock_key, "1", ex=CACHE_LOCK_TTL_SECONDS, nx=True)
        if acquired:
            cache_lock_acquisitions_total.labels(status="acquired").inc()
        else:
            cache_lock_acquisitions_total.labels(status="failed").inc()
        return acquired is True
    except Exception as e:
        cache_errors_total.labels(operation="lock_acquire").inc()
        logger.warning("cache_lock_acquire_error", error=str(e))
        return False


async def release_cache_lock(cache_key: str) -> None:
    """
    Освободить блокировку кэша.

    Args:
        cache_key: Ключ кэша, чью блокировку нужно освободить.
    """
    try:
        r = await get_redis()
        lock_key = CacheKeys.lock(cache_key)
        await r.delete(lock_key)
    except Exception as e:
        cache_errors_total.labels(operation="lock_release").inc()
        logger.warning("cache_lock_release_error", error=str(e))


# === ВЕРСИОНИРОВАНИЕ КЭША ===


async def increment_cache_version(cache_key: str) -> int:
    """
    Увеличить счётчик версии кэша (INCR с TTL).

    Используется для обнаружения устаревших записей
    при race conditions между чтением и инвалидацией.

    Args:
        cache_key: Ключ кэша.

    Returns:
        Новое значение версии или 0 при ошибке.
    """
    try:
        r = await get_redis()
        version_key = CacheKeys.version(cache_key)
        new_version = await r.incr(version_key)
        await r.expire(version_key, CACHE_LOCK_TTL_SECONDS)
        return new_version
    except Exception as e:
        cache_errors_total.labels(operation="version_increment").inc()
        logger.warning("cache_version_increment_error", error=str(e))
        return 0


async def check_cache_version(cache_key: str) -> int:
    """
    Получить текущую версию кэша.

    Args:
        cache_key: Ключ кэша.

    Returns:
        Номер версии или 0, если версия не установлена.
    """
    try:
        r = await get_redis()
        version_key = CacheKeys.version(cache_key)
        version = await r.get(version_key)
        return int(version) if version else 0
    except Exception as e:
        cache_errors_total.labels(operation="version_check").inc()
        logger.warning("cache_version_check_error", error=str(e))
        return 0


# === ЧТЕНИЕ С ЗАЩИТОЙ ===


async def get_with_lock(
    cache_key: str,
    fallback_func: Callable[[], Awaitable[str]],
    ttl: int = FEED_TTL_SECONDS,
) -> Optional[str]:
    """
    Получить данные из кэша с fallback в базу и защитой от thundering herd.

    Алгоритм:
        1. Попытка чтения из кэша.
        2. При промахе — попытка получить блокировку.
        3. Если блокировка получена — вызов ``fallback_func()`` и запись в кэш.
        4. Если блокировка занята — короткое ожидание и повторная попытка чтения.

    Args:
        cache_key: Ключ кэша.
        fallback_func: Асинхронная функция для получения данных из базы.
        ttl: Время жизни кэша в секундах.

    Returns:
        Данные из кэша или результат ``fallback_func()``, либо None при ошибке.
    """
    r = await get_redis()

    # --- Попытка чтения из кэша ---
    cached_data = await r.get(cache_key)
    if cached_data:
        return cached_data

    # --- Cache MISS — попытка получить блокировку ---
    acquired = await acquire_cache_lock(cache_key)
    if not acquired:
        # Блокировка занята — ждём и повторяем
        await asyncio.sleep(0.1)
        cached_data = await r.get(cache_key)
        if cached_data:
            return cached_data
        logger.debug("cache_lock_not_acquired", key=cache_key)

    try:
        # --- Получаем данные из базы ---
        data: str = await fallback_func()

        # --- Сохраняем в кэш ---
        await r.set(cache_key, data, ex=ttl)
        logger.info("cache_set", key=cache_key, ttl=ttl)

        return data
    finally:
        # --- Освобождаем блокировку ---
        await release_cache_lock(cache_key)
