import time
import datetime
import logging
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from fastapi import HTTPException, status

from src.models.db_models import ResponseApproval, Ticket
from src.models.schemas import ResponseApprovalRequest
from src.tickets.state_machine import TicketAction, TicketStatus, ticket_state_machine

logger = logging.getLogger("supportgpt.approval.workflows")

class HumanInTheLoopService:
    """
    Manages AI response validation, edits, approvals, and latency tracking.
    """
    async def create_pending_approval(
        self, 
        db: AsyncSession, 
        ticket_id: int, 
        drafted_response: str
    ) -> ResponseApproval:
        """Create a pending response approval ticket."""
        ticket_result = await db.execute(select(Ticket).filter(Ticket.id == ticket_id))
        ticket = ticket_result.scalars().first()
        if not ticket:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Ticket {ticket_id} not found.",
            )

        ticket_state_machine.transition(ticket, TicketAction.REQUEST_APPROVAL)

        approval = ResponseApproval(
            ticket_id=ticket_id,
            drafted_response=drafted_response,
            status="pending",
            created_at=datetime.datetime.utcnow()
        )
        db.add(approval)
        await db.commit()
        await db.refresh(approval)
        logger.info(f"Created pending approval ID {approval.id} for ticket ID {ticket_id}")
        return approval

    async def get_pending_approvals(self, db: AsyncSession) -> list[ResponseApproval]:
        """Fetch all response approvals currently pending review."""
        result = await db.execute(select(ResponseApproval).filter(ResponseApproval.status == "pending"))
        return list(result.scalars().all())

    async def process_agent_approval(
        self, 
        db: AsyncSession, 
        approval_id: int, 
        agent_id: int,
        req: ResponseApprovalRequest
    ) -> ResponseApproval:
        """
        Approve, reject, or edit an AI draft.
        Tracks response latency between AI generation and human review.
        """
        result = await db.execute(select(ResponseApproval).filter(ResponseApproval.id == approval_id))
        approval = result.scalars().first()
        
        if not approval:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Approval record {approval_id} not found."
            )
            
        if approval.status != "pending":
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Approval record {approval_id} has already been processed (status: {approval.status})."
            )

        # Calculate latency in seconds
        now = datetime.datetime.utcnow()
        delta = now - approval.created_at
        latency = delta.total_seconds()

        # Update record
        approval.status = req.status
        approval.agent_id = agent_id
        approval.latency_seconds = latency
        
        if req.modified_response:
            approval.modified_response = req.modified_response
        else:
            approval.modified_response = approval.drafted_response

        ticket_result = await db.execute(select(Ticket).filter(Ticket.id == approval.ticket_id))
        ticket = ticket_result.scalars().first()
        if ticket:
            if ticket.status in {TicketStatus.OPEN, TicketStatus.IN_PROGRESS}:
                ticket_state_machine.transition(ticket, TicketAction.REQUEST_APPROVAL)
            if req.status == "approved":
                ticket_state_machine.transition(ticket, TicketAction.APPROVE_RESPONSE)
            elif req.status == "modified":
                ticket_state_machine.transition(ticket, TicketAction.MODIFY_RESPONSE)
            elif req.status == "rejected":
                ticket_state_machine.transition(ticket, TicketAction.REJECT_RESPONSE)

        await db.commit()
        await db.refresh(approval)
        logger.info(f"Processed approval ID {approval_id} with status {req.status} by agent {agent_id}.")
        return approval

human_it_loop_service = HumanInTheLoopService()
