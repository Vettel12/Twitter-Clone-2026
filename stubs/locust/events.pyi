from argparse import ArgumentParser
from typing import Any, Callable, Generic, TypeVar

T = TypeVar("T", bound=Callable[..., Any])

class EventHook(Generic[T]):
    def add_listener(self, func: T) -> T: ...
    def remove_listener(self, func: T) -> T: ...
    def fire(self, **kwargs: Any) -> None: ...

# Объявляем все хуки, которые вы используете
init_command_line_parser: EventHook[Callable[[ArgumentParser], None]]
request: EventHook[Callable[..., None]]
# Добавьте другие по необходимости:
# test_start: EventHook[Callable[..., None]]
# test_stop: EventHook[Callable[..., None]]
