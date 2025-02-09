import random
from typing import Any

from polyfactory import Use
from polyfactory.factories.pydantic_factory import ModelFactory

from acidrain_logging import LogConfig
from acidrain_logging.config import TracingConfig

EmptyDictFactory: Use[Any, dict[Any, Any]] = Use(dict)


class LogConfigFactory(ModelFactory[LogConfig]):
    __model__ = LogConfig

    level = Use(
        lambda: random.choice(  # noqa: S311
            ("NOT_SET", "DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL")
        )
    )
    logger_levels = EmptyDictFactory
    # TODO: check if needed
    timestamp_key = "timestamp"
    timestamp_fmt = "iso"
    trace_injection_enabled = True


class TracingConfigFactory(ModelFactory[TracingConfig]):
    __model__ = TracingConfig
