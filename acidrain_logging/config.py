import logging
from enum import Enum
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import (
    BaseSettings,
    SettingsConfigDict,
)


class OutputFormat(str, Enum):
    __slots__ = ()

    CONSOLE = "console"
    JSON = "json"


class InvalidLogLevelError(Exception):
    def __init__(self, value: str) -> None:
        super().__init__(f"Invalid log level: {value}")


class DatadogSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="dd_")

    injection_enabled: bool = True
    env: str = ""
    service: str = ""
    version: str = ""

    def is_enabled(self) -> bool:
        return self.injection_enabled and any((self.env, self.service, self.version))


class LogConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="acidrain_log_", env_ignore_empty=True)

    level: str = "INFO"
    output_format: OutputFormat = OutputFormat.JSON
    color: bool = True
    logger_levels: Annotated[dict[str, str], Field(default_factory=dict)]
    timestamp_format: str = "iso"
    timestamp_key: str = "timestamp"
    level_names: dict[str, str] | None = None

    datadog: DatadogSettings = Field(default_factory=DatadogSettings)

    @field_validator("level")
    def validate_log_level(cls, value: str) -> str:
        sanitized = value.upper()

        # If there is a level with that name, getLevelName returns the corresponding int
        # value. If we don't get an int, the level doesn't exist.
        if sanitized not in logging.getLevelNamesMapping():
            raise InvalidLogLevelError(value)

        return sanitized
