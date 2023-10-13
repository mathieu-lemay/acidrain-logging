import time
from typing import Any, Callable, Dict, Iterable, List, Tuple
from uuid import uuid4

import structlog
from flask import Flask, Response, g, request  # type: ignore[import]
from structlog.contextvars import bind_contextvars, clear_contextvars
from structlog.stdlib import BoundLogger
from typing_extensions import Protocol, TypeAlias
from werkzeug.wrappers import Request  # type: ignore[import]

log: BoundLogger = structlog.get_logger()


# TODO: Import typing stuff from werkzeug when we update to latest
class StartResponse(Protocol):
    def __call__(
        self,
        __status: str,
        __headers: List[Tuple[str, str]],
        __exc_info: Any = ...,  # noqa: ANN401
    ) -> Callable[[bytes], object]:  # pragma: no cover
        ...


WSGIEnvironment: TypeAlias = Dict[str, Any]
WSGIApplication: TypeAlias = Callable[[WSGIEnvironment, StartResponse], Iterable[bytes]]


class BaseMiddleware:
    def __init__(self, app: WSGIApplication) -> None:
        self.app = app


class ResetContextMiddleware(BaseMiddleware):
    def __call__(
        self, environ: Dict[str, Any], start_response: StartResponse
    ) -> Iterable[bytes]:
        clear_contextvars()
        return self.app(environ, start_response)


class TraceIdMiddleware(BaseMiddleware):
    def __call__(
        self, environ: Dict[str, Any], start_response: StartResponse
    ) -> Iterable[bytes]:
        req = Request(environ)

        trace_id = req.headers.get("X-Trace-Id") or str(uuid4())
        bind_contextvars(trace_id=trace_id)

        return self.app(environ, start_response)


def _inject_start_time() -> None:
    g.start_time = time.perf_counter()


def _log_request(response: Response) -> Response:
    msg = f"{request.method} {request.path} {response.status_code}"

    host = request.host
    if ":" in host:  # pragma: no cover: tested through module test
        host = host.split(":")[0]

    request_data = {
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
            "elapsed": round((time.perf_counter() - g.start_time) * 1000, 3),
            "status_code": response.status_code,
        },
    }

    log.info(msg, http=request_data)

    return response


def add_log_middlewares(app: Flask) -> None:
    for cls in reversed((ResetContextMiddleware, TraceIdMiddleware)):
        app.wsgi_app = cls(app.wsgi_app)

    app.before_request(_inject_start_time)
    app.after_request(_log_request)
