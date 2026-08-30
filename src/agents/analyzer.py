import logging
import re
import time
from typing import Any, Dict

from src.guardrails.jailbreak_detection import detect_jailbreak
from src.guardrails.pii_detection import anonymize_pii
from src.guardrails.prompt_injection import analyze_prompt_injection
from src.guardrails.qwen3_guard import merge_qwen3_guard_result, qwen3_guard
from src.guardrails.security_policy import build_security_block
from src.llm.provider import llm_provider
from src.models.intents import (
    DEFAULT_INTENT,
    IntentType,
    intent_defaults,
    normalize_intent,
)
from src.observability.metrics import (
    AGENT_EXECUTION_DURATION_SECONDS,
    TICKET_SENTIMENT_TOTAL,
)
from src.observability.sanitization import redact_text
from src.risk.engine import risk_engine

logger = logging.getLogger("supportgpt.agents.analyzer")

_BILLING_DOMAIN = re.compile(
    r"\b(refund|payment|invoice|billing|charged?|card payment|bank statement)\b|"
    r"退款|支付|发票|账单|扣款|银行卡"
)
_API_INCIDENT = re.compile(
    r"(?:\bapi\b|接口|服务).{0,50}"
    r"(?:\b504\b|\b503\b|error|timeout|timing out|down|offline|crash|broken|"
    r"connectivity|slow|报错|超时|宕机|离线|无法访问|故障|缓慢)|"
    r"(?:\b504\b|\b503\b|报错|超时|宕机|故障).{0,30}(?:\bapi\b|接口|服务)"
)
_ORDER_STATUS = re.compile(
    r"\b(track|tracking|shipping status|delivery status|order status|where is (?:my )?order|"
    r"has been delivered|current status of order|package has not arrived|not received)\b|"
    r"订单状态|物流|快递|查询订单|订单.*(?:签收|配送)|包裹.*未到"
)
_CANCELLATION_ACTION = re.compile(
    r"\b(?:please |need to |want to |help me )?cancel (?:my |this |the )?order\b|"
    r"请?.{0,6}取消.{0,4}订单"
)
_CANCELLATION_INFORMATION = re.compile(
    r"\b(if i cancel|cancellation fee|cancel an order before|can .* cancel|"
    r"order cancellation policy)\b|取消订单.{0,12}(?:费用|政策|是否|能否)"
)
_ACCOUNT_INCIDENT = re.compile(
    r"\b(?:cannot|can't|unable to) (?:log ?in|sign ?in)|account (?:is )?locked|"
    r"invalid credentials|login keeps failing\b|无法登录|账户被锁|凭据失效"
)
_WARRANTY_ACTION = re.compile(
    r"\b(?:file|open|start|submit) (?:a )?(?:warranty )?claim\b|"
    r"\b(?:repair|replace) my (?:device|hardware|item)\b|"
    r"申请保修|发起维修|维修我的|更换我的"
)
_FEEDBACK = re.compile(r"\bthank you\b|\bthanks\b|\bgreat service\b|谢谢|感谢")


