import functools
import inspect
import logging
import socket
import time
from contextlib import contextmanager
from contextvars import ContextVar, Token
from typing import Any, Callable, Dict, Iterator, Optional
from urllib.parse import urlparse

from src.config import settings
from src.observability.sanitization import redact_text, sanitize_attributes

logger = logging.getLogger("supportgpt.observability.tracing")
_initialized = False
_request_id_context: ContextVar[Optional[str]] = ContextVar(
    "supportgpt_request_id", default=None
)
_langsmith_agent_context: ContextVar[bool] = ContextVar(
    "supportgpt_langsmith_agent_context", default=False
)
_agent_trace_id_context: ContextVar[Optional[str]] = ContextVar(
    "supportgpt_agent_trace_id", default=None
)


def get_tracer(name: str = "supportgpt"):
    from opentelemetry import trace

    return trace.get_tracer(name)


def _should_enable_otlp_exporter(endpoint: Optional[str], signal: str) -> bool:
    """本地启动时预检 Collector，避免后台 exporter 重试刷屏。"""
    if not endpoint:
        return False
    is_local = settings.APP_ENV.lower() in {"development", "dev", "local", "test"}
    if not settings.OTEL_EXPORTER_PREFLIGHT_ENABLED or not is_local:
        return True

    parsed = urlparse(endpoint)
    host = parsed.hostname
    port = parsed.port or (443 if parsed.scheme == "https" else 80)
    if not host:
        logger.warning("Skipping OTLP %s exporter: invalid endpoint.", signal)
        return False
    try:
        with socket.create_connection(
            (host, port), timeout=settings.OTEL_EXPORTER_PREFLIGHT_TIMEOUT_SECONDS
        ):
            return True
    except OSError:
        logger.warning(
            "Skipping OTLP %s exporter because Collector is unreachable at %s:%s; "
            "start Collector and restart backend to enable export.",
            signal,
            host,
            port,
        )
        return False


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


def bind_agent_trace_id() -> Token:
    """为当前请求初始化 Agent Trace ID 上下文。"""
    return _agent_trace_id_context.set(None)


def set_agent_trace_id(trace_id: Optional[str]) -> None:
    _agent_trace_id_context.set(trace_id)


def get_agent_trace_id() -> Optional[str]:
    return _agent_trace_id_context.get()


def reset_agent_trace_id(token: Token) -> None:
    try:
        _agent_trace_id_context.reset(token)
    except Exception:
        return


@contextmanager
def langsmith_agent_trace_context() -> Iterator[None]:
    """仅在主 Agent Workflow 执行期间允许 Span 进入 LangSmith。"""
    token = _langsmith_agent_context.set(True)
    try:
        yield
    finally:
        _langsmith_agent_context.reset(token)


def langsmith_span_attributes(
    kind: str, *, trace_name: Optional[str] = None, force: bool = False
) -> Dict[str, Any]:
    """为主 Agent 链路补充 LangSmith 可识别的 Run 类型。"""
    if not force and not _langsmith_agent_context.get():
        return {}
    attributes: Dict[str, Any] = {
        "langsmith.export": True,
        "langsmith.span.kind": kind,
    }
    if trace_name:
        attributes["langsmith.trace.name"] = trace_name
    return attributes


def _llm_span_attributes() -> Dict[str, Any]:
    """记录模型识别信息，不上报 Prompt 和回复正文。"""
    provider = settings.LLM_PROVIDER.lower()
    if provider == "azure":
        model = settings.AZURE_OPENAI_DEPLOYMENT or "azure"
    elif provider == "openai":
        model = settings.LLM_MODEL_NAME or "openai-compatible"
    else:
        model = "mock"
    return {
        **langsmith_span_attributes("llm"),
        "gen_ai.operation.name": "chat",
        "gen_ai.system": provider,
        "gen_ai.provider.name": provider,
        "gen_ai.request.model": model,
    }


def mark_span_error(span: Any, error: BaseException) -> None:
    """Record a sanitized exception while preserving the original exception flow."""
    try:
        from opentelemetry.trace import Status, StatusCode

        span.add_event(
            "exception",
            {
                "exception.type": error.__class__.__name__,
                "exception.escaped": True,
            },
        )
        span.set_status(Status(StatusCode.ERROR))
    except Exception:
        return


@contextmanager
def observed_span(
    tracer: Any,
    name: str,
    attributes: Optional[Dict[str, Any]] = None,
    *,
    root: bool = False,
) -> Iterator[Any]:
    """创建统一 OTel Span，并以脱敏属性记录耗时和异常。"""
    started = time.perf_counter()
    span_context = None
    if root:
        from opentelemetry.context import Context

        span_context = Context()
    with tracer.start_as_current_span(
        name,
        context=span_context,
        record_exception=False,
        set_status_on_exception=False,
    ) as span:
        set_span_attributes(
            span,
            {
                **(attributes or {}),
                "request.id": (attributes or {}).get("request.id") or get_request_id(),
            },
        )
        try:
            yield span
        except BaseException as exc:
            set_span_attributes(span, {"operation.status": "error"})
            mark_span_error(span, exc)
            raise
        else:
            set_span_attributes(
                span,
                {
                    "operation.status": "success",
                    "operation.duration_seconds": time.perf_counter() - started,
                },
            )


def trace_operation(*, name: str, component: str) -> Callable:
    """使用纯 OpenTelemetry 装饰同步或异步操作，不采集输入输出正文。"""

    def decorator(function: Callable) -> Callable:
        tracer = get_tracer(function.__module__)

        if inspect.iscoroutinefunction(function):

            @functools.wraps(function)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                # 仅记录低敏元数据，避免 Prompt 和业务结果进入观测系统。
                with observed_span(
                    tracer,
                    name,
                    {
                        "observability.component": component,
                        "code.function.name": function.__qualname__,
                        **(_llm_span_attributes() if component == "llm" else {}),
                    },
                ) as span:
                    result = await function(*args, **kwargs)
                    if (
                        component == "llm"
                        and isinstance(result, tuple)
                        and len(result) >= 3
                    ):
                        set_span_attributes(
                            span,
                            {
                                "gen_ai.usage.input_tokens": result[-2],
                                "gen_ai.usage.output_tokens": result[-1],
                                "gen_ai.usage.total_tokens": result[-2] + result[-1],
                            },
                        )
                    return result

            return async_wrapper

        @functools.wraps(function)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            with observed_span(
                tracer,
                name,
                {
                    "observability.component": component,
                    "code.function.name": function.__qualname__,
                    **(_llm_span_attributes() if component == "llm" else {}),
                },
            ):
                return function(*args, **kwargs)

        return sync_wrapper

    return decorator


def init_tracing() -> None:
    """初始化 OpenTelemetry Trace、Metrics 和统一 OTLP exporter。"""
    global _initialized
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

    traces_otlp_enabled = _should_enable_otlp_exporter(
        settings.OTEL_EXPORTER_OTLP_TRACES_ENDPOINT, "traces"
    )
    metrics_otlp_enabled = _should_enable_otlp_exporter(
        settings.OTEL_EXPORTER_OTLP_METRICS_ENDPOINT, "metrics"
    )

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

        if traces_otlp_enabled:
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
            if metrics_otlp_enabled:
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
        traces_otlp_enabled,
        metrics_otlp_enabled,
    )
