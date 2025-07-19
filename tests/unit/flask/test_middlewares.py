import importlib.metadata
from http import HTTPStatus
from unittest.mock import Mock, patch
from uuid import uuid4

import pytest
from _pytest.logging import LogCaptureFixture
from faker import Faker
from flask import Flask
from flask.testing import FlaskClient
from opentelemetry import trace
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from structlog.contextvars import bound_contextvars

from acidrain_logging import LogConfig, OutputFormat
from acidrain_logging.flask import middlewares
from acidrain_logging.testing.factories import LogConfigFactory
from acidrain_logging.testing.flask import create_app


@pytest.fixture(scope="module")
def log_config() -> LogConfig:
    logger_levels = {"httpx": "ERROR"}
    return LogConfigFactory.build(
        output_format=OutputFormat.CONSOLE, level="INFO", logger_levels=logger_levels
    )


@pytest.fixture(scope="module")
def api_app(log_config: LogConfig) -> Flask:
    return create_app(log_config)


@pytest.fixture
def api_client(api_app: Flask) -> FlaskClient:
    return api_app.test_client()


def test_context_reset_middleware(
    api_client: FlaskClient, caplog: LogCaptureFixture, faker: Faker
) -> None:
    extra_value = faker.pystr()

    with bound_contextvars(extra_value=extra_value):
        resp = api_client.get("/")

    assert resp.status_code == HTTPStatus.OK

    assert len(caplog.records) == 1

    log_values = caplog.records[0].msg
    assert isinstance(log_values, dict)  # type check
    assert "extra_value" not in log_values


def test_trace_id_middleware_adds_trace_id_when_no_header(
    api_client: FlaskClient, caplog: LogCaptureFixture
) -> None:
    trace_id = uuid4()

    with patch(f"{middlewares.__name__}.uuid4") as uuid4_mock:
        uuid4_mock.return_value = trace_id
        resp = api_client.get("/")

    assert resp.status_code == HTTPStatus.OK

    assert len(caplog.records) == 1

    log_values = caplog.records[0].msg
    assert isinstance(log_values, dict)  # type check
    assert log_values["trace_id"] == str(trace_id)


def test_trace_id_middleware_re_uses_trace_id_from_headers(
    api_client: FlaskClient, caplog: LogCaptureFixture, faker: Faker
) -> None:
    trace_id = faker.pystr()

    resp = api_client.get("/", headers={"x-trace-id": trace_id})
    assert resp.status_code == HTTPStatus.OK

    assert len(caplog.records) == 1

    log_values = caplog.records[0].msg
    assert isinstance(log_values, dict)  # type check
    assert log_values["trace_id"] == str(trace_id)


def test_otel_instrumentation_adds_trace_id_when_no_header(
    api_client: FlaskClient,
    span_exporter: InMemorySpanExporter,
    caplog: LogCaptureFixture,
) -> None:
    resp = api_client.get("/")
    assert resp.status_code == HTTPStatus.OK

    assert len(span_exporter.get_finished_spans()) != 0
    span = next(
        (s for s in span_exporter.get_finished_spans() if s.name == "GET /"), None
    )
    assert span is not None

    assert len(caplog.records) == 1

    log_values = caplog.records[0].msg
    assert isinstance(log_values, dict)  # type check
    assert log_values["otel.trace_id"] == trace.format_trace_id(span.context.trace_id)


def test_otel_instrumentation_re_uses_trace_id_from_headers(
    api_client: FlaskClient, span_exporter: InMemorySpanExporter, faker: Faker
) -> None:
    trace_id = faker.hexify("^" * 32)
    span_id = faker.hexify("^" * 16)

    resp = api_client.get("/", headers={"traceparent": f"00-{trace_id}-{span_id}-01"})
    assert resp.status_code == HTTPStatus.OK

    span = next(
        (s for s in span_exporter.get_finished_spans() if s.name == "GET /"), None
    )
    assert span is not None
    assert trace.format_trace_id(span.context.trace_id) == trace_id

    # The exported span should have our injected span_id as its parent
    assert span.parent is not None
    assert trace.format_span_id(span.parent.span_id) == span_id


@patch(f"{middlewares.__name__}.time")
def test_log_request_middleware(
    time_mock: Mock, api_client: FlaskClient, caplog: LogCaptureFixture, faker: Faker
) -> None:
    time_mock.perf_counter.side_effect = [1.23456789, 9.87654321]

    key1, key2, default, other = (faker.pystr() for _ in range(4))

    resp = api_client.get(f"/value/{key1}/{key2}?default={default}&other={other}")
    assert resp.status_code == HTTPStatus.OK

    assert len(caplog.records) == 1

    log_values = caplog.records[0].msg
    assert isinstance(log_values, dict)  # type check

    expected_path = f"/value/{key1}/{key2}"
    expected_user_agent = f"Werkzeug/{importlib.metadata.version('werkzeug')}"
    assert log_values["event"] == f"GET {expected_path} 200"
    assert log_values["http"] == {
        "client": {
            "remote_ip": "127.0.0.1",
            "user_agent": expected_user_agent,
        },
        "method": "GET",
        "request": {
            "path_params": {"key1": key1, "key2": key2},
            "query_params": {"default": default, "other": other},
        },
        "response": {
            "elapsed": 8641.975,
            "status_code": 200,
        },
        "url": {"host": "localhost", "path": expected_path, "scheme": "http"},
    }


def test_log_request_middleware_ignores_elapsed_if_theres_no_start_time(
    api_app: Flask, api_client: FlaskClient, caplog: LogCaptureFixture
) -> None:
    funcs = api_app.before_request_funcs
    api_app.before_request_funcs = {}

    resp = api_client.get("/")

    api_app.before_request_funcs = funcs

    assert resp.status_code == HTTPStatus.OK

    rec = next(
        (r for r in caplog.records if r.name.startswith("acidrain_logging.")), None
    )

    assert rec is not None
    log_values = rec.msg
    assert isinstance(log_values, dict)  # type check

    assert log_values["event"] == "GET / 200"
    assert "elapsed" not in log_values["http"]["response"]
