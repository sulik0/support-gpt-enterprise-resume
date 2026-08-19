import time
import logging
from typing import Dict, Any

from src.llm.provider import llm_provider
from src.guardrails.response_filter import filter_response
from src.observability.metrics import (
    AGENT_EXECUTION_DURATION_SECONDS,
    QA_SCORE_HISTOGRAM,
)
from src.risk.engine import risk_engine

logger = logging.getLogger("supportgpt.agents.quality_assurance")


class QualityAssuranceAgent:
    """负责校验回复质量、事实一致性和潜在幻觉。

    在输出前执行内容泄露过滤，并生成 QA 评分与风险结论。
    """

    async def verify(self, state: Dict[str, Any]) -> Dict[str, Any]:
        start_time = time.time()
        logger.info(
            f"QA Agent started verifying response for ticket: {state.get('ticket_id')}"
        )

        if "Security threat" in "".join(state.get("errors", [])):
            return state

        query = (
            f"Subject: {state.get('subject')}\nDescription: {state.get('description')}"
        )
        citations = state.get("context_citations", [])
        raw_response = state.get("suggested_response", "")

        context_texts = [c.text for c in citations]

        try:
            # 1. Run LLM-based hallucination and quality evaluation
            qa_eval, in_tok, out_tok = await llm_provider.evaluate_qa(
                query=query, context=context_texts, response=raw_response
            )

            # Update metrics
            state["tokens_input"] = state.get("tokens_input", 0) + in_tok
            state["tokens_output"] = state.get("tokens_output", 0) + out_tok

            qa_score = qa_eval.get("qa_score", 0.0)
            hallucinated = qa_eval.get("hallucination_detected", False)

            # Observe score distribution
            QA_SCORE_HISTOGRAM.record(qa_score)

            # 2. Apply Output Guardrail Response Filtering
            filtered_response_text = filter_response(raw_response)
            if filtered_response_text != raw_response:
                logger.warning(
                    "Response guardrail triggered: leaked instructions were scrubbed."
                )
                # Force high priority/escalation or low QA score if a leak occurred
                qa_score = 0.5
                hallucinated = True

            duration = time.time() - start_time
            AGENT_EXECUTION_DURATION_SECONDS.record(
                duration, {"agent_name": "quality_assurance"}
            )

            next_state = {
                **state,
                "suggested_response": filtered_response_text,
                "qa_score": qa_score,
                "hallucination_detected": hallucinated,
                "errors": state.get("errors", [])
                + (
                    ["QA score alert: potential hallucination detected."]
                    if hallucinated
                    else []
                ),
            }
            assessment = risk_engine.assess(next_state, stage="output")
            return {**next_state, **assessment.state_updates()}

        except Exception as e:
            logger.error(f"Error executing QA evaluation in QA agent: {e}")
            next_state = {
                **state,
                "qa_score": 0.5,
                "hallucination_detected": True,
                "errors": state.get("errors", []) + [f"QA agent error: {str(e)}"],
            }
            assessment = risk_engine.assess(next_state, stage="output")
            return {**next_state, **assessment.state_updates()}


quality_assurance_agent = QualityAssuranceAgent()
