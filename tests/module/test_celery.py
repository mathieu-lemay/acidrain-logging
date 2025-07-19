import json
import re
from datetime import UTC, datetime
from typing import Any

import pytest
import tenacity
from pytest_docker.plugin import (
    DockerComposeExecutor,
    Services,
)

from tests.module.conftest import DockerLogs


@pytest.fixture(scope="session")
def _celery_worker(docker_services: Services, docker_logs: DockerLogs) -> None:
    def _healthcheck() -> bool:
        logs = docker_logs("worker")

        return bool(re.search("celery@[0-9a-f]+ ready.", logs))

    docker_services.wait_until_responsive(_healthcheck, timeout=30, pause=0.05)


@pytest.mark.usefixtures("_celery_worker")  # ensure the worker is up and running
async def test_celery_logs_the_startup_banner(docker_logs: DockerLogs) -> None:
    worker_logs = (docker_logs("worker")).split("\n")

    for entry in map(json.loads, filter(None, reversed(worker_logs))):
        if "message" in entry and entry["message"].startswith("Celery Startup"):
            break
    else:  # pragma: no cover
        pytest.fail("Could not find startup banner")

    # Ensure the banner was logged properly by checking for some keys
    assert "[config]" in entry["message"]
    assert "[queues]" in entry["message"]

    # Ensure metadata
    assert datetime.strptime(  # noqa: DTZ007 -> Timezone is irrelevant
        entry["timestamp"], "%Y-%m-%dT%H:%M:%S.%fZ"
    )


@pytest.mark.usefixtures("_celery_worker")  # ensure the worker is up and running
async def test_task_logging_uses_otel(
    docker_logs: DockerLogs, docker_compose_executor: DockerComposeExecutor
) -> None:
    timestamp = datetime.now(tz=UTC)

    python_cmd = (
        "from acidrain_logging.testing.celery import dummy_task; "
        "dummy_task.delay(1).get(timeout=2)"
    )
    docker_compose_executor.execute(f"exec worker sh -c \"python -c '{python_cmd}'\"")

    worker_logs = docker_logs("worker", since=timestamp).split("\n")

    assert len(worker_logs) >= 1

    entry = next(
        (
            e
            for e in map(json.loads, worker_logs)
            if "logger" in e and e["logger"].startswith("acidrain_logging.")
        ),
        None,
    )

    assert entry is not None
    assert "otel.trace_id" in entry
    assert "otel.span_id" in entry

    def get_exported_spans() -> list[dict[str, Any]]:
        logs = docker_logs("worker", since=timestamp)

        return [
            e
            for e in map(json.loads, filter(None, logs.split("\n")))
            if "kind" in e and e["kind"].startswith("SpanKind.")
        ]

    log_entries = tenacity.retry(
        stop=tenacity.stop_after_delay(15),
        retry=tenacity.retry_if_result(lambda x: x == []),
    )(get_exported_spans)()

    assert len(log_entries) > 0
    assert log_entries[0]["resource"]["attributes"]["service.name"] == "test-celery"


@pytest.mark.usefixtures("_celery_worker")  # ensure the worker is up and running
async def test_task_start_log_includes_publish_tm(
    docker_logs: DockerLogs, docker_compose_executor: DockerComposeExecutor
) -> None:
    timestamp = datetime.now(tz=UTC)

    python_cmd = (
        "from acidrain_logging.testing.celery import dummy_task; "
        "dummy_task.delay(1).get(timeout=2)"
    )
    docker_compose_executor.execute(f"exec worker sh -c \"python -c '{python_cmd}'\"")

    worker_logs = docker_logs("worker", since=timestamp)
    log_entries = [
        entry
        for entry in map(json.loads, filter(None, worker_logs.split("\n")))
        if "logger" in entry
        and entry["message"].startswith("Received task")
        and entry["logger"].startswith("acidrain_logging.")
    ]

    assert len(log_entries) == 1

    # This validates the data is present and in the right format
    assert datetime.fromisoformat(log_entries[0]["data"]["publish_tm"])
