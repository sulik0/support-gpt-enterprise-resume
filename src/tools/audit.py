"""持久化 Tool 调用审计，只保存脱敏摘要与关联标识。"""

import uuid
from typing import Any, Iterable, Optional

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.config import settings
from src.models.db_models import ToolInvocationAudit
from src.observability.tracing import get_current_trace_id, get_request_id
from src.tools.audit_context import capture_tool_audit
from src.tools.payload_security import tool_payload_security


class ToolAuditRepository:
    """构建可追溯审计记录，并支持请求内批量落库。"""

    def build_record(
        self,
        *,
        tool_name: str,
        tool_version: str,
        operation_type: str,
        risk_level: str,
        payload: dict[str, Any],
        role: str,
        allowed: bool,
        status: str,
        attempts: int,
        latency_ms: float,
        mocked: bool,
        ticket_id: Optional[int] = None,
        actor_user_id: Optional[int] = None,
        action_id: Optional[str] = None,
        error_type: Optional[str] = None,
        result: Any = None,
        policy_version: Optional[str] = None,
    ) -> dict[str, Any]:
        """不保存原始参数和原始异常，避免审计表成为敏感数据副本。"""
        return {
            "id": str(uuid.uuid4()),
            "tool_action_id": action_id,
            "ticket_id": ticket_id,
            "request_id": get_request_id() or "unbound",
            "trace_id": get_current_trace_id(),
            "tool_name": tool_name,
            "tool_version": tool_version,
            "operation_type": operation_type,
            "risk_level": risk_level,
            "actor_user_id": actor_user_id,
            "actor_role": role,
            "allowed": allowed,
            "status": status,
            "attempts": attempts,
            "latency_ms": latency_ms,
            "mocked": mocked,
            "error_type": error_type,
            "payload_hash": tool_payload_security.payload_hash(payload),
            "payload_keys": sorted(str(key) for key in payload),
            "result_summary": (
                tool_payload_security.result_summary(result)
                if result is not None
                else None
            ),
            "policy_version": policy_version or settings.TOOL_POLICY_VERSION,
        }

    async def record(
        self,
        record: dict[str, Any],
        db: Optional[AsyncSession] = None,
    ) -> None:
        if db is None:
            capture_tool_audit(record)
            return
        db.add(ToolInvocationAudit(**record))
        await db.flush()

    async def persist_many(
        self, db: AsyncSession, records: Iterable[dict[str, Any]]
    ) -> int:
        items = list(records)
        if not items:
            return 0
        db.add_all(ToolInvocationAudit(**item) for item in items)
        await db.flush()
        return len(items)

    async def list_records(
        self,
        db: AsyncSession,
        *,
        limit: int,
        offset: int,
        tool_name: Optional[str] = None,
        status: Optional[str] = None,
        action_id: Optional[str] = None,
    ) -> tuple[list[ToolInvocationAudit], int]:
        filters = []
        if tool_name:
            filters.append(ToolInvocationAudit.tool_name == tool_name)
        if status:
            filters.append(ToolInvocationAudit.status == status)
        if action_id:
            filters.append(ToolInvocationAudit.tool_action_id == action_id)

        count_query = select(func.count(ToolInvocationAudit.id)).where(*filters)
        total = int((await db.execute(count_query)).scalar_one())
        query = (
            select(ToolInvocationAudit)
            .where(*filters)
            .order_by(ToolInvocationAudit.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        records = list((await db.execute(query)).scalars().all())
        return records, total


tool_audit_repository = ToolAuditRepository()
