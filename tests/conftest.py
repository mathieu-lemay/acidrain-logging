from collections.abc import Generator
from time import time

import pytest
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from opentelemetry.trace import set_tracer_provider

pytest_plugins = ("celery.contrib.pytest",)


@pytest.fixture(scope="session", autouse=True)
def faker_seed() -> float:
    return time()


@pytest.fixture(scope="session")
def span_exporter_session() -> InMemorySpanExporter:
    return InMemorySpanExporter()


@pytest.fixture(scope="session")
def tracer_provider(span_exporter_session: InMemorySpanExporter) -> TracerProvider:
    tp = TracerProvider()
    tp.add_span_processor(SimpleSpanProcessor(span_exporter_session))

    return tp


@pytest.fixture(scope="session", autouse=True)
def _setup_tracing(tracer_provider: TracerProvider) -> None:
    """Ensure tracing is set up properly for testing."""
    set_tracer_provider(tracer_provider)


@pytest.fixture
def span_exporter(
    span_exporter_session: InMemorySpanExporter,
) -> Generator[InMemorySpanExporter]:
    span_exporter_session.clear()
    yield span_exporter_session
    span_exporter_session.clear()
