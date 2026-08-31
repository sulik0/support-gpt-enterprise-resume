"""高风险 Tool Action 的提议、审批、执行与查询服务。"""

import datetime
import uuid
from typing import Any, Optional

from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.config import settings
from src.models.db_models import Ticket, ToolAction, ToolActionEvent, User
from src.models.intents import normalize_intent
from src.observability.metrics import TOOL_ACTION_TRANSITIONS_TOTAL
from src.observability.sanitization import redact_text, sanitize_value
from src.observability.tracing import (
    get_current_trace_id,
    get_request_id,
    get_tracer,
    observed_span,
    set_span_attributes,
)
from src.resilience.models import OperationType
from src.tools.action_state_machine import (
    ToolActionCommand,
    ToolActionStatus,
    tool_action_state_machine,
)
from src.tools.contracts import ApprovedToolExecution
from src.tools.payload_security import tool_payload_security
from src.tools.registry import ROLE_RANK, ToolDefinition, tool_registry


tracer = get_tracer(__name__)
TRANSIENT_EXECUTION_ERRORS = {
    "timeout",
    "rate_limit",
    "connection",
    "server_error",
    "circuit_open",
    "unknown",
}


class ToolGovernanceService:
    """强制高风险写操作经过可追溯的职责分离审批。"""

    async def propose(
        self,
        db: AsyncSession,
        *,
        ticket_id: int,
        tool_name: str,
        payload: dict[str, Any],
        intent: str,
        proposer: User,
    ) -> ToolAction:
        definition = self._high_risk_write_definition(tool_name)
        ticket = await db.get(Ticket, ticket_id)
        if not ticket:
            raise HTTPException(status_code=404, detail="Ticket not found.")

        normalized_payload = self._validate_payload(definition, payload)
        normalized_intent = normalize_intent(intent)
        if (
            definition.allowed_intents is not None
            and normalized_intent not in definition.allowed_intents
        ):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tool is not allowed for the requested intent.",
            )
        if normalized_payload.get("customer_id") != ticket.customer_id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Tool payload does not belong to the ticket customer.",
            )

        now = datetime.datetime.utcnow()
        action = ToolAction(
            id=str(uuid.uuid4()),
            ticket_id=ticket.id,
            tool_name=definition.name,
            tool_version=definition.version,
            intent=str(normalized_intent),
            risk_level=definition.risk_level,
            operation_type=definition.operation_type.value,
            status=ToolActionStatus.PROPOSED,
            version=1,
            policy_version=settings.TOOL_POLICY_VERSION,
            payload_encrypted=tool_payload_security.encrypt(normalized_payload),
            payload_hash=tool_payload_security.payload_hash(normalized_payload),
            payload_summary=tool_payload_security.summary(normalized_payload),
            request_id=get_request_id() or uuid.uuid4().hex,
            trace_id=get_current_trace_id(),
            proposed_by_user_id=proposer.id,
            proposed_by_role=proposer.role,
            created_at=now,
            updated_at=now,
        )
        db.add(action)
        self._append_event(
            action,
            command="propose",
            source=None,
            target=ToolActionStatus.PROPOSED,
            actor=proposer,
        )
        transition = tool_action_state_machine.transition(
            action, ToolActionCommand.REQUEST_APPROVAL
        )
        self._append_transition(action, transition, proposer)
        await db.flush()
        await db.refresh(action, attribute_names=["events"])
        return action

    async def decide(
        self,
        db: AsyncSession,
        *,
        action_id: str,
        decision: str,
        expected_version: int,
        reviewer: User,
        comment: Optional[str] = None,
    ) -> ToolAction:
        action = await self._load_for_update(db, action_id)
        self._check_version(action, expected_version)
        if ROLE_RANK.get(reviewer.role, 0) < ROLE_RANK["manager"]:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Reviewer must have manager or admin role.",
            )
        if decision not in {"approved", "rejected"}:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Decision must be approved or rejected.",
            )
        if decision == "approved" and action.proposed_by_user_id == reviewer.id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Proposer cannot approve their own high-risk Tool Action.",
            )

        command = (
            ToolActionCommand.APPROVE
            if decision == "approved"
            else ToolActionCommand.REJECT
        )
        transition = tool_action_state_machine.transition(action, command)
        action.reviewed_by_user_id = reviewer.id
        action.reviewed_by_role = reviewer.role
        action.review_comment = redact_text(comment or "")[:1000] or None
        action.reviewed_at = datetime.datetime.utcnow()
        self._append_transition(action, transition, reviewer)
        await db.flush()
        return action

    async def execute(
        self,
        db: AsyncSession,
        *,
        action_id: str,
        expected_version: int,
        executor: User,
    ) -> ToolAction:
        action = await self._load_for_update(db, action_id)
        self._check_version(action, expected_version)
        definition = self._high_risk_write_definition(action.tool_name)
        if (
            action.tool_version != definition.version
            or action.policy_version != settings.TOOL_POLICY_VERSION
        ):
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Tool or policy version changed; create a new Action.",
            )
        if ROLE_RANK.get(executor.role, 0) < ROLE_RANK.get(definition.min_role, 999):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Executor role is not permitted for this Tool.",
            )

        payload = self._verified_payload(action, definition)
        ticket = await db.get(Ticket, action.ticket_id)
        if not ticket or payload.get("customer_id") != ticket.customer_id:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Tool Action no longer matches its ticket customer.",
            )
        transition = tool_action_state_machine.transition(
            action, ToolActionCommand.START_EXECUTION
        )
        action.executed_by_user_id = executor.id
        action.execution_started_at = datetime.datetime.utcnow()
        self._append_transition(action, transition, executor)
        # 先持久化 executing，再触发外部写操作，避免无记录副作用。
        await db.commit()

        grant = ApprovedToolExecution(
            action_id=action.id,
            tool_name=action.tool_name,
            payload_hash=action.payload_hash,
            approved_by_user_id=int(action.reviewed_by_user_id or 0),
        )
        with observed_span(
            tracer,
            "supportgpt.tool_action.execute",
            {
                "tool.action_id": action.id,
                "gen_ai.tool.name": action.tool_name,
                "ticket.id": action.ticket_id,
            },
        ) as span:
            try:
                result = await tool_registry.call_tool(
                    action.tool_name,
                    payload,
                    role=executor.role,
                    ticket_id=action.ticket_id,
                    intent=action.intent,
                    request_risk_level=action.risk_level,
                    actor_user_id=executor.id,
                    audit_db=db,
                    action_id=action.id,
                    execution_grant=grant,
                )
                if result.get("status") == "success":
                    command = ToolActionCommand.SUCCEED
                    action.result_summary = tool_payload_security.result_summary(
                        result.get("result")
                    )
                elif result.get("error_type") in TRANSIENT_EXECUTION_ERRORS:
                    command = ToolActionCommand.MARK_UNKNOWN
                    action.error_type = result.get("error_type") or "unknown"
                    action.failure_reason = (
                        "External write outcome requires reconciliation."
                    )
                else:
                    command = ToolActionCommand.FAIL
                    action.error_type = result.get("error_type") or str(
                        result.get("status") or "failed"
                    )
                    action.failure_reason = (
                        "Tool execution was rejected or failed deterministically."
                    )
                transition = tool_action_state_machine.transition(action, command)
                action.completed_at = datetime.datetime.utcnow()
                self._append_transition(
                    action,
                    transition,
                    executor,
                    details={"audit_id": result.get("audit_id")},
                )
                set_span_attributes(
                    span,
                    {
                        "tool.action.status": action.status,
                        "tool.audit_id": result.get("audit_id"),
                    },
                )
                await db.commit()
                return await self.get(db, action.id)
            except HTTPException:
                await db.rollback()
                raise
            except Exception as exc:
                await db.rollback()
                await self._mark_unknown_after_exception(db, action.id, executor, exc)
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail="Tool execution outcome is unknown and requires reconciliation.",
                ) from exc

    async def get(self, db: AsyncSession, action_id: str) -> ToolAction:
        query = (
            select(ToolAction)
            .options(selectinload(ToolAction.events))
            .where(ToolAction.id == action_id)
        )
        action = (await db.execute(query)).scalar_one_or_none()
        if not action:
            raise HTTPException(status_code=404, detail="Tool Action not found.")
        return action

    async def list_actions(
        self,
        db: AsyncSession,
        *,
        limit: int,
        offset: int,
        action_status: Optional[str] = None,
        tool_name: Optional[str] = None,
    ) -> tuple[list[ToolAction], int]:
        filters = []
        if action_status:
            filters.append(ToolAction.status == action_status)
        if tool_name:
            filters.append(ToolAction.tool_name == tool_name)
        total = int(
            (
                await db.execute(select(func.count(ToolAction.id)).where(*filters))
            ).scalar_one()
        )
        query = (
            select(ToolAction)
            .options(selectinload(ToolAction.events))
            .where(*filters)
            .order_by(ToolAction.created_at.desc())
            .limit(limit)
            .offset(offset)
        )
        return list((await db.execute(query)).scalars().all()), total

    async def _load_for_update(self, db: AsyncSession, action_id: str) -> ToolAction:
        query = (
            select(ToolAction)
            .options(selectinload(ToolAction.events))
            .where(ToolAction.id == action_id)
            .with_for_update()
        )
        action = (await db.execute(query)).scalar_one_or_none()
        if not action:
            raise HTTPException(status_code=404, detail="Tool Action not found.")
        return action

    @staticmethod
    def _check_version(action: ToolAction, expected_version: int) -> None:
        if action.version != expected_version:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": "Stale Tool Action version.",
                    "expected_version": expected_version,
                    "current_version": action.version,
                },
            )

    @staticmethod
    def _high_risk_write_definition(tool_name: str) -> ToolDefinition:
        definition = tool_registry.get_definition(tool_name)
        if not definition:
            raise HTTPException(status_code=404, detail="Tool is not registered.")
        if not (
            definition.risk_level == "high"
            and definition.operation_type is OperationType.WRITE
        ):
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Only high-risk write Tools use the Action approval workflow.",
            )
        return definition

    @staticmethod
    def _validate_payload(
        definition: ToolDefinition, payload: dict[str, Any]
    ) -> dict[str, Any]:
        try:
            return definition.input_schema(**payload).model_dump()
        except ValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Tool payload failed schema validation.",
            ) from exc

    @staticmethod
    def _verified_payload(
        action: ToolAction, definition: ToolDefinition
    ) -> dict[str, Any]:
        try:
            payload = tool_payload_security.decrypt(action.payload_encrypted)
        except ValueError as exc:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Tool Action payload failed integrity verification.",
            ) from exc
        if tool_payload_security.payload_hash(payload) != action.payload_hash:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Tool Action payload hash does not match.",
            )
        return ToolGovernanceService._validate_payload(definition, payload)

    def _append_transition(
        self,
        action: ToolAction,
        transition: Any,
        actor: User,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        self._append_event(
            action,
            command=transition.command,
            source=transition.source,
            target=transition.target,
            actor=actor,
            details=details,
        )
        try:
            TOOL_ACTION_TRANSITIONS_TOTAL.add(
                1,
                {
                    "command": transition.command,
                    "from_status": transition.source,
                    "to_status": transition.target,
                },
            )
        except Exception:
            pass

    @staticmethod
    def _append_event(
        action: ToolAction,
        *,
        command: str,
        source: Optional[str],
        target: str,
        actor: User,
        details: Optional[dict[str, Any]] = None,
    ) -> None:
        action.events.append(
            ToolActionEvent(
                id=str(uuid.uuid4()),
                sequence=len(action.events) + 1,
                action=command,
                from_status=source,
                to_status=target,
                actor_user_id=actor.id,
                actor_role=actor.role,
                request_id=get_request_id() or action.request_id,
                trace_id=get_current_trace_id(),
                details=sanitize_value(details or {}),
            )
        )

    async def _mark_unknown_after_exception(
        self,
        db: AsyncSession,
        action_id: str,
        executor: User,
        exc: Exception,
    ) -> None:
        action = await self._load_for_update(db, action_id)
        if action.status != ToolActionStatus.EXECUTING:
            return
        transition = tool_action_state_machine.transition(
            action, ToolActionCommand.MARK_UNKNOWN
        )
        action.error_type = exc.__class__.__name__[:80]
        action.failure_reason = "Execution interrupted; reconciliation is required."
        action.completed_at = datetime.datetime.utcnow()
        self._append_transition(action, transition, executor)
        await db.commit()


tool_governance_service = ToolGovernanceService()
