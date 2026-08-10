import os
import logging
from contextvars import ContextVar, Token
from typing import Any, Dict, Optional

from src.config import settings
from src.observability.sanitization import sanitize_attributes, redact_text

logger = logging.getLogger("supportgpt.observability.tracing")
_initialized = False
_request_id_context: ContextVar[Optional[str]] = ContextVar(
    "supportgpt_request_id", default=None
)


def get_tracer(name: str = "supportgpt"):
    from opentelemetry import trace

    return trace.get_tracer(name)


def set_span_attributes(span: Any, attributes: Dict[str, Any]) -> None:
    """Set sanitized attributes without allowing telemetry to break business code."""
    try:
        span.set_attributes(sanitize_attributes(attributes))
    except Exception as exc:
        logger.debug("Unable to attach span attributes: %s", exc)


def bind_request_id(request_id: str) -> Token:
    return _request_id_context.set(redact_text(request_id)[:128])


def reset_request_id(token: Token) -> None:
    try:
        _request_id_context.reset(token)
    except Exception:
        return


def get_request_id() -> Optional[str]:
    return _request_id_context.get()


def get_current_trace_id() -> Optional[str]:
    try:
        from opentelemetry import trace

        context = trace.get_current_span().get_span_context()
        if context and context.is_valid:
            return format(context.trace_id, "032x")
    except Exception:
        return None
    return None


def mark_span_error(span: Any, error: BaseException) -> None:
    """Record a sanitized exception while preserving the original exception flow."""
    try:
        from opentelemetry.trace import Status, StatusCode

        safe_message = redact_text(str(error))[:256]
        span.add_event(
            "exception",
            {
                "exception.type": error.__class__.__name__,
                "exception.message": safe_message,
                "exception.escaped": True,
            },
        )
        span.set_status(Status(StatusCode.ERROR, safe_message))
    except Exception:
        return


def init_tracing() -> None:
    """Initialize OpenTelemetry traces/metrics and LangSmith settings."""
    global _initialized
    # LangSmith config
    langsmith_enabled = settings.LANGSMITH_TRACING or settings.LANGCHAIN_TRACING_V2
    if settings.LANGSMITH_TRACING:
        langsmith_api_key = settings.LANGSMITH_API_KEY or settings.LANGCHAIN_API_KEY
        langsmith_project = settings.LANGSMITH_PROJECT
    else:
        langsmith_api_key = settings.LANGCHAIN_API_KEY or settings.LANGSMITH_API_KEY
        langsmith_project = settings.LANGCHAIN_PROJECT

    if langsmith_enabled:
        os.environ["LANGSMITH_TRACING"] = "true"
        os.environ["LANGCHAIN_TRACING_V2"] = "true"
        if langsmith_api_key:
            os.environ["LANGSMITH_API_KEY"] = langsmith_api_key
            os.environ["LANGCHAIN_API_KEY"] = langsmith_api_key
        os.environ["LANGSMITH_PROJECT"] = langsmith_project
        os.environ["LANGCHAIN_PROJECT"] = langsmith_project
        os.environ["LANGSMITH_ENDPOINT"] = settings.LANGSMITH_ENDPOINT
        os.environ["LANGCHAIN_ENDPOINT"] = settings.LANGSMITH_ENDPOINT
        if settings.LANGSMITH_WORKSPACE_ID:
            os.environ["LANGSMITH_WORKSPACE_ID"] = settings.LANGSMITH_WORKSPACE_ID
        logger.info("LangSmith tracing enabled and environment variables configured.")
    else:
        os.environ["LANGSMITH_TRACING"] = "false"
        os.environ["LANGCHAIN_TRACING_V2"] = "false"
        logger.info("LangSmith tracing is disabled.")

    if _initialized or not settings.OTEL_ENABLED:
        return

    # OpenTelemetry SDK initialization is deliberately fail-open.
    try:
        from opentelemetry.sdk.resources import Resource

        resource = Resource.create(
            {
                "service.name": settings.OTEL_SERVICE_NAME,
                "service.version": "1.0.0",
                "deployment.environment": settings.APP_ENV,
            }
        )

    except Exception as e:
        logger.warning("Could not create OpenTelemetry resource: %s", e)
        _initialized = True
        return

    try:
        from opentelemetry import trace
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import (
            BatchSpanProcessor,
            ConsoleSpanExporter,
        )
        from opentelemetry.sdk.trace.sampling import ParentBased, TraceIdRatioBased

        current_tracer_provider = trace.get_tracer_provider()
        if isinstance(current_tracer_provider, TracerProvider):
            tracer_provider = current_tracer_provider
        else:
            tracer_provider = TracerProvider(
                resource=resource,
                sampler=ParentBased(
                    TraceIdRatioBased(settings.OTEL_TRACE_SAMPLE_RATIO)
                ),
            )
            trace.set_tracer_provider(tracer_provider)

        if settings.OTEL_EXPORTER_OTLP_TRACES_ENDPOINT:
            from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
                OTLPSpanExporter,
            )

            tracer_provider.add_span_processor(
                BatchSpanProcessor(
                    OTLPSpanExporter(
                        endpoint=settings.OTEL_EXPORTER_OTLP_TRACES_ENDPOINT,
                        timeout=settings.OTEL_EXPORTER_OTLP_TIMEOUT_SECONDS,
                    )
                )
            )
        if settings.OTEL_CONSOLE_EXPORTER:
            tracer_provider.add_span_processor(
                BatchSpanProcessor(ConsoleSpanExporter())
            )
    except Exception as exc:
        logger.warning("Could not initialize OpenTelemetry traces: %s", exc)

    try:
        from opentelemetry import metrics
        from opentelemetry.sdk.metrics import MeterProvider
        from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
        from opentelemetry.sdk.metrics.view import (
            ExplicitBucketHistogramAggregation,
            View,
        )

        current_meter_provider = metrics.get_meter_provider()
        if not isinstance(current_meter_provider, MeterProvider):
            metric_readers = []
            if settings.OTEL_EXPORTER_OTLP_METRICS_ENDPOINT:
                from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
                    OTLPMetricExporter,
                )

                metric_readers.append(
                    PeriodicExportingMetricReader(
                        OTLPMetricExporter(
                            endpoint=settings.OTEL_EXPORTER_OTLP_METRICS_ENDPOINT,
                            timeout=settings.OTEL_EXPORTER_OTLP_TIMEOUT_SECONDS,
                        ),
                        export_interval_millis=(
                            settings.OTEL_METRIC_EXPORT_INTERVAL_MILLISECONDS
                        ),
                    )
                )

            metrics.set_meter_provider(
                MeterProvider(
                    resource=resource,
                    metric_readers=metric_readers,
                    views=[
                        View(
                            instrument_name="qa_score_ratio",
                            aggregation=ExplicitBucketHistogramAggregation(
                                boundaries=(
                                    0.1,
                                    0.2,
                                    0.3,
                                    0.4,
                                    0.5,
                                    0.6,
                                    0.7,
                                    0.8,
                                    0.9,
                                    1.0,
                                )
                            ),
                        )
                    ],
                )
            )
    except Exception as exc:
        logger.warning("Could not initialize OpenTelemetry metrics: %s", exc)

    _initialized = True
    logger.info(
        "OpenTelemetry initialized: service=%s, traces_otlp=%s, metrics_otlp=%s",
        settings.OTEL_SERVICE_NAME,
        bool(settings.OTEL_EXPORTER_OTLP_TRACES_ENDPOINT),
        bool(settings.OTEL_EXPORTER_OTLP_METRICS_ENDPOINT),
    )
