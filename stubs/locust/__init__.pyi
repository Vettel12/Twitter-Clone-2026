# Экспортируем events, чтобы работало: from locust import events
# Декоратор task
from typing import Any, Callable, TypeVar, overload

from . import events as events

_F = TypeVar("_F", bound=Callable[..., Any])

@overload
def task(func: _F) -> _F: ...
@overload
def task(weight: int) -> Callable[[_F], _F]: ...

# Функция between
def between(min_wait: float, max_wait: float) -> Callable[[Any], float]: ...

# Базовые классы
class User:
    wait_time: Callable[[Any], float] | None
    def on_start(self) -> None: ...
    def on_stop(self) -> None: ...

class HttpUser(User): ...  # можно расширить при необходимости
