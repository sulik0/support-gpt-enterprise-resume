"""DecisionProvider 的类型化输入输出。"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping


@dataclass(frozen=True)
class DecisionAnswer:
    """保存单个 Choice、Score 或 Noul 的标准化结果。"""

    kind: str
    value: str | float
    probabilities: Mapping[str, float] = field(default_factory=dict)
    confidence: float | None = None


@dataclass(frozen=True)
class DecisionResult:
    """保存一次决策模型调用的可审计摘要。"""

    enabled: bool
    available: bool
    provider: str
    operation: str
    question_set_version: str
    model: str
    answers: Mapping[str, DecisionAnswer] = field(default_factory=dict)
    input_tokens: int = 0
    output_tokens: int = 0
    latency_seconds: float = 0.0
    error_code: str | None = None

    def audit_record(
        self, *, accepted: bool, fallback_reason: str | None = None
    ) -> dict[str, Any]:
        """不写入原始 State，只记录版本、结果和置信度。"""
        return {
            "provider": self.provider,
            "operation": self.operation,
            "question_set_version": self.question_set_version,
            "model": self.model,
            "available": self.available,
            "accepted": accepted,
            "fallback_reason": fallback_reason,
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "latency_seconds": self.latency_seconds,
            "error_code": self.error_code,
            "answers": {
                key: {
                    "kind": answer.kind,
                    "value": answer.value,
                    "probabilities": dict(answer.probabilities),
                    "confidence": answer.confidence,
                }
                for key, answer in self.answers.items()
            },
        }


@dataclass(frozen=True)
class TicketIntentDecision:
    """将通用决策结果映射为 Analyzer 可消费的分类。"""

    result: DecisionResult
    accepted: bool
    analysis: Mapping[str, Any] | None = None
    fallback_reason: str | None = None


@dataclass(frozen=True)
class QAReviewDecision:
    """将通用决策结果映射为 QA 结构化评判。"""

    result: DecisionResult
    accepted: bool
    evaluation: Mapping[str, Any] | None = None
    fallback_reason: str | None = None
