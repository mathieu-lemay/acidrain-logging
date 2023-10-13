from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from flask import Flask  # type: ignore[import]
from pydantic import BaseModel

from acidrain_logging import LogConfig, configure_logger
from acidrain_logging.flask.middlewares import add_log_middlewares

if TYPE_CHECKING:
    from structlog.stdlib import BoundLogger

app = Flask(__name__)

log: BoundLogger = structlog.get_logger()


class Result(BaseModel):
    status: str = "OK"


# Decorator is untyped
@app.route("/")  # type: ignore[misc]
def root() -> str:
    return Result().json()


# Decorator is untyped
@app.route("/value/<key1>/<key2>")  # type: ignore[misc]
def get_value(key1: str, key2: str) -> str:  # noqa: ARG001: Unused args are on purpose
    return Result().json()


def create_app(log_config: LogConfig | None = None) -> Flask:
    log_config = log_config or LogConfig()

    configure_logger(log_config)
    add_log_middlewares(app)

    return app
