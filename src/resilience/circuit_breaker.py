"""提供进程内 Circuit Breaker，快速隔离持续失败的依赖。"""

import asyncio
import time
from dataclasses import dataclass


class CircuitOpenError(RuntimeError):
    """表示调用因熔断开启而被快速拒绝。"""


@dataclass
class _CircuitEntry:
    failures: int = 0
    state: str = "closed"
    opened_at: float = 0.0
    probe_in_flight: bool = False


class CircuitBreakerRegistry:
    """按 dependency key 管理进程内熔断状态。"""

    def __init__(self) -> None:
        self._entries: dict[str, _CircuitEntry] = {}
        self._lock = asyncio.Lock()

    async def before_call(self, key: str, recovery_seconds: float) -> str:
        """关闭态放行，超过恢复窗口时只放行一个探测请求。"""
        async with self._lock:
            entry = self._entries.setdefault(key, _CircuitEntry())
            if entry.state == "half_open" and entry.probe_in_flight:
                raise CircuitOpenError(key)
            if entry.state != "open":
                return entry.state
            if time.monotonic() - entry.opened_at < recovery_seconds:
                raise CircuitOpenError(key)
            if entry.probe_in_flight:
                raise CircuitOpenError(key)
            entry.state = "half_open"
            entry.probe_in_flight = True
            return entry.state

    async def record_success(self, key: str) -> str:
        async with self._lock:
            entry = self._entries.setdefault(key, _CircuitEntry())
            previous = entry.state
            entry.failures = 0
            entry.state = "closed"
            entry.opened_at = 0.0
            entry.probe_in_flight = False
            return previous

    async def record_failure(self, key: str, threshold: int) -> str:
        async with self._lock:
            entry = self._entries.setdefault(key, _CircuitEntry())
            entry.failures += 1
            entry.probe_in_flight = False
            if entry.state == "half_open" or entry.failures >= threshold:
                entry.state = "open"
                entry.opened_at = time.monotonic()
            return entry.state

    async def clear(self) -> None:
        """仅供测试和运维恢复场景重置进程内状态。"""
        async with self._lock:
            self._entries.clear()


circuit_breakers = CircuitBreakerRegistry()
