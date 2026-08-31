from types import SimpleNamespace

import pytest
from fastapi import HTTPException

from src.tools.action_state_machine import (
    ToolActionCommand,
    ToolActionStatus,
    tool_action_state_machine,
)


def test_tool_action_state_machine_accepts_only_legal_lifecycle():
    action = SimpleNamespace(status=ToolActionStatus.PROPOSED, version=1)

    tool_action_state_machine.transition(action, ToolActionCommand.REQUEST_APPROVAL)
    tool_action_state_machine.transition(action, ToolActionCommand.APPROVE)
    tool_action_state_machine.transition(action, ToolActionCommand.START_EXECUTION)
    tool_action_state_machine.transition(action, ToolActionCommand.SUCCEED)

    assert action.status == ToolActionStatus.SUCCEEDED
    assert action.version == 5


def test_tool_action_state_machine_rejects_skipped_approval_and_terminal_replay():
    action = SimpleNamespace(status=ToolActionStatus.PROPOSED, version=1)
    with pytest.raises(HTTPException) as skipped:
        tool_action_state_machine.transition(action, ToolActionCommand.START_EXECUTION)
    assert skipped.value.status_code == 409

    action.status = ToolActionStatus.SUCCEEDED
    action.version = 5
    with pytest.raises(HTTPException) as replayed:
        tool_action_state_machine.transition(action, ToolActionCommand.START_EXECUTION)
    assert replayed.value.status_code == 409
    assert action.version == 5


def test_unknown_write_outcome_can_only_enter_reconciliation():
    action = SimpleNamespace(status=ToolActionStatus.UNKNOWN, version=6)

    transition = tool_action_state_machine.transition(
        action, ToolActionCommand.START_RECONCILIATION
    )

    assert transition.target == ToolActionStatus.RECONCILING
    assert action.version == 7
