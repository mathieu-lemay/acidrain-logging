from datetime import datetime
from typing import TYPE_CHECKING, Any, Dict, List, Tuple
from uuid import uuid4

import pytz
import structlog
from celery.apps.worker import Worker
from celery.signals import (
    before_task_publish,
    celeryd_after_setup,
    setup_logging,
    task_postrun,
    task_prerun,
)
from structlog.contextvars import bind_contextvars, get_contextvars, reset_contextvars
from structlog.stdlib import BoundLogger

from acidrain_logging import configure_logger

if TYPE_CHECKING:
    from celery import Task

log: BoundLogger = structlog.get_logger()


def utcnow() -> datetime:
    return datetime.now(tz=pytz.UTC)


def _setup_logging(*_: Tuple[Any], **__: Dict[str, Any]) -> None:
    configure_logger()


def _log_celery_startup(
    sender: str, instance: Worker, **__: Dict[str, Any]
) -> None:  # pragma: no cover: Covered through module tests
    """Log Celery's banner, which we are hiding with the --quiet param."""
    # Typing is wrong, instance does have `startup_info`
    banner = instance.startup_info(artlines=False)  # type: ignore[attr-defined]
    log.info("Celery Startup (%s)\n%s", sender, banner)


def _add_task_meta(
    headers: Dict[str, Any], *_: Tuple[Any], **__: Dict[str, Any]
) -> None:
    """Inject publish timestamp and trace id, if available, to all tasks."""
    headers["x_trace_id"] = get_contextvars().get("trace_id") or str(uuid4())
    headers["x_publish_tm"] = utcnow().isoformat()


def _task_prerun(
    task_id: str,
    task: "Task[Any, Any]",
    args: List[Any],
    kwargs: Dict[str, Any],
    *_: Tuple[Any],
    **__: Dict[str, Any],
) -> None:
    """Add task data to logging context."""
    start_time = utcnow()

    # Typing is wrong, request does have `get`
    trace_id = task.request.get("x_trace_id")  # type: ignore[attr-defined]
    if trace_id:
        # Bind the trace id if there's one in the props, otherwise, keep the one we may
        # already have
        bind_contextvars(trace_id=trace_id)

    bind_contextvars(task={"id": task_id, "name": task.name, "start_time": start_time})

    log_data: Dict[str, Any] = {
        "task_args": args,
        "task_kwargs": kwargs,
        "queue": task.request.delivery_info["routing_key"],
    }

    # Typing is wrong, request does have `get`
    publish_tm = task.request.get("x_publish_tm")  # type: ignore[attr-defined]
    if publish_tm:
        log_data["publish_tm"] = publish_tm
        log_data["start_delay"] = (
            start_time - datetime.fromisoformat(publish_tm)
        ).total_seconds()

    log.info("Received task: %s", task.name, data=log_data)


def _task_postrun(
    task: "Task[Any, Any]",
    state: str,
    *_: Tuple[Any],
    **__: Dict[str, Any],
) -> None:
    """Log the task end and status and reset context."""
    task_ctx = get_contextvars().get("task", {}).copy()
    start_time = task_ctx.get("start_time")
    task_ctx.update(
        {
            "name": task.name,
            "state": state,
            "duration": (utcnow() - start_time).total_seconds() if start_time else None,
        }
    )
    bind_contextvars(task=task_ctx)
    log.info("Task complete: %s", task.name)
    reset_contextvars()


def connect_signals() -> None:
    setup_logging.connect(_setup_logging)
    celeryd_after_setup.connect(_log_celery_startup)
    before_task_publish.connect(_add_task_meta)
    task_prerun.connect(_task_prerun)
    task_postrun.connect(_task_postrun)
