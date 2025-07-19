import os

from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    ConsoleSpanExporter,
    SpanExporter,
)
from opentelemetry.trace import set_tracer_provider

from acidrain_logging.config import OtelConfig, TraceExporter


def configure_tracing(tracing_config: OtelConfig | None = None) -> None:
    tracing_config = tracing_config or OtelConfig()

    tp = TracerProvider()

    exporter: SpanExporter | None = None

    match tracing_config.trace_exporter:
        case TraceExporter.CONSOLE:
            exporter = ConsoleSpanExporter(
                formatter=lambda s: s.to_json(indent=None) + os.linesep
            )
        case TraceExporter.OTLP:
            exporter = OTLPSpanExporter()
        case TraceExporter.NONE:
            pass

    if exporter:
        tp.add_span_processor(BatchSpanProcessor(exporter))

    set_tracer_provider(tp)
