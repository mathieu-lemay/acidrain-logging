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


@dataclass
class LogProcessorFactory:
    builder: Callable[[LogConfig], LogProcessor | None]

    def __call__(self, config: LogConfig) -> LogProcessor | None:
        return self.builder(config)


def timestamper_builder(config: LogConfig) -> LogProcessor:
    kwargs: dict[str, Any] = {}

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


def event_renamer_builder(config: LogConfig) -> LogProcessor | None:
    if config.output_format != OutputFormat.JSON:
        return None

    return event_renamer


EventRenamerFactory = LogProcessorFactory(builder=event_renamer_builder)


class LevelRenamer:
    """
    Rename level according to mapping.

    Levels that are not mapped are kept intact.
    """

    def __init__(self, rename_map: dict[str, str]) -> None:
        self._rename_map = rename_map

    def __call__(
        self, _logger: Logger, _method_name: str, event_dict: EventDict
    ) -> EventDict:
        level = event_dict["level"]
        event_dict["level"] = self._rename_map.get(level, level)
        return event_dict


def level_renamer_builder(config: LogConfig) -> LogProcessor | None:
    if not config.level_names:
        return None

    return LevelRenamer(config.level_names)


LevelRenamerFactory = LogProcessorFactory(builder=level_renamer_builder)


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


def otel_processor_builder(config: LogConfig) -> LogProcessor | None:
    if not config.trace_injection_enabled:
        return None

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
    LevelRenamerFactory,
    OtelInjectorFactory,
]
