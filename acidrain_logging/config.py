import logging
from collections.abc import Mapping
from enum import Enum

from pydantic import Field, field_validator
from pydantic_settings import (
    BaseSettings,
    EnvSettingsSource,
    PydanticBaseSettingsSource,
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


# TODO: Just use env_ignore_empty=True when available
#       See: https://github.com/pydantic/pydantic-settings/pull/198
class AllowEmptyEnvSettingsSource(EnvSettingsSource):
    @classmethod
    def from_settings_source(
        cls, settings_source: PydanticBaseSettingsSource
    ) -> "AllowEmptyEnvSettingsSource":
        if not isinstance(
            settings_source, EnvSettingsSource
        ):  # pragma: no cover: type check
            msg = "Invalid settings source"
            raise TypeError(msg)

        return cls(
            settings_cls=settings_source.settings_cls,
            case_sensitive=settings_source.case_sensitive,
            env_prefix=settings_source.env_prefix,
            env_nested_delimiter=settings_source.env_nested_delimiter,
        )

    def _load_env_vars(self) -> Mapping[str, str | None]:
        return {k: v for k, v in super()._load_env_vars().items() if v != ""}


class LogConfig(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="acidrain_log_")

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],  # noqa: ARG003: Unused argument
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        env_settings = AllowEmptyEnvSettingsSource.from_settings_source(env_settings)
        return init_settings, env_settings, dotenv_settings, file_secret_settings

    level: str = "INFO"
    output_format: OutputFormat = OutputFormat.JSON
    color: bool = True
    logger_levels: dict[str, str] = Field(default={})
    timestamp_format: str = "iso"
    timestamp_key: str = "timestamp"

    datadog: DatadogSettings = Field(default_factory=DatadogSettings)

    @field_validator("level")
    def validate_log_level(cls, value: str) -> str:
        sanitized = value.upper()

        lvl = logging.getLevelName(sanitized)

        # If there is a level with that name, getLevelName returns the corresponding int
        # value. If we don't get an int, the level doesn't exist.
        # TODO: use `if sanitized not in logging.getLevelNamesMapping()` in py3.11
        if not isinstance(lvl, int):
            raise InvalidLogLevelError(value)

        return sanitized
