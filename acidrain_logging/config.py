import logging
from enum import Enum
from typing import Any, Dict

from pydantic import BaseSettings, Field, validator


class OutputFormat(str, Enum):
    __slots__ = ()

    CONSOLE = "console"
    JSON = "json"


class InvalidLogLevelError(Exception):
    def __init__(self, value: str) -> None:
        super().__init__(f"Invalid log level: {value}")


class DatadogSettings(BaseSettings):
    class Config:
        env_prefix = "dd_"

    env: str = ""
    service: str = ""
    version: str = ""


class LogConfig(BaseSettings):
    class Config(BaseSettings.Config):
        env_prefix = "acidrain_log_"

        # ANN401: Dynamically typed expressions (typing.Any) are disallowed in
        # `parse_env_var`
        # Using the same typing as the parent class
        @classmethod
        def parse_env_var(cls, field_name: str, raw_val: str) -> Any:  # noqa: ANN401
            if field_name == "logger_levels" and raw_val == "":
                return {}

            return cls.json_loads(raw_val)

    level: str = "INFO"
    output_format: OutputFormat = OutputFormat.JSON
    color: bool = True
    logger_levels: Dict[str, str] = Field(default={})
    timestamp_format: str = "iso"
    timestamp_key: str = "timestamp"

    datadog: DatadogSettings = Field(default_factory=DatadogSettings)

    @validator("level")
    def validate_log_level(cls, value: str) -> str:
        sanitized = value.upper()

        lvl = logging.getLevelName(sanitized)

        # If there is a level with that name, getLevelName returns the corresponding int
        # value. If we don't get an int, the level doesn't exist.
        # TODO: use `if sanitized not in logging.getLevelNamesMapping()` in py3.11
        if not isinstance(lvl, int):
            raise InvalidLogLevelError(value)

        return sanitized
