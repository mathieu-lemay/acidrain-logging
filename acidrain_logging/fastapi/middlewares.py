import time
from typing import Any

import structlog
from fastapi import FastAPI
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.trace import format_trace_id, get_current_span
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from structlog.contextvars import clear_contextvars
from structlog.stdlib import BoundLogger

from acidrain_logging.telemetry import get_current_span_context

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
        response = await call_next(request)

        span = get_current_span_context()
        if not span:
            return response

        response.headers["X-Trace-Id"] = format_trace_id(span.trace_id)

        return response


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
) -> dict[str, Any]:
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
    FastAPIInstrumentor.instrument_app(app)
