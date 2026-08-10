"""Optional LangSmith tracing decorators with privacy-aware serialization."""

import re
from typing import Any, Callable

try:
    from langsmith import traceable as _langsmith_traceable
except ImportError:  # pragma: no cover - base runtime may omit optional SDK
    _langsmith_traceable = None


_EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
_PHONE_PATTERN = re.compile(r"(?<!\d)(?:\+?\d[\d\s-]{7,}\d)(?!\d)")
_SENSITIVE_KEYS = {
    "api_key",
    "authorization",
    "password",
    "secret",
    "access_token",
    "refresh_token",
}


def _redact_text(value: str) -> str:
    value = _EMAIL_PATTERN.sub("[REDACTED_EMAIL]", value)
    return _PHONE_PATTERN.sub("[REDACTED_PHONE]", value)


def sanitize_trace_value(value: Any) -> Any:
    """Return a JSON-friendly, PII-reduced view without mutating business data."""
    if isinstance(value, str):
        return _redact_text(value)
    if isinstance(value, dict):
        sanitized = {}
        for key, item in value.items():
            key_text = str(key)
            if key_text.lower() in _SENSITIVE_KEYS or key_text.lower().endswith("_api_key"):
                sanitized[key_text] = "[REDACTED]"
            else:
                sanitized[key_text] = sanitize_trace_value(item)
        return sanitized
    if isinstance(value, (list, tuple, set)):
        return [sanitize_trace_value(item) for item in value]
    if hasattr(value, "model_dump"):
        return sanitize_trace_value(value.model_dump())
    if isinstance(value, (bool, int, float)) or value is None:
        return value
    # Avoid serializing provider/registry instances and other internal objects.
    return f"<{value.__class__.__name__}>"


def _process_inputs(inputs: dict[str, Any]) -> dict[str, Any]:
    return sanitize_trace_value({key: value for key, value in inputs.items() if key != "self"})


def traceable(*, name: str, run_type: str) -> Callable:
    """Use LangSmith when installed; otherwise preserve the original callable."""
    if _langsmith_traceable is None:
        return lambda function: function
    return _langsmith_traceable(
        name=name,
        run_type=run_type,
        process_inputs=_process_inputs,
        process_outputs=sanitize_trace_value,
        tags=["supportgpt", "phase-1-evaluation"],
    )
