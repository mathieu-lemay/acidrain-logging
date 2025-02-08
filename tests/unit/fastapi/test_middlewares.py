from unittest.mock import Mock, patch

import pytest
from _pytest.logging import LogCaptureFixture
from faker import Faker
from fastapi import FastAPI
from fastapi.testclient import TestClient
from structlog.contextvars import bound_contextvars

from acidrain_logging import LogConfig, OutputFormat
from acidrain_logging.fastapi import middlewares
from acidrain_logging.testing.factories import LogConfigFactory, OtelSettingsFactory
from acidrain_logging.testing.fastapi import create_app


@pytest.fixture(scope="module")
def log_config() -> LogConfig:
    logger_levels = {"httpx": "ERROR"}
    return LogConfigFactory.build(
        output_format=OutputFormat.CONSOLE,
        level="INFO",
        logger_levels=logger_levels,
        otel=OtelSettingsFactory.build(injection_enabled=True),
    )


@pytest.fixture(scope="module")
def api_app(log_config: LogConfig) -> FastAPI:
    return create_app(log_config)


@pytest.fixture
def api_client(api_app: FastAPI) -> TestClient:
    return TestClient(api_app)


def test_context_reset_middleware(
    api_client: TestClient, caplog: LogCaptureFixture, faker: Faker
) -> None:
    extra_value = faker.pystr()

    with bound_contextvars(extra_value=extra_value):
        resp = api_client.get("/")

    assert resp.is_success

    assert len(caplog.records) == 1

    log_values = caplog.records[0].msg
    assert isinstance(log_values, dict)  # type check
    assert "extra_value" not in log_values


def test_trace_id_middleware_adds_trace_id_when_no_header(
    api_client: TestClient, caplog: LogCaptureFixture
) -> None:
    resp = api_client.get("/")

    assert resp.is_success
    assert "X-Trace-Id" in resp.headers

    trace_id = resp.headers["X-Trace-Id"]

    assert len(caplog.records) == 1

    log_values = caplog.records[0].msg
    assert isinstance(log_values, dict)  # type check
    assert log_values["otel.trace_id"] == str(trace_id)


def test_trace_id_middleware_re_uses_trace_id_from_headers(
    api_client: TestClient, caplog: LogCaptureFixture, faker: Faker
) -> None:
    trace_id = faker.hexify("^" * 32)
    span_id = faker.hexify("^" * 16)

    resp = api_client.get("/", headers={"traceparent": f"00-{trace_id}-{span_id}-01"})
    assert resp.is_success
    assert resp.headers["X-Trace-Id"] == trace_id

    assert len(caplog.records) == 1

    log_values = caplog.records[0].msg
    assert isinstance(log_values, dict)  # type check
    assert log_values["otel.trace_id"] == trace_id


@patch(f"{middlewares.__name__}.time")
def test_log_request_middleware(
    time_mock: Mock, api_client: TestClient, caplog: LogCaptureFixture, faker: Faker
) -> None:
    time_mock.perf_counter.side_effect = [1.23456789, 9.87654321]

    key1, key2, default, other = (faker.pystr() for _ in range(4))

    resp = api_client.get(f"/value/{key1}/{key2}?default={default}&other={other}")
    assert resp.is_success

    assert len(caplog.records) == 1

    log_values = caplog.records[0].msg
    assert isinstance(log_values, dict)  # type check

    expected_path = f"/value/{key1}/{key2}"
    assert log_values["event"] == f"GET {expected_path} 200"
    assert log_values["http"] == {
        "client": {"remote_ip": "testclient", "user_agent": "testclient"},
        "method": "GET",
        "request": {
            "path_params": {"key1": key1, "key2": key2},
            "query_params": {"default": default, "other": other},
        },
        "response": {"elapsed": 8641.975, "status_code": 200},
        "url": {"host": "testserver", "path": expected_path, "scheme": "http"},
    }
