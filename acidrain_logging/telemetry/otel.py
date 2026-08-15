import os

import structlog
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SpanExporter,
)
from opentelemetry.trace import SpanContext, get_current_span, set_tracer_provider
from structlog.stdlib import BoundLogger

from acidrain_logging.config import OtelConfig, SpanExporterType

log: BoundLogger = structlog.get_logger()


def configure_telemetry(telemetry_config: OtelConfig | None = None) -> None:
    telemetry_config = telemetry_config or OtelConfig()

    exporter: SpanExporter | None = None
    match telemetry_config.span_exporter:
        case SpanExporterType.OTLP:
            exporter = OTLPSpanExporter()
        case SpanExporterType.CONSOLE:
            exporter = ConsoleSpanExporter(
                formatter=lambda s: s.to_json(indent=None) + os.linesep
            )
        case SpanExporterType.NONE:
            pass

    tp = TracerProvider()

    if exporter:
        tp.add_span_processor(BatchSpanProcessor(exporter))

    set_tracer_provider(tp)


def get_current_span_context() -> "SpanContext | None":
    span = get_current_span()
    ctx = span.get_span_context()
    if not ctx.is_valid:
        return None

    return ctx
