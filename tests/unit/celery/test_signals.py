from typing import TYPE_CHECKING, Any, cast
from unittest.mock import ANY
from uuid import UUID

import pytest
import structlog
from _pytest.logging import LogCaptureFixture
from celery import Celery, Task
from celery.contrib.testing.worker import (  # type: ignore[import-untyped]
    TestWorkController,
)
from freezegun import freeze_time
from structlog.contextvars import bound_contextvars

from acidrain_logging.celery.signals import connect_signals, utcnow
from acidrain_logging.testing.utils import retry

if TYPE_CHECKING:
    from mypy_extensions import KwArg, VarArg

    LoggingTask = Task[[VarArg(tuple[Any]), KwArg(dict[str, Any])], int]


@pytest.fixture(scope="session")
def celery_config() -> dict[str, Any]:
    return {"broker_url": "memory://"}


@pytest.fixture(scope="session")
def celery_session_app(celery_session_app: Celery) -> Celery:
    connect_signals()

    return celery_session_app


@pytest.fixture(scope="session")
def logging_task(
    celery_session_app: Celery, celery_session_worker: TestWorkController
) -> "LoggingTask":
    @celery_session_app.task()
    def _task(*_: tuple[Any], **__: dict[str, Any]) -> int:
        structlog.get_logger("test.task").info("Test task is running")
        return 0

    celery_session_worker.reload()

    return _task


def test_task_metadata_is_logged_when_task_starts(
    logging_task: "LoggingTask", caplog: LogCaptureFixture
) -> None:
    args = (42, "foo")
    kwargs = {"k1": "val1", "k2": "val2"}
    task_name = f"{__name__}.{logging_task.__name__}"
    min_start = utcnow()
    result_future = logging_task.apply_async(args=args, kwargs=kwargs)

    # Ensure the task has completed with success
    assert result_future.get(timeout=2) == 0
    max_start = utcnow()

    record = next(
        r.msg for r in caplog.records if f"Received task: {task_name}" in r.message
    )
    assert isinstance(record, dict)  # type guard

    assert record["data"] == {
        "task_args": list(args),  # celery converts it to a list
        "task_kwargs": kwargs,
        "queue": "celery",
        "publish_tm": ANY,
        "start_delay": ANY,
    }
    assert record["task"] == {
        "id": result_future.task_id,
        "name": task_name,
        "start_time": ANY,
    }
    assert min_start <= record["task"]["start_time"] <= max_start


def test_task_metadata_is_logged_when_task_completes(
    logging_task: "LoggingTask", caplog: LogCaptureFixture
) -> None:
    task_name = f"{__name__}.{logging_task.__name__}"
    min_start = utcnow()
    result_future = logging_task.apply_async()

    # Ensure the task has completed with success
    assert result_future.get(timeout=2) == 0
    max_start = utcnow()

    record = find_log_record(
        caplog, f"Task complete: {task_name}", result_future.task_id
    )

    assert record["task"] == {
        "id": result_future.task_id,
        "name": task_name,
        "state": "SUCCESS",
        "start_time": ANY,
        "duration": ANY,
    }
    assert min_start <= record["task"]["start_time"] <= max_start
    assert 0 < record["task"]["duration"] <= (max_start - min_start).total_seconds()


@pytest.mark.parametrize("current_trace_id", [None, "some-trace-id"])
def test_trace_id_is_propagated_to_all_task_logs(
    logging_task: "LoggingTask",
    caplog: LogCaptureFixture,
    current_trace_id: str | None,
) -> None:
    """
    All logs should contain the trace id.

    If there was a trace id in the context when the task was published, that one should
    be propagated. Otherwise, a new one will be created.
    """
    with bound_contextvars(trace_id=current_trace_id):
        result_future = logging_task.apply_async()

    # Ensure the task has completed with success
    assert result_future.get(timeout=2) == 0

    task_start_record = find_log_record(
        caplog,
        f"Received task: {__name__}.{logging_task.__name__}",
        result_future.task_id,
    )
    if current_trace_id:
        expected_trace_id = current_trace_id
    else:
        # This validates that the record includes a trace id and that it's a valid UUID
        expected_trace_id = str(UUID(task_start_record["trace_id"]))

    task_running_record = find_log_record(
        caplog, "Test task is running", result_future.task_id
    )
    task_complete_record = find_log_record(
        caplog,
        f"Task complete: {__name__}.{logging_task.__name__}",
        result_future.task_id,
    )

    assert task_start_record["trace_id"] == expected_trace_id
    assert task_running_record["trace_id"] == expected_trace_id
    assert task_complete_record["trace_id"] == expected_trace_id


def test_task_publish_time_is_logged_when_task_starts(
    logging_task: "LoggingTask", caplog: LogCaptureFixture
) -> None:
    timestamp = utcnow()
    with freeze_time(time_to_freeze=timestamp):
        result_future = logging_task.apply_async()

    # Ensure the task has completed with success
    assert result_future.get(timeout=2) == 0

    record = find_log_record(
        caplog,
        f"Received task: {__name__}.{logging_task.__name__}",
        result_future.task_id,
    )
    assert record["data"]["publish_tm"] == timestamp.isoformat()

    start_delay = record["data"]["start_delay"]
    assert 0 < start_delay <= (utcnow() - timestamp).total_seconds()


@pytest.mark.parametrize("trace_id", [None, "some-trace-id"])
def test_task_can_be_run_sync(
    logging_task: "LoggingTask", caplog: LogCaptureFixture, trace_id: str | None
) -> None:
    """Task should run fine in a synchronous manner, but won't have a publish_tm."""
    if trace_id:
        with bound_contextvars(trace_id=trace_id):
            result = logging_task.apply()
    else:
        result = logging_task.apply()

    record = find_log_record(
        caplog,
        f"Received task: {__name__}.{logging_task.__name__}",
        result.task_id,
    )
    assert isinstance(record, dict)  # type guard

    assert "publish_tm" not in record["data"]
    assert "start_delay" not in record["data"]

    if trace_id:
        assert record["trace_id"] == trace_id
    else:
        assert "trace_id" not in record


def find_log_record(
    caplog: LogCaptureFixture, msg: str, task_id: str
) -> dict[str, Any]:
    def _find_record() -> dict[str, Any] | None:
        return next(
            (
                cast(dict[str, Any], r.msg)
                for r in caplog.records
                if msg in r.message
                and cast(dict[str, Any], r.msg)["task"]["id"] == task_id
            ),
            None,
        )

    record = retry(_find_record).until(lambda r: r is not None)
    assert record  # type guard, can't be None

    return record