class TicketAnalyzerAgent:
    """负责分析客服请求并执行输入侧安全检查。

    输出情绪、优先级、意图和业务部门，供后续节点路由使用。
    """

    async def analyze(self, state: Dict[str, Any]) -> Dict[str, Any]:
        start_time = time.time()
        logger.info(f"Analyzer Node started for customer: {state.get('customer_id')}")

        original_text = state.get("description", "")
        subject = state.get("subject", "")
        combined_text = f"Subject: {subject}\nDescription: {original_text}"

        # 1. 使用多层检测阻断直接 Prompt Injection。
        injection = analyze_prompt_injection(combined_text, source="user_input")
        if injection.detected:
            logger.warning(
                "Prompt injection detected by layered guardrails",
                extra={
                    "ticket_id": state.get("ticket_id"),
                    "risk_score": injection.risk_score,
                    "security_source": injection.source,
                },
            )
            return build_security_block(
                state,
                threat_type="Prompt injection attempt",
                source=injection.source,
                risk_score=injection.risk_score,
                findings=[*injection.layers, *injection.signals],
            )

        # 2. Security Check: Jailbreak Detection
        if detect_jailbreak(combined_text):
            logger.warning("Jailbreak pattern detected by guardrails.")
            return build_security_block(
                state,
                threat_type="Jailbreak vector",
                source="user_input",
                risk_score=0.95,
                findings=["jailbreak_signature"],
            )

        # 3. 调用外部模型前先移除客户 PII。
        clean_description = anonymize_pii(original_text)
        clean_subject = anonymize_pii(subject)
        semantic_text = redact_text(
            f"Subject: {clean_subject}\nDescription: {clean_description}"
        )

        # 4. 规则通过后再使用 Qwen3Guard 检测语义风险。
        semantic_result = await qwen3_guard.classify(semantic_text, source="user_input")
        state = merge_qwen3_guard_result(state, semantic_result)
        if semantic_result.block_recommended:
            return build_security_block(
                state,
                threat_type="Qwen3Guard semantic safety violation",
                source=semantic_result.source,
                risk_score=semantic_result.policy_score,
                findings=[
                    f"semantic_severity:{semantic_result.severity}",
                    *(
                        f"semantic_category:{item}"
                        for item in semantic_result.categories
                    ),
                ],
            )

        # 5. 高置信度固定意图优先走规则，模糊请求再调用 LLM。
        try:
            analysis = (
                None
                if semantic_result.degraded
                else self._match_rule(clean_description or clean_subject)
            )
            strategy = "rule" if analysis else "llm"
            in_tok = 0
            out_tok = 0
            if analysis is None:
                analysis, in_tok, out_tok = await llm_provider.analyze_ticket(
                    f"Subject: {clean_subject}\nDescription: {clean_description}"
                )

            # 所有分类结果在进入 State 前统一收敛到 IntentType。
            raw_intent = analysis.get("intent")
            normalized_intent = normalize_intent(raw_intent)
            intent_is_known = isinstance(raw_intent, IntentType) or (
                str(raw_intent).strip().lower() in IntentType.values()
            )
            analyzer_confidence = self._confidence(
                analysis.get("confidence_score", analysis.get("confidence", 0.0))
            )
            if not intent_is_known:
                analyzer_confidence = min(analyzer_confidence, 0.5)

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

            defaults = intent_defaults(normalized_intent)
            next_state = {
                **state,
                "description": clean_description,
                "subject": clean_subject,
                "sentiment": analysis.get("sentiment", "neutral"),
                "priority": defaults.priority,
                "intent": normalized_intent,
                "department": defaults.department,
                "analyzer_confidence": analyzer_confidence,
                "analyzer_strategy": strategy,
                "errors": state.get("errors", []),
            }
            assessment = risk_engine.assess(next_state, stage="input")
            return {**next_state, **assessment.state_updates()}
        except Exception as e:
            logger.error(f"Error executing LLM ticket analysis: {e}")
            next_state = {
                **state,
                "errors": state.get("errors", []) + [f"Analyzer agent error: {str(e)}"],
                "sentiment": "neutral",
                "priority": "medium",
                "department": "general",
                "intent": DEFAULT_INTENT,
                "analyzer_confidence": 0.0,
            }
            assessment = risk_engine.assess(next_state, stage="input")
            return {**next_state, **assessment.state_updates()}

    @staticmethod
    def _match_rule(text: str) -> Dict[str, Any] | None:
        """先区分实际业务操作与说明性咨询，歧义才交给 LLM。"""
        normalized = " ".join(text.lower().split())
        candidates: list[IntentType] = []
        if _BILLING_DOMAIN.search(normalized):
            candidates.append(IntentType.BILLING_DISPUTE)
            if _ORDER_STATUS.search(normalized):
                candidates.append(IntentType.ORDER_STATUS)
        elif _API_INCIDENT.search(normalized):
            candidates.append(IntentType.OUTAGE_REPORT)
        else:
            if _CANCELLATION_ACTION.search(normalized) and not _CANCELLATION_INFORMATION.search(
                normalized
            ):
                candidates.append(IntentType.ORDER_CANCELLATION)
            if _ORDER_STATUS.search(normalized):
                candidates.append(IntentType.ORDER_STATUS)
            if _ACCOUNT_INCIDENT.search(normalized):
                candidates.append(IntentType.ACCOUNT_SUPPORT)
            if _WARRANTY_ACTION.search(normalized):
                candidates.append(IntentType.WARRANTY_CLAIM)
            if _FEEDBACK.search(normalized):
                candidates.append(IntentType.FEEDBACK)

        if len(set(candidates)) > 1:
            return None
        intent = candidates[0] if candidates else IntentType.INFORMATION_REQUEST
        defaults = intent_defaults(intent)
        return {
            "intent": intent,
            "priority": defaults.priority,
            "department": defaults.department,
            "sentiment": (
                "negative"
                if intent
                in {
                    IntentType.BILLING_DISPUTE,
                    IntentType.OUTAGE_REPORT,
                    IntentType.ORDER_CANCELLATION,
                    IntentType.ACCOUNT_SUPPORT,
                }
                else "positive" if intent == IntentType.FEEDBACK else "neutral"
            ),
            "confidence_score": 0.95,
        }

    @staticmethod
    def _confidence(value: Any) -> float:
        """将 LLM 分类置信度约束在 0 到 1。"""
        try:
            return min(max(float(value), 0.0), 1.0)
        except (TypeError, ValueError):
            return 0.0


ticket_analyzer_agent = TicketAnalyzerAgent()
