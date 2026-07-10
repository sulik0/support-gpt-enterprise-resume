import pytest
from fastapi import HTTPException

from src.models.db_models import Ticket
from src.tickets.state_machine import TicketAction, TicketStatus, ticket_state_machine


def make_ticket(status: str = TicketStatus.OPEN) -> Ticket:
    return Ticket(
        customer_id="cust_101",
        subject="State transition",
        description="Check ticket lifecycle",
        status=status,
    )


def test_ticket_state_machine_approval_lifecycle():
    ticket = make_ticket()

    first = ticket_state_machine.transition(ticket, TicketAction.REQUEST_APPROVAL)
    assert first.source == TicketStatus.OPEN
    assert first.target == TicketStatus.PENDING_APPROVAL
    assert ticket.status == TicketStatus.PENDING_APPROVAL

    second = ticket_state_machine.transition(ticket, TicketAction.APPROVE_RESPONSE)
    assert second.source == TicketStatus.PENDING_APPROVAL
    assert second.target == TicketStatus.RESOLVED
    assert ticket.status == TicketStatus.RESOLVED

    third = ticket_state_machine.transition(ticket, TicketAction.CLOSE)
    assert third.source == TicketStatus.RESOLVED
    assert third.target == TicketStatus.CLOSED
    assert ticket.status == TicketStatus.CLOSED


def test_ticket_state_machine_rejects_illegal_transition():
    ticket = make_ticket(status=TicketStatus.OPEN)

    with pytest.raises(HTTPException) as exc:
        ticket_state_machine.transition(ticket, TicketAction.CLOSE)

    assert exc.value.status_code == 409
    assert ticket.status == TicketStatus.OPEN


def test_ticket_state_machine_rejection_returns_to_in_progress():
    ticket = make_ticket(status=TicketStatus.PENDING_APPROVAL)

    transition = ticket_state_machine.transition(ticket, TicketAction.REJECT_RESPONSE)

    assert transition.target == TicketStatus.IN_PROGRESS
    assert ticket.status == TicketStatus.IN_PROGRESS
