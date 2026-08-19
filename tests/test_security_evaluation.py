from types import SimpleNamespace

import pytest

from scripts.import_evaluation_feedback import build_feedback_evaluation
from src.evaluation.security_evaluation import (
    SecurityExpectations,
    evaluate_security_records,
)


def _record(
    case_id,
    *,
    tags=None,
    security_expectations=None,
    output=None,
    workflow_path=None,
):
    """构造安全专项评测所需的最小 Replay 记录。"""
    return SimpleNamespace(
        case=SimpleNamespace(
            id=case_id,
            tags=tags or [],
            security_expectations=security_expectations or {},
        ),
        contexts=[],
        workflow_path=workflow_path or [],
        workflow_output=output or {},
    )


def _blocked_output(*, source="user_input"):
    return {
        "security_threat_detected": True,
        "security_source": source,
        "risk_block_automation": True,
        "risk_level": "critical",
        "context_citations": [],
        "tool_context": {},
        "escalation_recommended": True,
        "approval_required": True,
    }


def test_security_metrics_build_confusion_matrix_and_disposition_rates():
    attack = _record(
        "attack",
        tags=["prompt_injection"],
        output=_blocked_output(),
        workflow_path=["ticket_analyzer", "escalation"],
    )
    business_escalation = _record(
        "refund-review",
        tags=["refund", "human_escalation"],
        output={
            "security_threat_detected": False,
            "escalation_recommended": True,
            "approval_required": True,
            "risk_level": "high",
        },
        workflow_path=["ticket_analyzer", "tool_call", "retriever", "escalation"],
    )

    summary, results = evaluate_security_records([attack, business_escalation])

    assert summary["confusion_matrix"] == {
        "true_positive": 1,
        "false_positive": 0,
        "true_negative": 1,
        "false_negative": 0,
    }
    assert summary["detection"] == {
        "precision": 1.0,
        "recall": 1.0,
        "f1_score": 1.0,
        "accuracy": 1.0,
        "false_positive_rate": 0.0,
        "false_negative_rate": 0.0,
    }
    assert all(value == 1.0 for value in summary["disposition"].values())
    assert summary["case_pass_rate"] == 1.0
    assert results["refund-review"].classification == "true_negative"


def test_security_metrics_expose_false_positive_and_false_negative():
    missed_attack = _record(
        "missed",
        tags=["jailbreak"],
        output={"security_threat_detected": False},
        workflow_path=["ticket_analyzer", "llm_generation", "qa", "escalation"],
    )
    false_alarm = _record(
        "false-alarm",
        output=_blocked_output(),
        workflow_path=["ticket_analyzer", "escalation"],
    )

    summary, results = evaluate_security_records([missed_attack, false_alarm])

    assert summary["confusion_matrix"]["false_positive"] == 1
    assert summary["confusion_matrix"]["false_negative"] == 1
    assert summary["detection"]["precision"] == 0.0
    assert summary["detection"]["recall"] == 0.0
    assert summary["detection"]["f1_score"] == 0.0
    assert results["missed"].passed is False
    assert results["false-alarm"].passed is False


def test_security_metrics_validate_indirect_source_and_safe_short_circuit():
    indirect_attack = _record(
        "tool-attack",
        security_expectations={
            "expected_attack": True,
            "attack_type": "indirect_prompt_injection",
            "expected_source": "tool_result",
            "should_block": True,
        },
        output=_blocked_output(source="tool_result"),
        workflow_path=["ticket_analyzer", "tool_call", "escalation"],
    )

    summary, results = evaluate_security_records([indirect_attack])

    assert results["tool-attack"].passed is True
    assert summary["source_breakdown"]["tool_result"] == {
        "cases": 1,
        "detected": 1,
        "recall": 1.0,
    }


def test_security_expectations_reject_unknown_fields():
    case = SimpleNamespace(
        tags=[], security_expectations={"expected_attack": True, "typo": "value"}
    )

    with pytest.raises(ValueError, match="Unknown security_expectations"):
        SecurityExpectations.from_case(case)


def test_security_failure_blocks_evaluation_feedback_training_candidate():
    case = {
        "rag_evaluation": {
            "citation_hit": True,
            "metrics": {
                "faithfulness": 1.0,
                "answer_relevancy": 1.0,
                "context_precision": 1.0,
                "context_recall": 1.0,
            },
        },
        "agent_evaluation": {"passed": True, "metrics": {"workflow": 1.0}},
        "security_evaluation": {
            "passed": False,
            "classification": "false_negative",
        },
    }

    metrics, passed = build_feedback_evaluation(case)

    assert passed is False
    assert metrics["security"]["classification"] == "false_negative"
