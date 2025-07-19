from unittest.mock import Mock, patch

import pytest
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.trace.export import ConsoleSpanExporter

from acidrain_logging import configure_tracing
from acidrain_logging.config import OtelConfig, TraceExporter


@patch("acidrain_logging.tracing.set_tracer_provider")
@patch("acidrain_logging.tracing.TracerProvider")
@pytest.mark.parametrize(
    ("exporter", "exporter_class"),
    [
        ("console", ConsoleSpanExporter),
        ("otlp", OTLPSpanExporter),
        ("none", None),
    ],
)
def test_configure_otel(
    tracer_provider_cls_mock: Mock,
    set_tracer_provider_mock: Mock,
    exporter: str,
    exporter_class: type | None,
) -> None:
    config = OtelConfig(trace_exporter=TraceExporter(exporter))
    configure_tracing(config)

    tp = tracer_provider_cls_mock.return_value

    if exporter_class:
        tp.add_span_processor.assert_called_once()
        span_processor = tp.add_span_processor.call_args.args[0]
        assert isinstance(span_processor.span_exporter, exporter_class)
    else:
        tp.add_span_processor.assert_not_called()

    set_tracer_provider_mock.assert_called_with(tp)


@patch("acidrain_logging.tracing.set_tracer_provider")
@patch("acidrain_logging.tracing.TracerProvider")
def test_configure_otel_uses_default_config(
    tracer_provider_cls_mock: Mock,
    set_tracer_provider_mock: Mock,
) -> None:
    configure_tracing()

    tp = tracer_provider_cls_mock.return_value

    tp.add_span_processor.assert_called_once()
    span_processor = tp.add_span_processor.call_args.args[0]
    assert isinstance(span_processor.span_exporter, OTLPSpanExporter)

    set_tracer_provider_mock.assert_called_with(tp)
