"""定义依赖故障、降级等级与执行结果。"""

from dataclasses import dataclass
from enum import Enum
from typing import Any, Generic, Optional, TypeVar


T = TypeVar("T")


class DependencyErrorType(str, Enum):
    """统一归类外部依赖故障，避免业务层解析异常文本。"""

    TIMEOUT = "timeout"
    RATE_LIMIT = "rate_limit"
    CONNECTION = "connection"
    SERVER = "server_error"
    AUTH = "auth_error"
    VALIDATION = "validation_error"
    MALFORMED_RESPONSE = "malformed_response"
    CIRCUIT_OPEN = "circuit_open"
    UNKNOWN = "unknown"


class DegradationLevel(str, Enum):
    """表示依赖故障对当前 Agent 请求的影响。"""

    NONE = "none"
    PARTIAL = "partial"
    HUMAN_REQUIRED = "human_required"
    FAILED = "failed"


DEGRADATION_RANK = {
    DegradationLevel.NONE.value: 0,
    DegradationLevel.PARTIAL.value: 1,
    DegradationLevel.HUMAN_REQUIRED.value: 2,
    DegradationLevel.FAILED.value: 3,
}


class OperationType(str, Enum):
    """区分可安全重试的读操作与默认不重试的写操作。"""

    READ = "read"
    WRITE = "write"


@dataclass(frozen=True)
class ResiliencePolicy:
    """描述单个依赖操作的超时、重试和熔断策略。"""

    timeout_seconds: float
    max_retries: int = 0
    operation_type: OperationType = OperationType.READ
    idempotent: bool = True
    circuit_failure_threshold: int = 3
    circuit_recovery_seconds: float = 30.0
    failure_degradation: DegradationLevel = DegradationLevel.PARTIAL

    def __post_init__(self) -> None:
        if self.timeout_seconds <= 0:
            raise ValueError("timeout_seconds must be greater than zero")
        if self.max_retries < 0:
            raise ValueError("max_retries cannot be negative")
        if (
            self.operation_type is OperationType.WRITE
            and not self.idempotent
            and self.max_retries > 0
        ):
            raise ValueError("non-idempotent write operations cannot be retried")


@dataclass(frozen=True)
class DependencyEvent:
    """保存可写入 State/Trace 的脱敏依赖执行摘要。"""

    component: str
    operation: str
    status: str
    attempts: int
    latency_ms: float
    degradation_level: DegradationLevel = DegradationLevel.NONE
    error_type: Optional[DependencyErrorType] = None
    fallback_used: Optional[str] = None
    circuit_state: str = "closed"

    @property
    def noteworthy(self) -> bool:
        return (
            self.status != "success"
            or self.attempts > 1
            or self.fallback_used is not None
        )

    def as_dict(self) -> dict[str, Any]:
        """仅序列化类型与状态，不向 State 写入原始异常。"""
        return {
            "component": self.component,
            "operation": self.operation,
            "status": self.status,
            "attempts": self.attempts,
            "latency_ms": self.latency_ms,
            "degradation_level": self.degradation_level.value,
            "error_type": self.error_type.value if self.error_type else None,
            "fallback_used": self.fallback_used,
            "circuit_state": self.circuit_state,
        }


@dataclass
class ResilienceResult(Generic[T]):
    """统一返回主调用、Retry 或 Fallback 的执行结果。"""

    success: bool
    value: Optional[T]
    event: DependencyEvent
    cause: Optional[BaseException] = None

    def unwrap(self) -> T:
        if self.success:
            return self.value  # type: ignore[return-value]
        raise ResilienceExhaustedError(self.event, self.cause)


class ResilienceExhaustedError(RuntimeError):
    """表示依赖在有界恢复后仍不可用。"""

    def __init__(
        self, event: DependencyEvent, cause: Optional[BaseException] = None
    ) -> None:
        self.event = event
        self.cause = cause
        super().__init__(
            f"{event.component}.{event.operation} failed: "
            f"{event.error_type.value if event.error_type else 'unknown'}"
        )
