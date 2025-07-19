import structlog
from flask import Flask
from pydantic import BaseModel
from structlog.stdlib import BoundLogger

from acidrain_logging import LogConfig, configure_logger, configure_tracing
from acidrain_logging.config import OtelConfig
from acidrain_logging.flask.middlewares import add_log_middlewares

app = Flask(__name__)

log: BoundLogger = structlog.get_logger()


class Result(BaseModel):
    status: str = "OK"


# Decorator is untyped
@app.route("/")
def root() -> str:
    return Result().model_dump_json()


# Decorator is untyped
@app.route("/value/<key1>/<key2>")
def get_value(key1: str, key2: str) -> str:  # noqa: ARG001 -> Unused args are on purpose
    return Result().model_dump_json()


def create_app(
    log_config: LogConfig | None = None, otel_config: OtelConfig | None = None
) -> Flask:
    log_config = log_config or LogConfig()
    otel_config = otel_config or OtelConfig()

    configure_logger(log_config)
    configure_tracing(otel_config)

    add_log_middlewares(app)

    return app
