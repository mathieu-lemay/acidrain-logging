import time
from typing import Any, Dict
from uuid import uuid4

import structlog
from fastapi import FastAPI
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from structlog.contextvars import bind_contextvars, clear_contextvars
from structlog.stdlib import BoundLogger

log: BoundLogger = structlog.get_logger()


class ContextResetMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        clear_contextvars()

        return await call_next(request)


class TraceIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        trace_id = request.headers.get("X-Trace-Id") or str(uuid4())
        bind_contextvars(trace_id=trace_id)

        return await call_next(request)


class LogRequestMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self, request: Request, call_next: RequestResponseEndpoint
    ) -> Response:
        start_time = time.perf_counter()

        response = await call_next(request)

        end_time = time.perf_counter()
        elapsed_ms = round((end_time - start_time) * 1000, 3)

        msg = f"{request.method} {request.url.path} {response.status_code}"
        request_data = get_request_data(request, response, elapsed_ms)

        log.info(msg, http=request_data)

        return response


def get_request_data(
    request: Request, response: Response, elapsed_ms: float
) -> Dict[str, Any]:
    return {
        "method": request.method,
        "client": {
            "remote_ip": request.client.host if request.client else None,
            "user_agent": request.headers.get("user-agent"),
        },
        "request": {
            "path_params": request.path_params,
            "query_params": {**request.query_params},
        },
        "url": {
            "host": request.url.hostname,
            "path": request.url.path,
            "scheme": request.url.scheme,
        },
        "response": {
            "elapsed": elapsed_ms,
            "status_code": response.status_code,
        },
    }


def add_log_middlewares(app: FastAPI) -> None:
    app.add_middleware(LogRequestMiddleware)
    app.add_middleware(TraceIdMiddleware)
    app.add_middleware(ContextResetMiddleware)
