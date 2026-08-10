"""LangSmith tracing paired with matching OpenTelemetry spans."""

import functools
import inspect
import time
from typing import Any, Callable

from src.observability.sanitization import sanitize_value
from src.observability.tracing import (
    get_request_id,
    get_tracer,
    mark_span_error,
    set_span_attributes,
)

try:
    from langsmith import traceable as _langsmith_traceable
except ImportError:  # pragma: no cover - base runtime may omit optional SDK
    _langsmith_traceable = None


def sanitize_trace_value(value: Any) -> Any:
    """Return a JSON-friendly, PII-reduced view without mutating business data."""
    return sanitize_value(value)


def _process_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    return sanitize_trace_value({key: value for key, value in inputs.items() if key != "self"})


def traceable(*, name: str, run_type: str) -> Callable:
    """Create equivalent LangSmith and OTel spans without changing return values."""
    def decorator(function: Callable) -> Callable:
        langsmith_function = function
        if _langsmith_traceable is not None:
            langsmith_function = _langsmith_traceable(
                name=name,
                run_type=run_type,
                process_inputs=_process_inputs,
                process_outputs=sanitize_trace_value,
                tags=["supportgpt", "observability-phase-1"],
            )(function)

        tracer = get_tracer(function.__module__)

        if inspect.iscoroutinefunction(function):
            @functools.wraps(function)
            async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
                started = time.perf_counter()
                with tracer.start_as_current_span(name) as span:
                    set_span_attributes(
                        span,
                        {
                            "langsmith.trace.name": name,
                            "langsmith.span.kind": run_type,
                            "observability.component": "agent",
                            "request.id": get_request_id(),
                            "langsmith.metadata.request_id": get_request_id(),
                        },
                    )
                    try:
                        result = await langsmith_function(*args, **kwargs)
                        set_span_attributes(
                            span,
                            {
                                "operation.status": "success",
                                "operation.duration_seconds": time.perf_counter() - started,
                            },
                        )
                        return result
                    except BaseException as exc:
                        set_span_attributes(span, {"operation.status": "error"})
                        mark_span_error(span, exc)
                        raise

            return async_wrapper

        @functools.wraps(function)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            started = time.perf_counter()
            with tracer.start_as_current_span(name) as span:
                set_span_attributes(
                    span,
                    {
                        "langsmith.trace.name": name,
                        "langsmith.span.kind": run_type,
                        "observability.component": "agent",
                        "request.id": get_request_id(),
                        "langsmith.metadata.request_id": get_request_id(),
                    },
                )
                try:
                    result = langsmith_function(*args, **kwargs)
                    set_span_attributes(
                        span,
                        {
                            "operation.status": "success",
                            "operation.duration_seconds": time.perf_counter() - started,
                        },
                    )
                    return result
                except BaseException as exc:
                    set_span_attributes(span, {"operation.status": "error"})
                    mark_span_error(span, exc)
                    raise

        return sync_wrapper

    return decorator
