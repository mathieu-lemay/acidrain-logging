from collections.abc import Callable
from logging import Logger
from unittest.mock import Mock, patch

import pytest
from faker import Faker
from opentelemetry.trace import (
    Span,
    SpanContext,
    format_span_id,
    format_trace_id,
)
from structlog.processors import TimeStamper

from acidrain_logging import LogConfig, OutputFormat
from acidrain_logging.config import DatadogSettings
from acidrain_logging.processors import (
    LevelRenamer,
    LogProcessor,
    datadog_injector,
    datadog_injector_builder,
    drop_color_message_key,
    event_renamer,
    event_renamer_builder,
    level_renamer_builder,
    otel_processor,
    otel_processor_builder,
    timestamper_builder,
)
from acidrain_logging.testing.factories import DatadogSettingsFactory


@pytest.mark.parametrize(
    ("output_format", "expected_key", "expected_utc"),
    [
        (OutputFormat.CONSOLE, lambda _: "timestamp", False),
        (OutputFormat.JSON, lambda c: c.timestamp_key, True),
    ],
)
def test_timestamper_builder_creates_a_timestamper_from_config(
    faker: Faker,
    output_format: OutputFormat,
    expected_key: Callable[[LogConfig], str],
    expected_utc: bool,
) -> None:
    config = LogConfig(
        output_format=output_format,
        timestamp_format=faker.pystr(),
        timestamp_key=faker.pystr(),
    )

    processor = timestamper_builder(config)

    assert isinstance(processor, TimeStamper)
    assert processor.fmt == config.timestamp_format
    assert processor.key == expected_key(config)
    assert processor.utc is expected_utc


def test_event_renamer_renames_event_to_message(faker: Faker) -> None:
    logger = Mock(Logger)
    method_name = faker.pystr()
    msg = faker.pystr()

    event_dict = {"event": msg}

    assert event_renamer(logger, method_name, event_dict) == {"message": msg}


@pytest.mark.parametrize(
    ("output_format", "should_be_enabled"),
    [
        (OutputFormat.CONSOLE, False),
        (OutputFormat.JSON, True),
    ],
)
def test_event_renamer_builder_returns_the_right_processor(
    faker: Faker, output_format: OutputFormat, should_be_enabled: bool
) -> None:
    config = LogConfig(output_format=output_format)
    processor = event_renamer_builder(config)
    if not should_be_enabled:
        assert processor is None
        return

    logger = Mock(Logger)
    method_name = faker.pystr()
    msg = faker.pystr()

    event_dict = {"event": msg}

    assert processor is not None
    assert processor(logger, method_name, event_dict) == {"message": msg}


def test_level_renamer_renames_level(faker: Faker) -> None:
    logger = Mock(Logger)
    method_name = faker.pystr()

    info_rename = faker.pystr()
    warning_rename = faker.pystr()

    rename_map = {
        "info": info_rename,
        "warning": warning_rename,
        faker.pystr(): "info",  # Invalid level name, will be ignored
    }
    level_renamer = LevelRenamer(rename_map)

    assert level_renamer(logger, method_name, {"level": "info"}) == {
        "level": info_rename
    }
    assert level_renamer(logger, method_name, {"level": "warning"}) == {
        "level": warning_rename
    }
    assert level_renamer(logger, method_name, {"level": "unmapped-level"}) == {
        "level": "unmapped-level"
    }


@pytest.mark.parametrize(
    ("rename_map", "should_be_enabled"),
    [
        (None, False),
        ({}, False),
        ({"info": "ofni"}, True),
    ],
)
def test_level_renamer_builder_returns_the_right_processor(
    faker: Faker, rename_map: dict[str, str] | None, should_be_enabled: bool
) -> None:
    config = LogConfig(level_names=rename_map)
    processor = level_renamer_builder(config)
    if not should_be_enabled:
        assert processor is None
        return

    logger = Mock(Logger)
    method_name = faker.pystr()

    level_dict = {"level": "info"}

    assert processor is not None
    assert processor(logger, method_name, level_dict) == {"level": "ofni"}


def test_drop_color_message_key_drops_the_color_message(faker: Faker) -> None:
    logger = Mock(Logger)
    method_name = faker.pystr()

    key1, key2, value1, value2 = (faker.pystr() for _ in range(4))

    event_dict = {key1: value1, key2: value2, "color_message": faker.pystr()}

    assert drop_color_message_key(logger, method_name, event_dict) == {
        key1: value1,
        key2: value2,
    }


