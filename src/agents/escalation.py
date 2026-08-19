import time
import logging
from typing import Dict, Any

from src.config import settings
from src.observability.metrics import (
    AGENT_EXECUTION_DURATION_SECONDS,
    RISK_ASSESSMENTS_TOTAL,
    RISK_SCORE_HISTOGRAM,
    TICKET_ESCALATIONS_TOTAL,
)
from src.risk.engine import risk_engine

logger = logging.getLogger("supportgpt.agents.escalation")


class EscalationAgent:
    """负责根据优先级、情绪和 QA 结果判断是否升级人工。

    同时计算当前工单对应的 SLA 处理时限。
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
        assessment = risk_engine.assess(state, stage="final")

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
        elif "qa_score_below_threshold" in assessment.reasons or hallucination_detected:
            escalate = True
            reason = (
                f"AI quality assurance score ({qa_score}) below threshold "
                f"({settings.RISK_QA_SCORE_THRESHOLD}) or hallucination detected."
            )
        elif assessment.requires_human:
            escalate = True
            reasons = ", ".join(assessment.reasons) or "policy threshold"
            reason = f"Risk Engine classified ticket as {assessment.level}: {reasons}."

        # 3. Handle telemetry updates
        try:
            RISK_ASSESSMENTS_TOTAL.add(
                1,
                {
                    "level": assessment.level,
                    "requires_human": str(assessment.requires_human).lower(),
                },
            )
            RISK_SCORE_HISTOGRAM.record(
                assessment.score,
                {"stage": "final", "level": assessment.level},
            )
        except Exception:
            logger.debug("Unable to record Risk Engine metrics")
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
            **assessment.state_updates(),
            "escalation_recommended": escalate,
            "escalation_reason": reason if escalate else None,
            "sla_hours": sla_hours,
        }


escalation_agent = EscalationAgent()
