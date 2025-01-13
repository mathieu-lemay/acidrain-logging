from collections.abc import Callable
from dataclasses import dataclass
from logging import Logger
from typing import Any

import structlog
from structlog.typing import EventDict

from acidrain_logging import LogConfig, OutputFormat

try:
    from opentelemetry import trace
except ImportError:  # pragma: no cover
    trace = None  # type: ignore[assignment]

LogProcessor = Callable[[Logger, str, EventDict], EventDict]


def null_processor(_: Logger, __: str, event_dict: EventDict) -> EventDict:
    return event_dict


@dataclass
class LogProcessorFactory:
    builder: Callable[[LogConfig], LogProcessor]

    def __call__(self, config: LogConfig) -> LogProcessor:
        return self.builder(config)


def timestamper_builder(config: LogConfig) -> LogProcessor:
    kwargs: dict[str, Any] = {}

    # TODO: Check if needed for DD logs
    if config.output_format == OutputFormat.JSON:
        kwargs["key"] = config.timestamp_key
    else:
        kwargs["utc"] = False

    return structlog.processors.TimeStamper(
        fmt=config.timestamp_format,
        **kwargs,
    )


TimeStamperFactory = LogProcessorFactory(builder=timestamper_builder)


# https://github.com/hynek/structlog/issues/35#issuecomment-591321744
def event_renamer(
    _logger: Logger, _method_name: str, event_dict: EventDict
) -> EventDict:
    """
    Rename `event` key to `message`.

    Log entries keep the text message in the `event` field, but message is usually more
    appropriate. This processor moves the value from one field to the other.
    See https://github.com/hynek/structlog/issues/35#issuecomment-591321744
    """
    event_dict["message"] = event_dict.pop("event")
    return event_dict


def event_renamer_builder(config: LogConfig) -> LogProcessor:
    if config.output_format != OutputFormat.JSON:
        return null_processor

    return event_renamer


EventRenamerFactory = LogProcessorFactory(builder=event_renamer_builder)


def drop_color_message_key(
    _logger: Logger, _method_name: str, event_dict: EventDict
) -> EventDict:
    """
    Remove the `color_message` key.

    Uvicorn logs the message a second time in the extra `color_message`, but we don't
    need it. This processor drops the key from the event dict if it exists.
    """
    event_dict.pop("color_message", None)
    return event_dict


def otel_processor(
    _logger: Logger,
    _method_name: str,
    event_dict: EventDict,
) -> EventDict:
    # TODO:
    # - Test without otel
    # - Test with otel but no tracing / invalid span
    # - Test with otel

    # To run with agent:
    #   https://opentelemetry.io/docs/zero-code/python/#configuring-the-agent
    span = trace and trace.get_current_span()
    if not span:
        return event_dict

    ctx = span.get_span_context()
    if not ctx.is_valid:
        return event_dict

    event_dict.update(
        {
            "otel.span_name": getattr(span, "name", None),
            "otel.span_id": trace.format_span_id(ctx.span_id),
            "otel.trace_id": trace.format_trace_id(ctx.trace_id),
        }
    )

    return event_dict


def otel_processor_builder(config: LogConfig) -> LogProcessor:
    if not config.otel.is_enabled():
        return null_processor

    return otel_processor


OtelInjectorFactory = LogProcessorFactory(builder=otel_processor_builder)


SHARED_PRE_PROCESSORS: list[LogProcessor | LogProcessorFactory] = [
    structlog.contextvars.merge_contextvars,
    structlog.stdlib.add_logger_name,
    structlog.stdlib.add_log_level,
    structlog.stdlib.PositionalArgumentsFormatter(),
    structlog.stdlib.ExtraAdder(),
    TimeStamperFactory,
    structlog.processors.format_exc_info,
    structlog.processors.StackInfoRenderer(),
    drop_color_message_key,
    EventRenamerFactory,
    OtelInjectorFactory,
]
