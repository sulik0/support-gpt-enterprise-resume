import time
import logging
from typing import Dict, Any

from src.config import settings
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

        query = str(state.get("description", ""))
        citations = state.get("context_citations", [])
        raw_response = state.get("suggested_response", "")
        filtered_response_text = filter_response(raw_response)
        context_texts = self._compact_context(citations)

        try:
            # 确定性失败直接阻断，有证据的回复才交给轻量 Judge。
            rule_result = self._rule_failure(
                raw_response=raw_response,
                filtered_response=filtered_response_text,
                has_context=bool(context_texts),
            )
            if rule_result is None:
                qa_eval, in_tok, out_tok = await llm_provider.evaluate_qa(
                    query=query,
                    context=context_texts,
                    response=filtered_response_text,
                )
                strategy = "llm"
            else:
                qa_eval = rule_result
                in_tok = 0
                out_tok = 0
                strategy = "rule"

            # Update metrics
            state["tokens_input"] = state.get("tokens_input", 0) + in_tok
            state["tokens_output"] = state.get("tokens_output", 0) + out_tok

            qa_score = qa_eval.get("score", qa_eval.get("qa_score", 0.0))
            hallucinated = qa_eval.get("hallucination_detected", False)
            citation_verified = qa_eval.get("citation_verified", False)

            # Observe score distribution
            QA_SCORE_HISTOGRAM.record(qa_score)

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
                "citation_verified": citation_verified,
                "qa_strategy": strategy,
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

    @staticmethod
    def _compact_context(citations: list[Any]) -> list[str]:
        """只保留最相关的两条证据并限制总长度。"""
        remaining = settings.LLM_QA_MAX_CONTEXT_CHARS
        context = []
        for index, citation in enumerate(citations[:2], start=1):
            source = str(getattr(citation, "source", f"doc-{index}"))
            prefix = f"[S{index}] {source}: "
            text = prefix + str(getattr(citation, "text", ""))[
                : max(remaining - len(prefix), 0)
            ]
            if not text:
                continue
            context.append(text)
            remaining -= len(text)
            if remaining <= 0:
                break
        return context

    @staticmethod
    def _rule_failure(
        *, raw_response: str, filtered_response: str, has_context: bool
    ) -> Dict[str, Any] | None:
        """对空回复、泄露和无证据回复执行确定性失败。"""
        if not raw_response.strip():
            return {
                "score": 0.0,
                "hallucination_detected": True,
                "citation_verified": False,
            }
        if filtered_response != raw_response:
            return {
                "score": 0.5,
                "hallucination_detected": True,
                "citation_verified": False,
            }
        if not has_context:
            return {
                "score": 0.45,
                "hallucination_detected": True,
                "citation_verified": False,
            }
        return None


quality_assurance_agent = QualityAssuranceAgent()
