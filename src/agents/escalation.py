import time
import logging
from typing import Dict, Any

from src.observability.metrics import (
    AGENT_EXECUTION_DURATION_SECONDS,
    TICKET_ESCALATIONS_TOTAL,
)

logger = logging.getLogger("supportgpt.agents.escalation")


class EscalationAgent:
    """
    Evaluates SLA parameters, inspects QA evaluation scores, and suggests routing
    escalation if the AI resolution fails confidence checks.
    """

    async def evaluate(self, state: Dict[str, Any]) -> Dict[str, Any]:
        start_time = time.time()
        logger.info(
            f"Escalation Agent started verifying state rules for ticket: {state.get('ticket_id')}"
        )

        priority = state.get("priority", "medium").lower()
        sentiment = state.get("sentiment", "neutral").lower()
        qa_score = state.get("qa_score", 1.0)
        hallucination_detected = state.get("hallucination_detected", False)
        department = state.get("department", "general")
        errors = state.get("errors", [])

        # 1. Map SLA window based on ticket priority
        sla_hours = 24.0  # default medium
        if priority == "urgent":
            sla_hours = 2.0
        elif priority == "high":
            sla_hours = 12.0
        elif priority == "medium":
            sla_hours = 24.0
        elif priority == "low":
            sla_hours = 48.0

        # 2. Check escalation criteria
        escalate = False
        reason = ""

        if "Security threat" in "".join(errors):
            escalate = True
            reason = "Security guardrails violation block."
        elif priority == "urgent":
            escalate = True
            reason = "Ticket designated as Urgent priority."
        elif sentiment == "negative" and priority == "high":
            escalate = True
            reason = "Negative customer sentiment combined with high priority."
        elif qa_score < 0.8 or hallucination_detected:
            escalate = True
            reason = f"AI quality assurance score ({qa_score}) below threshold (0.8) or hallucination detected."

        # 3. Handle telemetry updates
        if escalate:
            TICKET_ESCALATIONS_TOTAL.add(
                1, {"department": department, "priority": priority}
            )
            logger.info(f"Escalation recommended for ticket: {reason}")

        duration = time.time() - start_time
        AGENT_EXECUTION_DURATION_SECONDS.record(
            duration, {"agent_name": "escalation_agent"}
        )

        return {
            **state,
            "escalation_recommended": escalate,
            "escalation_reason": reason if escalate else None,
            "sla_hours": sla_hours,
        }


escalation_agent = EscalationAgent()
