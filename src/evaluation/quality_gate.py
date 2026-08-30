"""基于 Baseline 报告执行离线、确定性的发布质量门禁。"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping, Sequence


SUPPORTED_OPERATORS = {"eq", "ne", "gte", "lte", "in", "not_in"}


class QualityGateError(ValueError):
    """表示门禁配置或候选报告不满足可评估条件。"""


def load_json_object(path: Path) -> dict[str, Any]:
    """读取 JSON 对象，并为 CI 输出稳定的错误信息。"""
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise QualityGateError(
            f"Unable to read JSON object from {path}: {exc}"
        ) from exc
    if not isinstance(value, dict):
        raise QualityGateError(f"Expected a JSON object in {path}.")
    return value


def evaluate_quality_gate(
    report: Mapping[str, Any],
    policy: Mapping[str, Any],
    *,
    profile: str,
) -> dict[str, Any]:
    """校验报告完整性、Dataset、质量阈值和失败 Case 白名单。"""
    profile_config = _profile(policy, profile)
    checks = [
        *_structural_checks(report, policy),
        *(
            _evaluate_requirement(report, requirement)
            for requirement in profile_config.get("requirements", [])
        ),
        _failure_allowlist_check(report, profile_config),
    ]
    failed_checks = [check for check in checks if not check["passed"]]
    return {
        "schema_version": "1.0",
        "gate_name": str(policy.get("policy_name", "quality-gate")),
        "profile": profile,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "candidate": {
            "run_id": report.get("run_id"),
            "source_revision": _lookup(
                report, "experiment_config.workflow.source_revision", default="unknown"
            ),
            "dataset_sha256": _lookup(
                report, "experiment_config.dataset.sha256", default=None
            ),
            "case_count": report.get("case_count"),
            "execution_mode": _lookup(report, "execution.mode", default=None),
            "model_provider": _lookup(
                report, "experiment_config.models.provider", default=None
            ),
        },
        "passed": not failed_checks,
        "check_count": len(checks),
        "failed_check_count": len(failed_checks),
        "checks": checks,
    }


def write_quality_gate_report(
    result: Mapping[str, Any], output_dir: Path
) -> dict[str, Path]:
    """同时输出机器可读 JSON 和便于 Actions 展示的 Markdown。"""
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "quality_gate.json"
    markdown_path = output_dir / "quality_gate.md"
    json_path.write_text(
        json.dumps(result, ensure_ascii=False, indent=2, default=str),
        encoding="utf-8",
    )
    markdown_path.write_text(_render_markdown(result), encoding="utf-8")
    return {"json": json_path, "markdown": markdown_path}


def _profile(policy: Mapping[str, Any], profile: str) -> Mapping[str, Any]:
    profiles = policy.get("profiles")
    if not isinstance(profiles, Mapping) or profile not in profiles:
        available = sorted(profiles) if isinstance(profiles, Mapping) else []
        raise QualityGateError(
            f"Unknown quality-gate profile '{profile}'. Available: {available}"
        )
    value = profiles[profile]
    if not isinstance(value, Mapping):
        raise QualityGateError(f"Profile '{profile}' must be an object.")
    requirements = value.get("requirements", [])
    if not isinstance(requirements, Sequence) or isinstance(requirements, (str, bytes)):
        raise QualityGateError(f"Profile '{profile}' requirements must be a list.")
    return value


def _structural_checks(
    report: Mapping[str, Any], policy: Mapping[str, Any]
) -> list[dict[str, Any]]:
    dataset = policy.get("dataset", {})
    cases = report.get("cases", [])
    case_ids = [case.get("id") for case in cases if isinstance(case, Mapping)]
    expected_metrics = dataset.get("enabled_behavior_metrics", [])
    actual_metrics = report.get("enabled_behavior_metrics", [])
    return [
        _check(
            "report_type",
            "eq",
            "baseline_workflow_replay_v1",
            report.get("evaluation_type"),
        ),
        _check(
            "dataset_sha256",
            "eq",
            dataset.get("sha256"),
            _lookup(report, "experiment_config.dataset.sha256", default=None),
        ),
        _check(
            "dataset_case_count",
            "eq",
            dataset.get("case_count"),
            report.get("case_count"),
        ),
        _check(
            "report_case_rows_complete",
            "eq",
            report.get("case_count"),
            len(cases) if isinstance(cases, list) else None,
        ),
        _check(
            "case_ids_unique",
            "eq",
            len(case_ids),
            len(set(case_ids)),
        ),
        _check(
            "case_ids_present",
            "eq",
            len(case_ids),
            sum(bool(case_id) for case_id in case_ids),
        ),
        _check(
            "enabled_behavior_metrics",
            "eq",
            list(expected_metrics),
            (
                list(actual_metrics)
                if isinstance(actual_metrics, list)
                else actual_metrics
            ),
        ),
    ]


def _evaluate_requirement(
    report: Mapping[str, Any], requirement: Any
) -> dict[str, Any]:
    if not isinstance(requirement, Mapping):
        raise QualityGateError("Each quality-gate requirement must be an object.")
    name = str(requirement.get("name") or requirement.get("path") or "unnamed")
    path = requirement.get("path")
    operator = str(requirement.get("operator", "eq"))
    if not isinstance(path, str) or not path:
        raise QualityGateError(f"Requirement '{name}' has no path.")
    if operator not in SUPPORTED_OPERATORS:
        raise QualityGateError(
            f"Requirement '{name}' uses unsupported operator '{operator}'."
        )
    expected = requirement.get("value")
    actual = _lookup(report, path, default=None)
    return _check(name, operator, expected, actual, path=path)


def _failure_allowlist_check(
    report: Mapping[str, Any], profile: Mapping[str, Any]
) -> dict[str, Any]:
    allowed = {str(item) for item in profile.get("allowed_failed_case_ids", [])}
    failed = {
        str(case.get("id"))
        for case in report.get("cases", [])
        if isinstance(case, Mapping)
        and not bool(
            _lookup(case, "behavior_evaluation.passed", default=False)
        )
    }
    unexpected = sorted(failed - allowed)
    return {
        "name": "no_new_failed_cases",
        "path": "cases[].behavior_evaluation.passed",
        "operator": "subset",
        "expected": sorted(allowed),
        "actual": sorted(failed),
        "unexpected_failed_case_ids": unexpected,
        "passed": not unexpected,
    }


def _check(
    name: str,
    operator: str,
    expected: Any,
    actual: Any,
    *,
    path: str | None = None,
) -> dict[str, Any]:
    try:
        passed = _compare(actual, expected, operator)
    except (TypeError, ValueError):
        passed = False
    return {
        "name": name,
        "path": path,
        "operator": operator,
        "expected": expected,
        "actual": actual,
        "passed": passed,
    }


def _compare(actual: Any, expected: Any, operator: str) -> bool:
    if operator == "eq":
        return actual == expected
    if operator == "ne":
        return actual != expected
    if operator == "gte":
        return float(actual) >= float(expected)
    if operator == "lte":
        return float(actual) <= float(expected)
    if operator == "in":
        return actual in expected
    if operator == "not_in":
        return actual not in expected
    raise QualityGateError(f"Unsupported operator: {operator}")


def _lookup(value: Any, path: str, *, default: Any) -> Any:
    current = value
    for part in path.split("."):
        if not isinstance(current, Mapping) or part not in current:
            return default
        current = current[part]
    return current


def _render_markdown(result: Mapping[str, Any]) -> str:
    candidate = result["candidate"]
    status = "PASS" if result["passed"] else "FAIL"
    lines = [
        "# Agent Evaluation Quality Gate",
        "",
        f"- Status: **{status}**",
        f"- Profile: `{result['profile']}`",
        f"- Run ID: `{candidate.get('run_id') or 'unknown'}`",
        f"- Source Revision: `{candidate.get('source_revision') or 'unknown'}`",
        f"- Dataset SHA256: `{candidate.get('dataset_sha256') or 'unknown'}`",
        f"- Failed Checks: {result['failed_check_count']} / {result['check_count']}",
        "",
        "| Check | Operator | Expected | Actual | Result |",
        "|---|---|---|---|---|",
    ]
    for check in result["checks"]:
        lines.append(
            f"| {_markdown(check['name'])} | `{check['operator']}` "
            f"| {_markdown(check.get('expected'))} "
            f"| {_markdown(check.get('actual'))} "
            f"| {'PASS' if check['passed'] else 'FAIL'} |"
        )
    return "\n".join(lines) + "\n"


def _markdown(value: Any) -> str:
    if isinstance(value, (dict, list, tuple, set)):
        text = json.dumps(value, ensure_ascii=False, sort_keys=True, default=str)
    else:
        text = str(value)
    return text.replace("|", "\\|").replace("\n", " ")
