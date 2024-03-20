from collections.abc import Callable
from copy import deepcopy
from logging import Logger
from unittest.mock import Mock, patch

import pytest
from faker import Faker
from structlog.processors import TimeStamper

from acidrain_logging import LogConfig, OutputFormat
from acidrain_logging.config import DatadogSettings
from acidrain_logging.processors import (
    datadog_injector,
    datadog_injector_builder,
    drop_color_message_key,
    event_renamer,
    event_renamer_builder,
    null_processor,
    timestamper_builder,
)
from acidrain_logging.testing.factories import DatadogSettingsFactory


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
    ("output_format", "expected_key"),
    [
        (OutputFormat.CONSOLE, lambda _: "timestamp"),
        (OutputFormat.JSON, lambda c: c.timestamp_key),
    ],
)
def test_timestamper_builder_creates_a_timestamper_from_config(
    faker: Faker,
    output_format: OutputFormat,
    expected_key: Callable[[LogConfig], str],
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
    assert processor.utc is True


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
def test_datadog_injector_builder_returns_the_right_processor(  # noqa: PLR0913: too many args
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

    logger = Mock(Logger)
    method_name = faker.pystr()
    msg = faker.pystr()

    event_dict = {"event": msg}

    event = processor(logger, method_name, event_dict)

    dd_keys = {"dd.env", "dd.service", "dd.version"}
    event_dd_keys = event.keys() & dd_keys

    if should_be_enabled:
        assert event_dd_keys == dd_keys
    else:
        assert event_dd_keys == set()
