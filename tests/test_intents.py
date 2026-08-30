from src.models.intents import (
    DEFAULT_INTENT,
    INTENT_TAXONOMY,
    IntentType,
    intent_defaults,
    intent_prompt_guide,
    intent_prompt_values,
    normalize_intent,
)


def test_intent_enum_is_the_single_canonical_set():
    """规则、Prompt 和 State 使用的枚举值应保持稳定且无重复。"""
    expected = {
        "billing_dispute",
        "outage_report",
        "order_cancellation",
        "order_status",
        "account_support",
        "warranty_claim",
        "feedback",
        "information_request",
    }

    assert set(IntentType.values()) == expected
    assert set(intent_prompt_values().split("|")) == expected
    assert set(INTENT_TAXONOMY) == set(IntentType)
    assert "information_request" in intent_prompt_guide()
    assert intent_defaults(IntentType.OUTAGE_REPORT).department == "technical"


def test_unknown_intent_is_normalized_to_the_only_fallback():
    """模型自由生成的新标签不得进入 Agent Workflow。"""
    assert normalize_intent("order_status") is IntentType.ORDER_STATUS
    assert normalize_intent(IntentType.FEEDBACK) is IntentType.FEEDBACK
    assert normalize_intent("refund_after_delivery_issue") is DEFAULT_INTENT
