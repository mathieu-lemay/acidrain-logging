from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

import structlog
from fastapi import FastAPI, Path, Query
from pydantic import BaseModel

from acidrain_logging import LogConfig, configure_logger, configure_tracing
from acidrain_logging.config import OtelConfig
from acidrain_logging.fastapi.middlewares import add_log_middlewares

if TYPE_CHECKING:
    from structlog.stdlib import BoundLogger

app = FastAPI()

log: BoundLogger = structlog.get_logger()


class Result(BaseModel):
    status: str = "OK"


@app.get("/")
def root() -> Result:
    return Result()


@app.get("/value/{key1}/{key2}")
def get_value(
    _key1: Annotated[str, Path(alias="key1")],
    _key2: Annotated[str, Path(alias="key2")],
    _default: Annotated[str, Query(alias="default")],
) -> Result:
    return Result()


def create_app(
    log_config: LogConfig | None = None, otel_config: OtelConfig | None = None
) -> FastAPI:
    log_config = log_config or LogConfig()
    otel_config = otel_config or OtelConfig()

    configure_logger(log_config)
    configure_tracing(otel_config)

    add_log_middlewares(app)

    return app
