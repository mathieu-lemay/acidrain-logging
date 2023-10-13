import random
from typing import Any

from polyfactory import Use
from polyfactory.factories.pydantic_factory import ModelFactory

from acidrain_logging import LogConfig
from acidrain_logging.config import DatadogSettings

EmptyDictFactory: Use[Any, dict[Any, Any]] = Use(lambda: {})


class DatadogSettingsFactory(ModelFactory[DatadogSettings]):
    __model__ = DatadogSettings


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
    datadog = DatadogSettingsFactory
