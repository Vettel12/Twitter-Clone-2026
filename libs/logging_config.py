import logging
import sys

import structlog


def setup_logging() -> None:
    """
    Настраивает structlog для работы в контейнере.
    Выводит логи в stdout в формате JSON (для сборщика логов).
    """

    # Совместимость со стандартным logging (для uvicorn/sqlalchemy)
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            # В проде используем JSON
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Перехватываем стандартный logging (чтобы видеть логи Uvicorn/SQLAlchemy)
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.INFO,
    )
