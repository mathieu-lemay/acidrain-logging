from collections.abc import Callable
from copy import deepcopy
from logging import Logger
from unittest.mock import Mock, patch

import pytest
from faker import Faker
from opentelemetry.trace import Span, SpanContext, format_span_id, format_trace_id
from structlog.processors import TimeStamper

from acidrain_logging import LogConfig, OutputFormat
from acidrain_logging.config import OtelSettings
from acidrain_logging.processors import (
    LogProcessor,
    drop_color_message_key,
    event_renamer,
    event_renamer_builder,
    null_processor,
    otel_processor,
    otel_processor_builder,
    timestamper_builder,
)


def test_null_processor_returns_the_event_dict_untouched(faker: Faker) -> None:
    logger = Mock(Logger)
    method_name = faker.pystr()

    key1, key2, value1, value2 = (faker.pystr() for _ in range(4))

    event_dict = {
        key1: value1,
        key2: value2,
    }

    expected = deepcopy(event_dict)

    assert null_processor(logger, method_name, event_dict) == expected


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
    ("output_format", "expected_key"),
    [
        (OutputFormat.CONSOLE, "event"),
        (OutputFormat.JSON, "message"),
    ],
)
def test_event_renamer_builder_returns_the_right_processor(
    faker: Faker, output_format: OutputFormat, expected_key: str
) -> None:
    config = LogConfig(output_format=output_format)
    processor = event_renamer_builder(config)

    logger = Mock(Logger)
    method_name = faker.pystr()
    msg = faker.pystr()

    event_dict = {"event": msg}

    assert processor(logger, method_name, event_dict) == {expected_key: msg}


def test_drop_color_message_key_drops_the_color_message(faker: Faker) -> None:
    logger = Mock(Logger)
    method_name = faker.pystr()

    key1, key2, value1, value2 = (faker.pystr() for _ in range(4))

    event_dict = {key1: value1, key2: value2, "color_message": faker.pystr()}

    assert drop_color_message_key(logger, method_name, event_dict) == {
        key1: value1,
        key2: value2,
    }


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


@pytest.mark.parametrize(
    ("otel_enabled", "expected"),
    [
        (False, null_processor),
        (True, otel_processor),
    ],
)
def test_otel_processor_builder_returns_the_right_processor(
    otel_enabled: bool, expected: LogProcessor
) -> None:
    config = LogConfig(otel=OtelSettings(injection_enabled=otel_enabled))
    processor = otel_processor_builder(config)

    assert processor is expected
