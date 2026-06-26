import pytest
from _pytest.monkeypatch import MonkeyPatch
from pydantic import ValidationError

from acidrain_logging import LogConfig, OutputFormat
from acidrain_logging.config import InvalidLogLevelError, OtelConfig, TraceExporter


def test_log_config(monkeypatch: MonkeyPatch) -> None:
    with monkeypatch.context() as ctx:
        ctx.setenv("ACIDRAIN_LOG_LEVEL", "DEBUG")
        ctx.setenv("ACIDRAIN_LOG_OUTPUT_FORMAT", "console")
        ctx.setenv("ACIDRAIN_LOG_COLOR", "0")
        ctx.setenv("ACIDRAIN_LOG_LOGGER_LEVELS", '{"foo.bar": "error"}')
        ctx.setenv("ACIDRAIN_LOG_TIMESTAMP_FORMAT", "%m/%d/%Y")  # derp format
        ctx.setenv("ACIDRAIN_LOG_TIMESTAMP_KEY", "asctime")
        ctx.setenv("ACIDRAIN_LOG_TRACE_INJECTION_ENABLED", "false")

        config = LogConfig()

    assert config.level == "DEBUG"
    assert config.output_format == OutputFormat.CONSOLE
    assert config.color is False
    assert config.logger_levels == {"foo.bar": "error"}
    assert config.timestamp_format == "%m/%d/%Y"
    assert config.timestamp_key == "asctime"
    assert config.trace_injection_enabled is False


def test_log_config_default_values() -> None:
    config = LogConfig()

    assert config.level == "INFO"
    assert config.output_format == OutputFormat.JSON
    assert config.color is True
    assert config.logger_levels == {}
    assert config.timestamp_format == "iso"
    assert config.timestamp_key == "timestamp"
    assert config.trace_injection_enabled is True


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


def test_log_config_logger_levels_can_be_an_empty_string(
    monkeypatch: MonkeyPatch,
) -> None:
    """Ensure an empty string is handled like a null value."""
    with monkeypatch.context() as ctx:
        ctx.setenv("ACIDRAIN_LOG_LOGGER_LEVELS", "")

        config = LogConfig()

    assert config.logger_levels == {}


def test_otel_config(monkeypatch: MonkeyPatch) -> None:
    with monkeypatch.context() as ctx:
        ctx.setenv("ACIDRAIN_OTEL_TRACE_EXPORTER", "console")

        config = OtelConfig()

    assert config.trace_exporter == TraceExporter.CONSOLE


def test_tracing_config_default_values() -> None:
    config = OtelConfig()

    assert config.trace_exporter == TraceExporter.OTLP


@pytest.mark.parametrize(
    ("exporter", "is_valid"),
    [
        *((exp.value, True) for exp in TraceExporter),
        ("CoNsOlE", False),  # Case matters
        ("invalid", False),
    ],
)
def test_otel_config_validate_exporter(
    *, monkeypatch: MonkeyPatch, exporter: str, is_valid: bool
) -> None:
    with monkeypatch.context() as ctx:
        ctx.setenv("ACIDRAIN_OTEL_TRACE_EXPORTER", exporter)

        if is_valid:
            config = OtelConfig()
            assert config.trace_exporter == TraceExporter(exporter)
        else:
            with pytest.raises(ValidationError, match="trace_exporter"):
                _ = OtelConfig()
