import json

import pytest

from src.evaluation.baseline_error_analysis import (
    build_baseline_error_analysis,
    write_baseline_error_analysis,
)


def _case(
    case_id,
    *,
    passed,
    checks,
    expected,
    actual,
    trace_id,
    failures,
):
    return {
        "id": case_id,
        "dataset_case": {"query": f"query for {case_id}"},
        "trace_id": trace_id,
        "behavior_evaluation": {
            "passed": passed,
            "checks": checks,
            "expected": expected,
            "actual": actual,
            "failures": failures,
        },
    }


def _report():
    common_expected = {
        "department": "billing",
        "required_tools": ["crm", "orders"],
        "forbidden_tools": ["refund_execute"],
        "hitl": True,
        "approval": True,
    }
    return {
        "schema_version": "1.1",
        "evaluation_type": "baseline_workflow_replay_v1",
        "run_id": "20260827_120000",
        "generated_at": "2026-08-27T12:00:00+00:00",
        "dataset": "evaluation/baseline/supportgpt_baseline_100.json",
        "case_count": 3,
        "cases": [
            _case(
                "fail-intent-tool-hitl",
                passed=False,
                checks={
                    "intent_accuracy": 0.0,
                    "department_accuracy": 1.0,
                    "required_tool_hit_rate": 0.5,
                    "forbidden_tool_violation_rate": 0.0,
                    "hitl_accuracy": 0.0,
                    "approval_accuracy": 1.0,
                },
                expected={**common_expected, "intent": "billing_dispute"},
                actual={
                    "intent": "information_request",
                    "department": "billing",
                    "tools": ["crm"],
                    "hitl": False,
                    "approval": True,
                },
                trace_id="a" * 32,
                failures=[
                    "intent expected=billing_dispute actual=information_request",
                    "missing required tools: orders",
                    "HITL expected=True actual=False",
                ],
            ),
            _case(
                "fail-forbidden-approval",
                passed=False,
                checks={
                    "intent_accuracy": 1.0,
                    "department_accuracy": 1.0,
                    "required_tool_hit_rate": 1.0,
                    "forbidden_tool_violation_rate": 1.0,
                    "hitl_accuracy": 1.0,
                    "approval_accuracy": 0.0,
                },
                expected={**common_expected, "intent": "billing_dispute"},
                actual={
                    "intent": "billing_dispute",
                    "department": "billing",
                    "tools": ["crm", "orders", "refund_execute"],
                    "hitl": True,
                    "approval": False,
                },
                trace_id="b" * 32,
                failures=[
                    "forbidden tools called: refund_execute",
                    "approval expected=True actual=False",
                ],
            ),
            _case(
                "pass-case-must-not-appear",
                passed=True,
                checks={
                    "intent_accuracy": 1.0,
                    "department_accuracy": 1.0,
                    "required_tool_hit_rate": 1.0,
                    "forbidden_tool_violation_rate": 0.0,
                    "hitl_accuracy": 1.0,
                    "approval_accuracy": 1.0,
                },
                expected={**common_expected, "intent": "billing_dispute"},
                actual={
                    "intent": "billing_dispute",
                    "department": "billing",
                    "tools": ["crm", "orders"],
                    "hitl": True,
                    "approval": True,
                },
                trace_id="c" * 32,
                failures=[],
            ),
        ],
    }


def test_error_analysis_is_deterministic_and_only_contains_failed_cases():
    report = _report()

    first = build_baseline_error_analysis(report, "baseline_snapshot.json")
    second = build_baseline_error_analysis(report, "baseline_snapshot.json")

    assert first == second
    assert "FAIL Cases：2" in first
    assert "Failure Breakdown" in first
    assert "Intent Confusion Matrix" in first
    assert "HITL / Approval Mismatch" in first
    assert "Tool 问题" in first
    assert "fail-intent-tool-hitl" in first
    assert "fail-forbidden-approval" in first
    assert "pass-case-must-not-appear" not in first
    assert "missing required tools: orders" in first
    assert "refund_execute" in first
    assert "`" + "a" * 32 + "`" in first
    assert '"intent": "information_request"' in first


def test_error_analysis_writes_matching_snapshot_and_regular_latest(tmp_path):
    source = tmp_path / "baseline_v1_20260827_120000.json"
    source.write_text(json.dumps(_report()), encoding="utf-8")

    paths = write_baseline_error_analysis(source)

    assert paths["snapshot"].name == "error_analysis_20260827_120000.md"
    assert paths["latest"].name == "error_analysis_latest.md"
    assert paths["latest"].is_symlink() is False
    assert paths["snapshot"].read_bytes() == paths["latest"].read_bytes()


def test_error_analysis_refuses_to_overwrite_changed_snapshot(tmp_path):
    source = tmp_path / "baseline_v1_20260827_120000.json"
    source.write_text(json.dumps(_report()), encoding="utf-8")
    paths = write_baseline_error_analysis(source)
    paths["snapshot"].write_text("changed", encoding="utf-8")

    with pytest.raises(FileExistsError, match="immutable snapshot"):
        write_baseline_error_analysis(source)
