"""独立、确定性的 Agent Risk Engine。"""

from dataclasses import dataclass
from typing import Any, Literal, Mapping

from src.config import settings


_HIGH_RISK_INTENT_TOKENS = (
    "refund",
    "billing_dispute",
    "chargeback",
    "order_cancel",
    "cancellation",
    "compensation",
    "complaint",
    "account_deletion",
    "退款",
    "拒付",
    "取消订单",
    "补偿",
    "投诉",
    "删除账户",
)


@dataclass(frozen=True)
class RiskAssessment:
    """保存风险等级、分数、原因和自动化处置建议。"""

    level: str
    score: float
    reasons: tuple[str, ...]
    requires_human: bool
    block_automation: bool

    def state_updates(self) -> dict[str, Any]:
        return {
            "risk_level": self.level,
            "risk_score": self.score,
            "risk_reasons": list(self.reasons),
            "risk_requires_human": self.requires_human,
            "risk_block_automation": self.block_automation,
        }


class RiskEngine:
    """综合安全、业务、分类置信度和回复质量计算风险。"""

    def assess(
        self,
        state: Mapping[str, Any],
        *,
        stage: Literal["input", "output", "final"],
    ) -> RiskAssessment:
        """按处理阶段聚合已有风险信号，分数只升不降。"""
        score = float(state.get("risk_score", 0.0) or 0.0)
        reasons = set(str(item) for item in state.get("risk_reasons", []))
        errors = " ".join(str(item) for item in state.get("errors", []))
        security_threat = bool(state.get("security_threat_detected")) or (
            "Security threat" in errors
        )

        if security_threat:
            score = max(
                score, float(state.get("security_risk_score", 1.0) or 1.0), 0.95
            )
            reasons.add("security_threat_detected")

        priority = str(state.get("priority", "medium")).lower()
        sentiment = str(state.get("sentiment", "neutral")).lower()
        intent = str(state.get("intent", "general")).lower()
        analyzer_confidence = self._bounded_score(
            state.get("analyzer_confidence", 1.0), default=1.0
        )

        if priority == "urgent":
            score = max(score, 0.85)
            reasons.add("urgent_priority")
        elif priority == "high":
            score = max(score, 0.55)
            reasons.add("high_priority")

        if sentiment == "negative" and priority == "high":
            score = max(score, 0.75)
            reasons.add("negative_high_priority")

        if any(token in intent for token in _HIGH_RISK_INTENT_TOKENS):
            score = max(score, 0.78)
            reasons.add("high_risk_business_intent")

        if analyzer_confidence < settings.RISK_LOW_CONFIDENCE_THRESHOLD:
            score = max(score, 0.8)
            reasons.add("low_analyzer_confidence")
        elif analyzer_confidence < 0.8:
            score = max(score, 0.5)
            reasons.add("medium_analyzer_confidence")

        if stage in {"output", "final"}:
            qa_score = self._bounded_score(state.get("qa_score", 1.0), default=1.0)
            if bool(state.get("hallucination_detected", False)):
                score = max(score, 0.9)
                reasons.add("hallucination_detected")
            if qa_score < settings.RISK_QA_SCORE_THRESHOLD:
                score = max(score, 0.82 if qa_score >= 0.5 else 0.9)
                reasons.add("qa_score_below_threshold")

        non_security_errors = [
            item
            for item in state.get("errors", [])
            if "Security threat" not in str(item)
        ]
        if non_security_errors:
            score = max(score, 0.55)
            reasons.add("workflow_error")

        score = round(min(max(score, 0.0), 1.0), 4)
        if score >= settings.RISK_CRITICAL_THRESHOLD:
            level = "critical"
        elif score >= settings.RISK_HIGH_THRESHOLD:
            level = "high"
        elif score >= settings.RISK_MEDIUM_THRESHOLD:
            level = "medium"
        else:
            level = "low"

        return RiskAssessment(
            level=level,
            score=score,
            reasons=tuple(sorted(reasons)),
            requires_human=level in {"high", "critical"},
            block_automation=security_threat,
        )

    @staticmethod
    def _bounded_score(value: Any, *, default: float) -> float:
        try:
            return min(max(float(value), 0.0), 1.0)
        except (TypeError, ValueError):
            return default


risk_engine = RiskEngine()
