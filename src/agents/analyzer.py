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
from src.models.intents import DEFAULT_INTENT, IntentType, normalize_intent
from src.observability.metrics import (
    AGENT_EXECUTION_DURATION_SECONDS,
    TICKET_SENTIMENT_TOTAL,
)
from src.observability.sanitization import redact_text
from src.risk.engine import risk_engine

logger = logging.getLogger("supportgpt.agents.analyzer")

_INTENT_RULES = (
    {
        "intent": IntentType.BILLING_DISPUTE,
        "priority": "high",
        "department": "billing",
        "sentiment": "negative",
        "tokens": (
            "refund",
            "request a refund",
            "need a refund",
            "want a refund",
            "charged twice",
            "duplicate charge",
            "incorrect charge",
            "unauthorized charge",
            "退款",
            "申请退款",
            "重复扣款",
            "错误扣款",
            "未授权扣款",
        ),
    },
    {
        "intent": IntentType.OUTAGE_REPORT,
        "priority": "urgent",
        "department": "technical",
        "sentiment": "negative",
        "tokens": (
            "api is down",
            "service down",
            "offline",
            "service outage",
            "api timeout",
            "504",
            "503",
            "服务宕机",
            "接口故障",
            "接口超时",
            "服务无法访问",
        ),
    },
    {
        "intent": IntentType.ORDER_CANCELLATION,
        "priority": "high",
        "department": "shipping",
        "sentiment": "negative",
        "tokens": (
            "cancel my order",
            "cancel order",
            "order cancellation",
            "取消订单",
        ),
    },
    {
        "intent": IntentType.ORDER_STATUS,
        "priority": "medium",
        "department": "shipping",
        "sentiment": "neutral",
        "tokens": (
            "order status",
            "where is my order",
            "tracking number",
            "shipment",
            "delivery status",
            "not received",
            "物流",
            "快递",
            "订单状态",
            "还没收到",
            "没有收到",
        ),
    },
    {
        "intent": IntentType.ACCOUNT_SUPPORT,
        "priority": "medium",
        "department": "general",
        "sentiment": "neutral",
        "tokens": (
            "account settings",
            "reset password",
            "cannot login",
            "can't login",
            "update my profile",
            "账户设置",
            "账号设置",
            "重置密码",
            "无法登录",
            "修改资料",
        ),
    },
    {
        "intent": IntentType.WARRANTY_CLAIM,
        "priority": "medium",
        "department": "general",
        "sentiment": "neutral",
        "tokens": (
            "warranty",
            "repair",
            "replacement",
            "保修",
            "维修",
            "换货",
        ),
    },
    {
        "intent": IntentType.FEEDBACK,
        "priority": "low",
        "department": "general",
        "sentiment": "positive",
        "tokens": ("thank you", "thanks", "great service", "谢谢", "感谢"),
    },
)


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
                None if semantic_result.degraded else self._match_rule(semantic_text)
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

            next_state = {
                **state,
                "description": clean_description,
                "subject": clean_subject,
                "sentiment": analysis.get("sentiment", "neutral"),
                "priority": analysis.get("priority", "medium"),
                "intent": normalized_intent,
                "department": analysis.get("department", "general"),
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
        """仅在唯一意图组命中时返回高置信度分类。"""
        normalized = " ".join(text.lower().split())
        matches = [
            rule
            for rule in _INTENT_RULES
            if any(
                TicketAnalyzerAgent._contains_token(normalized, token)
                for token in rule["tokens"]
            )
        ]
        if len(matches) != 1:
            return None
        rule = matches[0]
        return {
            "intent": rule["intent"],
            "priority": rule["priority"],
            "department": rule["department"],
            "sentiment": rule["sentiment"],
            "confidence_score": 0.95,
        }

    @staticmethod
    def _contains_token(text: str, token: str) -> bool:
        """英文关键词使用单词边界，中文关键词使用子串匹配。"""
        if token.isascii():
            return bool(re.search(rf"(?<!\w){re.escape(token)}(?!\w)", text))
        return token in text

    @staticmethod
    def _confidence(value: Any) -> float:
        """将 LLM 分类置信度约束在 0 到 1。"""
        try:
            return min(max(float(value), 0.0), 1.0)
        except (TypeError, ValueError):
            return 0.0


ticket_analyzer_agent = TicketAnalyzerAgent()
