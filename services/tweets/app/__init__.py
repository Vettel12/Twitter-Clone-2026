# services/tweets/app/__init__.py

# 1. Импортируем роутер из файла маршрутов
# 2. Импортируем модели, чтобы они зарегистрировались в Base.metadata
# "noqa" нужен, чтобы линтер не ругался на неиспользуемый импорт
from . import models  # noqa: F401
from .api.routes import router

# Что мы хотим видеть снаружи при импорте: from services.tweets.app import router
__all__ = ["router"]
