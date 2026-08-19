import pytest

from src.config import Settings
from src.risk.engine import RiskEngine


def test_risk_engine_keeps_normal_request_low_risk():
    assessment = RiskEngine().assess(
        {
            "priority": "medium",
            "sentiment": "neutral",
            "intent": "general_query",
            "analyzer_confidence": 0.95,
            "qa_score": 0.95,
        },
        stage="final",
    )

    assert assessment.level == "low"
    assert assessment.requires_human is False
    assert assessment.block_automation is False


def test_risk_engine_escalates_low_confidence_and_high_risk_business_intent():
    low_confidence = RiskEngine().assess(
        {"analyzer_confidence": 0.4, "priority": "medium"},
        stage="input",
    )
    refund = RiskEngine().assess(
        {"analyzer_confidence": 0.95, "intent": "refund_request"},
        stage="input",
    )

    assert low_confidence.level == "high"
    assert "low_analyzer_confidence" in low_confidence.reasons
    assert low_confidence.requires_human is True
    assert refund.level == "high"
    assert "high_risk_business_intent" in refund.reasons


def test_risk_engine_blocks_security_threat_and_flags_bad_output():
    security = RiskEngine().assess(
        {
            "security_threat_detected": True,
            "security_risk_score": 0.98,
        },
        stage="input",
    )
    bad_output = RiskEngine().assess(
        {"qa_score": 0.4, "hallucination_detected": True},
        stage="output",
    )

    assert security.level == "critical"
    assert security.block_automation is True
    assert security.requires_human is True
    assert bad_output.level == "critical"
    assert "hallucination_detected" in bad_output.reasons


def test_risk_engine_fuses_qwen3_guard_severity_and_degraded_context():
    controversial = RiskEngine().assess(
        {
            "semantic_guard_label": "controversial",
            "semantic_guard_categories": ["Unethical Acts"],
        },
        stage="input",
    )
    degraded_rag = RiskEngine().assess(
        {
            "semantic_guard_degraded": True,
            "semantic_guard_checks": [{"source": "rag_document", "status": "error"}],
        },
        stage="input",
    )

    assert controversial.level == "high"
    assert controversial.requires_human is True
    assert controversial.block_automation is False
    assert "semantic_safety_controversial" in controversial.reasons
    assert degraded_rag.level == "high"
    assert degraded_rag.requires_human is True
    assert "untrusted_context_guard_unavailable" in degraded_rag.reasons


def test_risk_thresholds_must_be_strictly_ordered():
    with pytest.raises(ValueError, match="medium < high < critical"):
        Settings(
            _env_file=None,
            RISK_MEDIUM_THRESHOLD=0.8,
            RISK_HIGH_THRESHOLD=0.7,
            RISK_CRITICAL_THRESHOLD=0.9,
        )
