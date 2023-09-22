import pytest
from _pytest.monkeypatch import MonkeyPatch

from acidrain_logging import LogConfig, OutputFormat
from acidrain_logging.config import InvalidLogLevelError


def test_log_config(monkeypatch: MonkeyPatch) -> None:
    with monkeypatch.context() as ctx:
        ctx.setenv("ACIDRAIN_LOG_LEVEL", "DEBUG")
        ctx.setenv("ACIDRAIN_LOG_OUTPUT_FORMAT", "console")
        ctx.setenv("ACIDRAIN_LOG_COLOR", "0")
        ctx.setenv("ACIDRAIN_LOG_LOGGER_LEVELS", '{"foo.bar": "error"}')
        ctx.setenv("ACIDRAIN_LOG_TIMESTAMP_FORMAT", "%m/%d/%Y")  # derp format
        ctx.setenv("ACIDRAIN_LOG_TIMESTAMP_KEY", "asctime")

        config = LogConfig()

    assert config.level == "DEBUG"
    assert config.output_format == OutputFormat.CONSOLE
    assert config.color is False
    assert config.logger_levels == {"foo.bar": "error"}
    assert config.timestamp_format == "%m/%d/%Y"
    assert config.timestamp_key == "asctime"


def test_log_config_default_values() -> None:
    config = LogConfig()

    assert config.level == "INFO"
    assert config.output_format == OutputFormat.JSON
    assert config.color is True
    assert config.logger_levels == {}
    assert config.timestamp_format == "iso"
    assert config.timestamp_key == "timestamp"


@pytest.mark.parametrize(
    ("level", "is_valid"),
    [
        *(
            (lvl, True)
            for lvl in (
                "NOTSET",
                "DEBUG",
                "INFO",
                "WARN",
                "WARNING",
                "ERROR",
                "FATAL",
                "CRITICAL",
            )
        ),
        ("CrItIcAl", True),  # Case doesn't matter
        ("invalid", False),
    ],
)
def test_log_config_validate_log_level(*, level: str, is_valid: bool) -> None:
    if is_valid:
        config = LogConfig(level=level)
        assert config.level == level.upper()
    else:
        with pytest.raises(InvalidLogLevelError, match=f"Invalid log level: {level}"):
            LogConfig(level=level)