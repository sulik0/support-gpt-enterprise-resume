from enum import Enum
from typing import Any


class IntentType(str, Enum):
    """定义客服 Workflow 唯一允许使用的意图集合。

    规则、LLM、Tool、Risk Engine 和 Evaluation 均应引用本枚举。
    """

    BILLING_DISPUTE = "billing_dispute"
    OUTAGE_REPORT = "outage_report"
    ORDER_CANCELLATION = "order_cancellation"
    ORDER_STATUS = "order_status"
    ACCOUNT_SUPPORT = "account_support"
    WARRANTY_CLAIM = "warranty_claim"
    FEEDBACK = "feedback"
    INFORMATION_REQUEST = "information_request"

    def __str__(self) -> str:
        """确保日志、Prompt 与持久化摘要始终使用枚举值。"""
        return self.value

    @classmethod
    def values(cls) -> tuple[str, ...]:
        """返回可直接写入 Prompt 或 Dataset 的稳定枚举值。"""
        return tuple(item.value for item in cls)


DEFAULT_INTENT = IntentType.INFORMATION_REQUEST


def normalize_intent(value: Any) -> IntentType:
    """将外部或 LLM 意图归一化，未知值统一降级为通用咨询。"""
    if isinstance(value, IntentType):
        return value
    try:
        return IntentType(str(value).strip().lower())
    except (TypeError, ValueError):
        return DEFAULT_INTENT


def intent_prompt_values() -> str:
    """生成供不同 LLM Provider 共用的意图枚举约束。"""
    return "|".join(IntentType.values())
