import time
import logging
from typing import Dict, Any

from src.llm.provider import llm_provider
from src.guardrails.pii_detection import anonymize_pii
from src.guardrails.prompt_injection import detect_prompt_injection
from src.guardrails.jailbreak_detection import detect_jailbreak
from src.observability.metrics import (
    AGENT_EXECUTION_DURATION_SECONDS,
    TICKET_SENTIMENT_TOTAL,
)

logger = logging.getLogger("supportgpt.agents.analyzer")


class TicketAnalyzerAgent:
    """
    Scans incoming support requests, filters via guardrails (PII, Injection, Jailbreaks),
    and determines sentiment, urgency, classification category, and routing.
    """

    async def analyze(self, state: Dict[str, Any]) -> Dict[str, Any]:
        start_time = time.time()
        logger.info(f"Analyzer Node started for customer: {state.get('customer_id')}")

        original_text = state.get("description", "")
        subject = state.get("subject", "")
        combined_text = f"Subject: {subject}\nDescription: {original_text}"

        # 1. Security Check: Prompt Injection
        if detect_prompt_injection(combined_text):
            logger.warning("Prompt injection detected by guardrails.")
            return {
                **state,
                "errors": state.get("errors", [])
                + ["Security threat: Prompt injection attempt detected."],
                "sentiment": "negative",
                "priority": "urgent",
                "escalation_recommended": True,
                "escalation_reason": "Security violation block",
                "suggested_response": "I cannot fulfill this request due to system security constraints.",
            }

        # 2. Security Check: Jailbreak Detection
        if detect_jailbreak(combined_text):
            logger.warning("Jailbreak pattern detected by guardrails.")
            return {
                **state,
                "errors": state.get("errors", [])
                + ["Security threat: Jailbreak vector detected."],
                "sentiment": "negative",
                "priority": "urgent",
                "escalation_recommended": True,
                "escalation_reason": "Security violation block",
                "suggested_response": "I cannot fulfill this request due to system security constraints.",
            }

        # 3. Privacy Scrubbing: Anonymize PII
        clean_description = anonymize_pii(original_text)
        clean_subject = anonymize_pii(subject)

        # 4. Perform LLM analysis
        try:
            analysis, in_tok, out_tok = await llm_provider.analyze_ticket(
                f"Subject: {clean_subject}\nDescription: {clean_description}"
            )

            # Increment token and latency stats
            state["tokens_input"] = state.get("tokens_input", 0) + in_tok
            state["tokens_output"] = state.get("tokens_output", 0) + out_tok

            # Track sentiment through OpenTelemetry Metrics.
            TICKET_SENTIMENT_TOTAL.add(
                1, {"sentiment": analysis.get("sentiment", "neutral")}
            )

            # Record execution latency
            duration = time.time() - start_time
            AGENT_EXECUTION_DURATION_SECONDS.record(
                duration, {"agent_name": "ticket_analyzer"}
            )

            return {
                **state,
                "description": clean_description,
                "subject": clean_subject,
                "sentiment": analysis.get("sentiment", "neutral"),
                "priority": analysis.get("priority", "medium"),
                "intent": analysis.get("intent", "general_query"),
                "department": analysis.get("department", "general"),
                "errors": state.get("errors", []),
            }
        except Exception as e:
            logger.error(f"Error executing LLM ticket analysis: {e}")
            return {
                **state,
                "errors": state.get("errors", []) + [f"Analyzer agent error: {str(e)}"],
                "sentiment": "neutral",
                "priority": "medium",
                "department": "general",
            }


ticket_analyzer_agent = TicketAnalyzerAgent()