@patch("acidrain_logging.processors.tracer", new=None)
def test_datadog_injector_adds_the_datadog_values(faker: Faker) -> None:
    logger = Mock(Logger)
    method_name = faker.pystr()

    dd_settings: DatadogSettings = DatadogSettingsFactory.build()

    assert datadog_injector(logger, method_name, {}, datadog_settings=dd_settings) == {
        "dd.env": dd_settings.env,
        "dd.service": dd_settings.service,
        "dd.version": dd_settings.version,
    }


@patch("acidrain_logging.processors.tracer")
def test_datadog_injector_adds_the_span_values_if_there_is_one(
    mock_tracer: Mock, faker: Faker
) -> None:
    logger = Mock(Logger)
    method_name = faker.pystr()

    span_id = faker.pystr()
    trace_id = faker.pystr()
    mock_tracer.current_span.return_value = Mock(span_id=span_id, trace_id=trace_id)

    event_dict = datadog_injector(
        logger, method_name, {}, datadog_settings=DatadogSettingsFactory.build()
    )

    assert event_dict["dd.span_id"] == span_id
    assert event_dict["dd.trace_id"] == trace_id


@pytest.mark.parametrize(
    ("dd_enabled", "dd_env", "dd_service", "dd_version", "should_be_enabled"),
    [
        (False, "", "", "", False),
        (False, "some-env", "some-service", "some-version", False),
        (True, "", "", "", False),
        (True, "some-env", "", "", True),
        (True, "", "some-service", "", True),
        (True, "", "", "some-version", True),
        (True, "some-env", "some-service", "some-version", True),
    ],
)
@patch("acidrain_logging.processors.tracer", new=None)
def test_datadog_injector_builder_returns_the_right_processor(
    faker: Faker,
    dd_enabled: bool,
    dd_env: str,
    dd_service: str,
    dd_version: str,
    should_be_enabled: bool,
) -> None:
    config = LogConfig(
        datadog=DatadogSettings(
            injection_enabled=dd_enabled,
            env=dd_env,
            service=dd_service,
            version=dd_version,
        )
    )
    processor = datadog_injector_builder(config)

    if not should_be_enabled:
        assert processor is None
        return

    logger = Mock(Logger)
    method_name = faker.pystr()
    msg = faker.pystr()

    event_dict = {"event": msg}

    assert processor is not None
    event = processor(logger, method_name, event_dict)

    dd_keys = {"dd.env", "dd.service", "dd.version"}
    event_dd_keys = event.keys() & dd_keys

    assert event_dd_keys == dd_keys


@patch("acidrain_logging.processors.trace")
def test_otel_injector_adds_the_span_values_if_there_is_one(
    mock_trace: Mock, faker: Faker
) -> None:
    logger = Mock(Logger)
    method_name = faker.pystr()

    span_name = faker.pystr()
    span_id = faker.pyint()
    trace_id = faker.pyint()

    mock_span_ctx = Mock(
        spec=SpanContext, span_id=span_id, trace_id=trace_id, is_valid=True
    )

    mock_span = Mock(spec=Span)
    mock_span.name = span_name
    mock_span.get_span_context.return_value = mock_span_ctx

    mock_trace.get_current_span.return_value = mock_span
    mock_trace.format_span_id = format_span_id
    mock_trace.format_trace_id = format_trace_id

    event_dict = otel_processor(logger, method_name, {})

    assert event_dict["otel.span_name"] == span_name
    assert event_dict["otel.span_id"] == format_span_id(span_id)
    assert event_dict["otel.trace_id"] == format_trace_id(trace_id)


@patch("acidrain_logging.processors.trace", new=None)
def test_otel_injector_does_nothing_if_otel_is_not_installed(faker: Faker) -> None:
    logger = Mock(Logger)
    method_name = faker.pystr()

    event_dict = otel_processor(logger, method_name, {})

    assert not any(k for k in event_dict if k.startswith("otel."))


@patch("acidrain_logging.processors.trace")
@pytest.mark.parametrize(
    "span",
    [
        None,
        Mock(spec=Span, get_span_context=lambda: Mock(is_valid=False)),
    ],
)
def test_otel_injector_does_nothing_if_span_is_invalid(
    mock_trace: Mock,
    faker: Faker,
    span: Span,
) -> None:
    logger = Mock(Logger)
    method_name = faker.pystr()

    mock_trace.get_current_span.return_value = span

    event_dict = otel_processor(logger, method_name, {})

    assert not any(k for k in event_dict if k.startswith("otel."))


@pytest.mark.parametrize(
    ("trace_injection_enabled", "expected"),
    [
        (False, None),
        (True, otel_processor),
    ],
)
def test_otel_processor_builder_returns_the_right_processor(
    trace_injection_enabled: bool, expected: LogProcessor | None
) -> None:
    config = LogConfig(trace_injection_enabled=trace_injection_enabled)
    processor = otel_processor_builder(config)

    assert processor is expected
