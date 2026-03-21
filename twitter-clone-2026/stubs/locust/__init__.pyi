from typing import Any, Callable, TypeVar, Union

# Определяем переменную для функций-задач, чтобы типизация была точной
F = TypeVar("F", bound=Callable[..., Any])

def between(min_wait: float, max_wait: float) -> Callable[[Any], float]: ...

# [Any, Any], чтобы Callable не был «голым»
def task(weight: int = ...) -> Callable[[F], F]: ...

class HttpUser:
    # Union описывает возможные варианты wait_time в Locust
    wait_time: Union[float, tuple[float, float], Callable[[Any], float]]
    client: Any
    def on_start(self) -> None: ...
    def on_stop(self) -> None: ...
