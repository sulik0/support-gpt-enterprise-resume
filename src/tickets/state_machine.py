import datetime
from dataclasses import dataclass
from typing import Dict, Set

from fastapi import HTTPException, status

from src.models.db_models import Ticket


class TicketStatus:
    OPEN = "open"
    IN_PROGRESS = "in_progress"
    PENDING_APPROVAL = "pending_approval"
    RESOLVED = "resolved"
    CLOSED = "closed"


class TicketAction:
    START_WORK = "start_work"
    REQUEST_APPROVAL = "request_approval"
    APPROVE_RESPONSE = "approve_response"
    MODIFY_RESPONSE = "modify_response"
    REJECT_RESPONSE = "reject_response"
    CLOSE = "close"
    REOPEN = "reopen"


@dataclass(frozen=True)
class Transition:
    source: str
    target: str
    action: str


class TicketStateMachine:
    """Controls legal ticket status transitions for the support workflow."""

    transitions: Dict[str, Dict[str, str]] = {
        TicketStatus.OPEN: {
            TicketAction.START_WORK: TicketStatus.IN_PROGRESS,
            TicketAction.REQUEST_APPROVAL: TicketStatus.PENDING_APPROVAL,
        },
        TicketStatus.IN_PROGRESS: {
            TicketAction.REQUEST_APPROVAL: TicketStatus.PENDING_APPROVAL,
        },
        TicketStatus.PENDING_APPROVAL: {
            TicketAction.APPROVE_RESPONSE: TicketStatus.RESOLVED,
            TicketAction.MODIFY_RESPONSE: TicketStatus.RESOLVED,
            TicketAction.REJECT_RESPONSE: TicketStatus.IN_PROGRESS,
        },
        TicketStatus.RESOLVED: {
            TicketAction.CLOSE: TicketStatus.CLOSED,
            TicketAction.REOPEN: TicketStatus.IN_PROGRESS,
        },
        TicketStatus.CLOSED: {
            TicketAction.REOPEN: TicketStatus.IN_PROGRESS,
        },
    }

    terminal_statuses: Set[str] = {TicketStatus.CLOSED}

    def transition(self, ticket: Ticket, action: str) -> Transition:
        current = ticket.status or TicketStatus.OPEN
        target = self.transitions.get(current, {}).get(action)
        if not target:
            allowed = sorted(self.transitions.get(current, {}).keys())
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail={
                    "message": "Illegal ticket status transition.",
                    "current_status": current,
                    "requested_action": action,
                    "allowed_actions": allowed,
                },
            )

        ticket.status = target
        ticket.updated_at = datetime.datetime.utcnow()
        return Transition(source=current, target=target, action=action)

    def allowed_actions(self, ticket: Ticket) -> list[str]:
        current = ticket.status or TicketStatus.OPEN
        return sorted(self.transitions.get(current, {}).keys())


ticket_state_machine = TicketStateMachine()
