import hashlib
import json
from pathlib import Path

from src.evaluation.quality_gate import (
    evaluate_quality_gate,
    load_json_object,
    write_quality_gate_report,
)


METRICS = [
    "intent_accuracy",
    "department_accuracy",
    "required_tool_hit_rate",
    "forbidden_tool_violation_rate",
    "hitl_accuracy",
    "approval_accuracy",
]
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _report(*, provider="mock", pass_rate=1.0, failed_ids=()):
    """构造包含门禁必要字段的最小 Baseline 报告。"""
    cases = [
        {
            "id": case_id,
            "behavior_evaluation": {"passed": case_id not in failed_ids},
        }
        for case_id in ("case-1", "case-2")
    ]
    return {
        "evaluation_type": "baseline_workflow_replay_v1",
        "run_id": "test-run",
        "case_count": 2,
        "enabled_behavior_metrics": METRICS,
        "execution": {"mode": "ci_offline_workflow_replay"},
        "experiment_config": {
            "dataset": {"sha256": "dataset-hash"},
            "workflow": {"source_revision": "a" * 40},
            "models": {"provider": provider},
        },
        "behavior_summary": {
            "intent_accuracy": 1.0,
            "case_pass_rate": pass_rate,
        },
        "cases": cases,
    }


def _policy(*, allowed_failed_ids=()):
    return {
        "policy_name": "test-gate",
        "dataset": {
            "case_count": 2,
            "sha256": "dataset-hash",
            "enabled_behavior_metrics": METRICS,
        },
        "profiles": {
            "pull_request": {
                "allowed_failed_case_ids": list(allowed_failed_ids),
                "requirements": [
                    {
                        "name": "provider",
                        "path": "experiment_config.models.provider",
                        "operator": "eq",
                        "value": "mock",
                    },
                    {
                        "name": "intent",
                        "path": "behavior_summary.intent_accuracy",
                        "operator": "gte",
                        "value": 1.0,
                    },
                    {
                        "name": "pass-rate",
                        "path": "behavior_summary.case_pass_rate",
                        "operator": "gte",
                        "value": 1.0,
                    },
                ],
            }
        },
    }


def test_quality_gate_passes_complete_candidate():
    result = evaluate_quality_gate(_report(), _policy(), profile="pull_request")

    assert result["passed"] is True
    assert result["failed_check_count"] == 0
    assert result["candidate"]["dataset_sha256"] == "dataset-hash"


def test_quality_gate_rejects_metric_regression_and_new_failed_case():
    result = evaluate_quality_gate(
        _report(pass_rate=0.5, failed_ids=("case-2",)),
        _policy(),
        profile="pull_request",
    )

    assert result["passed"] is False
    failed = {check["name"]: check for check in result["checks"] if not check["passed"]}
    assert "pass-rate" in failed
    assert failed["no_new_failed_cases"]["unexpected_failed_case_ids"] == ["case-2"]


def test_quality_gate_allows_only_explicit_known_failure():
    result = evaluate_quality_gate(
        _report(pass_rate=0.5, failed_ids=("case-2",)),
        _policy(allowed_failed_ids=("case-2",)),
        profile="pull_request",
    )

    allowlist = next(
        check for check in result["checks"] if check["name"] == "no_new_failed_cases"
    )
    assert allowlist["passed"] is True
    assert result["passed"] is False  # Aggregate threshold remains independent.


def test_quality_gate_rejects_duplicate_case_ids():
    report = _report()
    report["cases"][1]["id"] = "case-1"

    result = evaluate_quality_gate(report, _policy(), profile="pull_request")

    duplicate_check = next(
        check for check in result["checks"] if check["name"] == "case_ids_unique"
    )
    assert duplicate_check["passed"] is False


def test_quality_gate_writes_json_and_markdown(tmp_path: Path):
    result = evaluate_quality_gate(_report(), _policy(), profile="pull_request")

    paths = write_quality_gate_report(result, tmp_path)

    assert json.loads(paths["json"].read_text(encoding="utf-8"))["passed"] is True
    markdown = paths["markdown"].read_text(encoding="utf-8")
    assert "Agent Evaluation Quality Gate" in markdown
    assert "**PASS**" in markdown


def test_versioned_policy_matches_fixed_baseline_dataset():
    """策略中的 Case 数和 Hash 必须绑定仓库内的固定 Dataset。"""
    policy = load_json_object(PROJECT_ROOT / "evaluation" / "quality_gate_policy.json")
    dataset_path = (
        PROJECT_ROOT / "evaluation" / "baseline" / "supportgpt_baseline_100.json"
    )
    dataset = json.loads(dataset_path.read_text(encoding="utf-8"))
    digest = hashlib.sha256(dataset_path.read_bytes()).hexdigest()

    assert len(dataset["cases"]) == policy["dataset"]["case_count"] == 100
    assert digest == policy["dataset"]["sha256"]
    assert set(policy["profiles"]) == {"pull_request", "release"}
