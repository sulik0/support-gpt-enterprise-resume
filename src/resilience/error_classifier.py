"""将 SDK 差异屏蔽在 Resilience 模块内。"""

import asyncio
import json
from typing import Any

from pydantic import ValidationError

from src.resilience.models import DependencyErrorType


_RETRYABLE = frozenset(
    {
        DependencyErrorType.TIMEOUT,
        DependencyErrorType.RATE_LIMIT,
        DependencyErrorType.CONNECTION,
        DependencyErrorType.SERVER,
    }
)


def classify_dependency_error(error: BaseException) -> DependencyErrorType:
    """优先根据异常类型，其次根据 HTTP status 归类。"""
    if isinstance(error, (asyncio.TimeoutError, TimeoutError)):
        return DependencyErrorType.TIMEOUT
    if isinstance(error, json.JSONDecodeError):
        return DependencyErrorType.MALFORMED_RESPONSE
    if isinstance(error, ValidationError):
        return DependencyErrorType.VALIDATION

    name = error.__class__.__name__.lower()
    if "ratelimit" in name:
        return DependencyErrorType.RATE_LIMIT
    if "timeout" in name:
        return DependencyErrorType.TIMEOUT
    if "connection" in name or "connect" in name:
        return DependencyErrorType.CONNECTION
    if "authentication" in name or "permission" in name:
        return DependencyErrorType.AUTH

    status = _status_code(error)
    if status == 429:
        return DependencyErrorType.RATE_LIMIT
    if status in {401, 403}:
        return DependencyErrorType.AUTH
    if status in {400, 404, 409, 422}:
        return DependencyErrorType.VALIDATION
    if status is not None and status >= 500:
        return DependencyErrorType.SERVER
    return DependencyErrorType.UNKNOWN


def is_retryable_error(error_type: DependencyErrorType) -> bool:
    return error_type in _RETRYABLE


def _status_code(error: BaseException) -> int | None:
    status: Any = getattr(error, "status_code", None)
    if status is None:
        response = getattr(error, "response", None)
        status = getattr(response, "status_code", None)
    try:
        return int(status) if status is not None else None
    except (TypeError, ValueError):
        return None
