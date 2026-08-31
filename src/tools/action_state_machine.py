"""高风险 Tool Action 的确定性状态机。"""

import datetime
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, status


class ToolActionStatus:
    """集中定义高风险动作的生命周期状态。"""

    PROPOSED = "proposed"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    REJECTED = "rejected"
    EXECUTING = "executing"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    UNKNOWN = "unknown"
    RECONCILING = "reconciling"


class ToolActionCommand:
    """定义唯一允许触发状态迁移的业务命令。"""

    REQUEST_APPROVAL = "request_approval"
    APPROVE = "approve"
    REJECT = "reject"
    START_EXECUTION = "start_execution"
    SUCCEED = "succeed"
    FAIL = "fail"
    MARK_UNKNOWN = "mark_unknown"
    START_RECONCILIATION = "start_reconciliation"
    RECONCILE_SUCCESS = "reconcile_success"
    RECONCILE_FAILURE = "reconcile_failure"


@dataclass(frozen=True)
class ToolActionTransition:
    """保存状态机已执行的一次迁移。"""

    source: str
    target: str
    command: str


class ToolActionStateMachine:
    """拒绝跳过审批、重复执行或终态修改。"""

    transitions = {
        ToolActionStatus.PROPOSED: {
            ToolActionCommand.REQUEST_APPROVAL: ToolActionStatus.PENDING_APPROVAL,
        },
        ToolActionStatus.PENDING_APPROVAL: {
            ToolActionCommand.APPROVE: ToolActionStatus.APPROVED,
            ToolActionCommand.REJECT: ToolActionStatus.REJECTED,
        },
        ToolActionStatus.APPROVED: {
            ToolActionCommand.START_EXECUTION: ToolActionStatus.EXECUTING,
        },
        ToolActionStatus.EXECUTING: {
            ToolActionCommand.SUCCEED: ToolActionStatus.SUCCEEDED,
            ToolActionCommand.FAIL: ToolActionStatus.FAILED,
            ToolActionCommand.MARK_UNKNOWN: ToolActionStatus.UNKNOWN,
        },
        ToolActionStatus.UNKNOWN: {
            ToolActionCommand.START_RECONCILIATION: ToolActionStatus.RECONCILING,
        },
        ToolActionStatus.RECONCILING: {
            ToolActionCommand.RECONCILE_SUCCESS: ToolActionStatus.SUCCEEDED,
            ToolActionCommand.RECONCILE_FAILURE: ToolActionStatus.FAILED,
        },
    }

    def transition(self, action: Any, command: str) -> ToolActionTransition:
        source = str(action.status)
        target = self.transitions.get(source, {}).get(command)
        if not target:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": "Illegal Tool Action transition.",
                    "current_status": source,
                    "requested_command": command,
                    "allowed_commands": sorted(self.transitions.get(source, {})),
                },
            )
        action.status = target
        action.version = int(action.version or 0) + 1
        action.updated_at = datetime.datetime.utcnow()
        return ToolActionTransition(source=source, target=target, command=command)


tool_action_state_machine = ToolActionStateMachine()
