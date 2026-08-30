"""在当前 Agent Node 内收集脱敏降级事件。"""

from contextvars import ContextVar, Token

from src.resilience.models import DependencyEvent


_events: ContextVar[list[DependencyEvent] | None] = ContextVar(
    "supportgpt_resilience_events", default=None
)


def begin_resilience_scope() -> Token:
    """为单个 Node 创建独立的事件容器。"""
    return _events.set([])


def finish_resilience_scope(token: Token) -> list[DependencyEvent]:
    """返回当前 Node 事件并恢复上下文。"""
    events = list(_events.get() or [])
    _events.reset(token)
    return events


def record_resilience_event(event: DependencyEvent) -> None:
    """只将对业务有影响的 Retry/Fallback/失败写入 State。"""
    events = _events.get()
    if events is not None and event.noteworthy:
        events.append(event)
