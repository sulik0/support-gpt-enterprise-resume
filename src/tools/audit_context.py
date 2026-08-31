"""在并行 Tool 执行期间收集审计，由请求主会话统一落库。"""

from contextvars import ContextVar, Token
from typing import Any


_audit_records: ContextVar[list[dict[str, Any]] | None] = ContextVar(
    "supportgpt_tool_audit_records", default=None
)


def begin_tool_audit_scope() -> Token:
    return _audit_records.set([])


def capture_tool_audit(record: dict[str, Any]) -> bool:
    records = _audit_records.get()
    if records is None:
        return False
    records.append(record)
    return True


def finish_tool_audit_scope(token: Token) -> list[dict[str, Any]]:
    records = list(_audit_records.get() or [])
    _audit_records.reset(token)
    return records
