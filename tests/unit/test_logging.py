import json
import logging
from collections.abc import Generator
from datetime import UTC, datetime

import pytest
import structlog
from _pytest.capture import CaptureFixture
from _pytest.logging import LogCaptureFixture
from faker import Faker
from structlog.contextvars import bound_contextvars

from acidrain_logging import LogConfig, OutputFormat, configure_logger


@pytest.fixture()
def _log_restore() -> Generator[None, None, None]:
    logger = logging.getLogger()
    handlers = [*logger.handlers]

    yield

    # reset handlers to initially discovered
    if handlers or logger.handlers:
        logger.handlers = handlers


@pytest.fixture()
def caplog(caplog: LogCaptureFixture, _log_restore: None) -> LogCaptureFixture:
    return caplog


@pytest.mark.usefixtures("freezer")
def test_configure_logger_initializes_the_logger_with_the_default_config(
    caplog: LogCaptureFixture, faker: Faker
) -> None:
    """Logger should be initialized and contain basic fields."""
    configure_logger()

    log_name = faker.pystr()
    msg_debug = faker.pystr()
    msg_info = faker.pystr()

    structlog.get_logger(log_name).debug(msg_debug)
    structlog.get_logger(log_name).info(msg_info)

    assert len(caplog.records) == 1

    log_values = caplog.records[0].msg
    assert isinstance(log_values, dict)  # type check
    assert (
        log_values.items()
        >= {
            "logger": log_name,
            "level": "info",
            "timestamp": datetime.now(tz=UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ"),
            "message": msg_info,
        }.items()
    )


def test_configure_logger_initializes_the_logger_with_the_specified_level(
    caplog: LogCaptureFixture, faker: Faker
) -> None:
    log_config = LogConfig(level="DEBUG")
    configure_logger(log_config)

    msg = faker.pystr()

    structlog.get_logger().debug(msg)

    assert "DEBUG" in caplog.text
    assert msg in caplog.text


def test_configure_logger_initializes_the_logger_with_level_overrides(
    caplog: LogCaptureFixture, faker: Faker
) -> None:
    other_logger_name = faker.pystr()
    log_config = LogConfig(level="DEBUG", logger_levels={other_logger_name: "ERROR"})
    configure_logger(log_config)

    msg = faker.pystr()

    structlog.get_logger().debug(msg)

    # Ensure our base level is still valid
    assert "DEBUG" in caplog.text
    assert msg in caplog.text

    other_msg_info = faker.pystr()
    other_msg_error = faker.pystr()

    structlog.get_logger(other_logger_name).info(other_msg_info)
    structlog.get_logger(other_logger_name).error(other_msg_error)

    assert other_msg_info not in caplog.text
    assert other_msg_error in caplog.text


def test_context_values_are_present_in_the_log(
    caplog: LogCaptureFixture, faker: Faker
) -> None:
    configure_logger()

    msg = faker.pystr()

    context = {faker.pystr(): faker.pystr()}
    extra_value = {faker.pystr(): faker.pystr()}

    with bound_contextvars(context=context):
        structlog.get_logger().info(msg, extra_value=extra_value)

    log_values = caplog.records[0].msg
    assert isinstance(log_values, dict)  # type check
    assert log_values["context"] == context
    assert log_values["extra_value"] == extra_value


def test_positional_arguments_are_formatted_properly(
    caplog: LogCaptureFixture, faker: Faker
) -> None:
    configure_logger()

    some_int = faker.pyint()
    some_str = faker.pystr()
    structlog.get_logger().info("integer=%d, string='%s'", some_int, some_str)

    assert f"integer={some_int}, string='{some_str}'" in caplog.text


def test_extra_values_are_added_to_the_event_dict(
    capsys: CaptureFixture[str], faker: Faker
) -> None:
    # Force output format to JSON for easier parsing
    configure_logger(LogConfig(output_format=OutputFormat.JSON))

    key = faker.pystr()
    val = faker.pystr()

    # `extra` is specific to the standard logger.
    log = logging.getLogger(__name__)
    log.info("with extra", extra={key: val})

    # Using capsys to get the fully rendered log and assert on that
    log_record = json.loads(capsys.readouterr().err)
    assert log_record[key] == val


def test_exc_info_is_added_to_the_log_if_requested(
    caplog: LogCaptureFixture, faker: Faker
) -> None:
    configure_logger()

    exc_msg = faker.pystr()
    try:
        # Dummy try catch on purpose to generate a stack trace for the logger
        raise ValueError(exc_msg)  # noqa: TRY301
    except ValueError:
        structlog.get_logger().info("message with exc", exc_info=True)

    log_values = caplog.records[0].msg
    assert isinstance(log_values, dict)  # type check

    assert f"ValueError: {exc_msg}" in log_values["exception"]


def test_stack_info_is_added_to_the_log_if_requested(caplog: LogCaptureFixture) -> None:
    configure_logger()

    structlog.get_logger().info("message with stack", stack_info=True)

    log_values = caplog.records[0].msg
    assert isinstance(log_values, dict)  # type check

    # The `stack_info` key should have been removed
    assert "stack_info" not in log_values

    # The stack should be present
    assert f'File "{__file__}"' in log_values["stack"]


def test_the_color_message_key_is_dropped_if_present(caplog: LogCaptureFixture) -> None:
    configure_logger()

    structlog.get_logger().info("message", color_message="message with color")

    log_values = caplog.records[0].msg
    assert isinstance(log_values, dict)  # type check
    assert "color_message" not in log_values


@pytest.mark.parametrize(
    ("output_format", "key"),
    [
        (OutputFormat.CONSOLE, "event"),
        (OutputFormat.JSON, "message"),
    ],
)
def test_the_event_key_is_renamed_to_message_if_json(
    caplog: LogCaptureFixture, faker: Faker, output_format: OutputFormat, key: str
) -> None:
    configure_logger(LogConfig(output_format=output_format))

    msg = faker.pystr()

    structlog.get_logger().info(msg)

    log_values = caplog.records[0].msg
    assert isinstance(log_values, dict)  # type check
    assert log_values[key] == msg
