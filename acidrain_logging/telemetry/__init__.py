try:
    from acidrain_logging.telemetry.otel import (
        configure_telemetry,
        get_current_span_context,
    )
except ImportError:
    from acidrain_logging.telemetry.null import (
        configure_telemetry,
        get_current_span_context,
    )


__all__ = ["configure_telemetry", "get_current_span_context"]
