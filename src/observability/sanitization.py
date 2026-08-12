"""Shared data protection for every observability backend."""

import re
from typing import Any, Dict


EMAIL_PATTERN = re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)
PHONE_PATTERN = re.compile(r"(?<!\d)(?:\+?\d[\d\s().-]{7,}\d)(?!\d)")
SSN_PATTERN = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
CREDIT_CARD_PATTERN = re.compile(r"\b(?:\d[ -]*?){13,19}\b")
INLINE_SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{12,}\b", re.IGNORECASE),
    re.compile(
        r"\b(?:api[_-]?key|access[_-]?token|password|secret)\s*[:=]\s*[^\s,;]+",
        re.IGNORECASE,
    ),
)

SECRET_KEYS = {
    "api_key",
    "authorization",
    "password",
    "secret",
    "access_token",
    "refresh_token",
    "cookie",
    "set-cookie",
}

SENSITIVE_BUSINESS_KEYS = {
    "address",
    "bank_account",
    "card_number",
    "credit_card",
    "customer_id",
    "customer_email",
    "customer_name",
    "drafted_response",
    "email",
    "items",
    "modified_response",
    "name",
    "order_id",
    "payment_details",
    "payment_method",
    "phone",
    "session_id",
    "ssn",
    "total_amount",
}


def redact_text(value: str) -> str:
    value = EMAIL_PATTERN.sub("[REDACTED_EMAIL]", value)
    value = PHONE_PATTERN.sub("[REDACTED_PHONE]", value)
    value = SSN_PATTERN.sub("[REDACTED_SSN]", value)
    value = CREDIT_CARD_PATTERN.sub("[REDACTED_CARD]", value)
    for pattern in INLINE_SECRET_PATTERNS:
        value = pattern.sub("[REDACTED_SECRET]", value)
    return value


def is_sensitive_key(key: str) -> bool:
    normalized = key.lower().replace("-", "_").replace(".", "_")
    return (
        normalized in SECRET_KEYS
        or normalized in SENSITIVE_BUSINESS_KEYS
        or normalized.endswith("_api_key")
        or normalized.endswith("_secret")
        or normalized.endswith("_password")
    )


def sanitize_value(value: Any) -> Any:
    """Create a telemetry-safe representation without changing business data."""
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, dict):
        sanitized: Dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            sanitized[key_text] = (
                "[FILTERED]" if is_sensitive_key(key_text) else sanitize_value(item)
            )
        return sanitized
    if isinstance(value, (list, tuple, set)):
        return [sanitize_value(item) for item in value]
    if hasattr(value, "model_dump"):
        return sanitize_value(value.model_dump())
    if isinstance(value, (bool, int, float)) or value is None:
        return value
    return f"<{value.__class__.__name__}>"


def sanitize_attributes(attributes: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize values to OpenTelemetry-compatible scalar/sequence attributes."""
    output: Dict[str, Any] = {}
    for key, value in attributes.items():
        if value is None:
            continue
        safe_value = "[FILTERED]" if is_sensitive_key(key) else sanitize_value(value)
        if isinstance(safe_value, (str, bool, int, float)):
            output[key] = safe_value
        elif isinstance(safe_value, list) and all(
            isinstance(item, (str, bool, int, float)) for item in safe_value
        ):
            output[key] = safe_value
        else:
            output[key] = str(safe_value)
    return output
