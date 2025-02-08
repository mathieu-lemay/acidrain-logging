import time
from typing import Any

import structlog
from fastapi import FastAPI
from opentelemetry import trace
from opentelemetry.propagate import extract
from opentelemetry.trace import SpanKind, get_tracer_provider
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response
from structlog.contextvars import clear_contextvars
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
        tracer = get_tracer_provider().get_tracer(__name__)

        with tracer.start_as_current_span(
            "API Request",
            context=extract(request.headers),
            kind=SpanKind.SERVER,
        ) as span:
            ctx = span.get_span_context()
            trace_id = trace.format_trace_id(ctx.trace_id)

            resp = await call_next(request)

            resp.headers["X-Trace-Id"] = trace_id

        return resp


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
