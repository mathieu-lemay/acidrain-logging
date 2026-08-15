from typing import TYPE_CHECKING

from acidrain_logging.config import OtelConfig

if TYPE_CHECKING:
    from opentelemetry.trace import SpanContext


def configure_telemetry(telemetry_config: OtelConfig | None = None) -> None:
    pass


def get_current_span_context() -> "SpanContext | None":
    return None
