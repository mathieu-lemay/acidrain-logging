import json
import re
from datetime import UTC, datetime
from uuid import UUID

import pytest
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
        if entry["message"].startswith("Celery Startup"):
            break
    else:  # pragma: no cover
        pytest.fail("Could not find startup banner")

    # Ensure the banner was logged properly by checking for some keys
    assert "[config]" in entry["message"]
    assert "[queues]" in entry["message"]

    # Ensure metadata
    assert entry["dd.env"] == "testing"
    assert entry["dd.service"] == "test-api"
    assert entry["dd.version"] == "0.0.0-dev"
    assert datetime.strptime(  # noqa: DTZ007 -> Timezone is irrelevant
        entry["timestamp"], "%Y-%m-%dT%H:%M:%S.%fZ"
    )


@pytest.mark.usefixtures("_celery_worker")  # ensure the worker is up and running
async def test_task_logging_includes_task_id_and_trace_id(
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
        if entry["logger"].startswith("acidrain_logging.")
    ]

    assert len(log_entries) == 3

    # Ensure all logs have the same task id and that it is a valid uuid
    task_id = log_entries[0]["task"]["id"]
    assert UUID(task_id)
    assert {e["task"]["id"] for e in log_entries} == {task_id}

    # Ensure all logs have the same trace id and that it is a valid uuid
    trace_id = log_entries[0]["trace_id"]
    assert UUID(trace_id)
    assert {e["trace_id"] for e in log_entries} == {trace_id}


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
        if entry["message"].startswith("Received task")
        and entry["logger"].startswith("acidrain_logging.")
    ]

    assert len(log_entries) == 1

    # This validates the data is present and in the right format
    assert datetime.fromisoformat(log_entries[0]["data"]["publish_tm"])
