import logging
from logging import StreamHandler
from typing import List, Optional, Union

import orjson
import structlog
from structlog.dev import ConsoleRenderer, plain_traceback
from structlog.processors import JSONRenderer
from structlog.typing import Processor

from acidrain_logging import LogConfig, OutputFormat
from acidrain_logging.processors import (
    SHARED_PRE_PROCESSORS,
    LogProcessor,
    LogProcessorFactory,
)


def configure_logger(log_config: Optional[LogConfig] = None) -> None:
    log_config = log_config or LogConfig()

    pre_processors = _get_pre_processors(
        log_config, pre_processors=SHARED_PRE_PROCESSORS
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            _get_log_renderer(log_config),
        ],
        foreign_pre_chain=pre_processors,
    )

    handler = StreamHandler()
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.addHandler(handler)
    root_logger.setLevel(log_config.level)

    for name, level in log_config.logger_levels.items():
        logger = logging.getLogger(name)
        logger.setLevel(level.upper())

    _override_uvicorn_loggers()

    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            *pre_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def _get_pre_processors(
    config: LogConfig, pre_processors: List[Union[LogProcessor, LogProcessorFactory]]
) -> List[LogProcessor]:
    processors = []

    for pre_processor in pre_processors:
        if isinstance(pre_processor, LogProcessorFactory):
            processor = pre_processor(config)
            if processor is not None:
                processors.append(processor)
        else:
            processors.append(pre_processor)

    return processors


def _get_log_renderer(config: LogConfig) -> Processor:
    if config.output_format == OutputFormat.CONSOLE:
        return ConsoleRenderer(colors=config.color, exception_formatter=plain_traceback)

    if config.output_format == OutputFormat.JSON:
        return JSONRenderer(serializer=lambda *a, **kw: orjson.dumps(*a, **kw).decode())

    # Shoud never happen, but ensures we don't forget to handle any new enum value
    raise ValueError(config.output_format)  # pragma: no cover


def _override_uvicorn_loggers() -> None:
    """
    Override uvicorn's logging with ours.

    First we disable the handlers for the two base uvicorn loggers and let the logs
    propagate to our handler.

    Then we disable uvicorn's access logs and disable propagation. Our
    LogRequestMiddleware will take care of that.
    """
    for log_name in ("uvicorn", "uvicorn.error"):
        logger = logging.getLogger(log_name)
        logger.handlers.clear()
        logger.propagate = True

    logger = logging.getLogger("uvicorn.access")
    logger.handlers.clear()
    logger.propagate = False
