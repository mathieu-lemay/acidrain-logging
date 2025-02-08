from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.trace import set_tracer_provider


def configure_tracing() -> None:
    tp = TracerProvider()
    # tp.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))

    set_tracer_provider(tp)
