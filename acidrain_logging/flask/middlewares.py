import time
from collections.abc import Iterable
from typing import TYPE_CHECKING, Any

import structlog
from flask import Flask, Response, g, request
from opentelemetry.instrumentation.flask import FlaskInstrumentor
from opentelemetry.trace import format_trace_id
from structlog.contextvars import clear_contextvars
from structlog.stdlib import BoundLogger

from acidrain_logging.telemetry import get_current_span_context

log: BoundLogger = structlog.get_logger()

if TYPE_CHECKING:
    from _typeshed.wsgi import StartResponse, WSGIApplication, WSGIEnvironment


class BaseMiddleware:
    def __init__(self, app: "WSGIApplication") -> None:
        self.app = app


class ResetContextMiddleware(BaseMiddleware):
    def __call__(
        self, environ: "WSGIEnvironment", start_response: "StartResponse"
    ) -> Iterable[bytes]:
        clear_contextvars()
        return self.app(environ, start_response)


def _inject_start_time() -> None:
    g.start_time = time.perf_counter()


def _log_request(response: Response) -> Response:
    msg = f"{request.method} {request.path} {response.status_code}"

    host = request.host
    if ":" in host:  # pragma: no cover: tested through module test
        host = host.split(":")[0]

    request_data: dict[str, Any] = {
        "method": request.method,
        "client": {
            "remote_ip": request.remote_addr,
            "user_agent": request.headers.get("user-agent"),
        },
        "request": {
            "path_params": request.view_args,
            "query_params": dict(request.args),
        },
        "url": {
            "host": host,
            "path": request.path,
            "scheme": request.scheme,
        },
        "response": {
            "status_code": response.status_code,
        },
    }

    start_time = g.get("start_time")
    if start_time:
        request_data["response"]["elapsed"] = round(
            (time.perf_counter() - start_time) * 1000, 3
        )

    log.info(msg, http=request_data)

    return response

def _inject_trace_id(response: Response) -> Response:
    span = get_current_span_context()
    if not span:
        return response

    response.headers["X-Trace-Id"] = format_trace_id(span.trace_id)

    return response

def add_log_middlewares(app: Flask) -> None:
    FlaskInstrumentor().instrument_app(app)  # type: ignore[no-untyped-call]

    for cls in reversed((ResetContextMiddleware,)):
        # Types are fine, and assigning to a method is what we _must_ do here.
        app.wsgi_app = cls(app.wsgi_app)  # type: ignore[method-assign]

    app.before_request(_inject_start_time)
    app.after_request(_log_request)
    app.after_request(_inject_trace_id)
