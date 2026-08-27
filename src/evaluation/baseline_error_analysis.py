"""基于 Baseline JSON 生成纯离线、确定性失败分析报告。"""

import json
import os
import re
import shutil
from collections import Counter
from pathlib import Path
from typing import Any, Dict, Mapping, Sequence


METRIC_TARGETS = {
    "intent_accuracy": 1.0,
    "department_accuracy": 1.0,
    "required_tool_hit_rate": 1.0,
    "forbidden_tool_violation_rate": 0.0,
    "hitl_accuracy": 1.0,
    "approval_accuracy": 1.0,
}
_SAFE_RUN_ID = re.compile(r"^[A-Za-z0-9_-]+$")


def write_baseline_error_analysis(
    source_json: Path, output_dir: Path | None = None
) -> Dict[str, Path]:
    """读取本次 Baseline JSON，写入不可变快照和 latest 副本。"""
    report = json.loads(source_json.read_text(encoding="utf-8"))
    _validate_report(report)
    run_id = str(report["run_id"])
    if not _SAFE_RUN_ID.fullmatch(run_id):
        raise ValueError("Baseline report run_id contains unsafe characters.")

    target_dir = output_dir or source_json.parent
    target_dir.mkdir(parents=True, exist_ok=True)
    snapshot = target_dir / f"error_analysis_{run_id}.md"
    latest = target_dir / "error_analysis_latest.md"
    content = build_baseline_error_analysis(report, source_json.name)
    _write_immutable_snapshot(snapshot, content)
    _replace_latest_copy(latest, snapshot)
    return {"latest": latest, "snapshot": snapshot}


def build_baseline_error_analysis(
    report: Mapping[str, Any], source_json_name: str
) -> str:
    """只对 FAIL Case 生成 Breakdown、混淆矩阵和逐 Case 证据。"""
    _validate_report(report)
    failed_cases = [
        row
        for row in report["cases"]
        if not bool(row["behavior_evaluation"].get("passed", False))
    ]
    metric_failures = {
        metric: [row for row in failed_cases if _metric_failed(row, metric)]
        for metric in METRIC_TARGETS
    }
    lines = [
        "# Baseline Workflow Replay V1 Error Analysis",
        "",
        f"- Run ID：`{report['run_id']}`",
        f"- Source JSON：`{source_json_name}`",
        f"- Source Generated At：`{report.get('generated_at', 'unavailable')}`",
        f"- Dataset：`{report.get('dataset', 'unavailable')}`",
        f"- Total Cases：{report.get('case_count', len(report['cases']))}",
        f"- FAIL Cases：{len(failed_cases)}",
        "- 本报告仅读取本次 Baseline JSON 中的 FAIL Case，不重放 Workflow，不调用 LLM。",
        "",
        "## Failure Breakdown",
        "",
        "| Metric | Target | Failed Cases | Case IDs |",
        "|---|---:|---:|---|",
    ]
    for metric, rows in metric_failures.items():
        ids = ", ".join(str(row["id"]) for row in rows) or "-"
        lines.append(
            f"| `{metric}` | {_metric(METRIC_TARGETS[metric])} "
            f"| {len(rows)} | {_markdown(ids)} |"
        )

    failure_count_distribution = Counter(
        len(_failed_metrics(row)) for row in failed_cases
    )
    lines.extend(
        [
            "",
            "### 单 Case 失败指标数分布",
            "",
            "| Failed Metrics per Case | Cases |",
            "|---:|---:|",
        ]
    )
    if failure_count_distribution:
        for count in sorted(failure_count_distribution):
            lines.append(f"| {count} | {failure_count_distribution[count]} |")
    else:
        lines.append("| 0 | 0 |")

    lines.extend(_render_intent_confusion_matrix(failed_cases))
    lines.extend(_render_decision_mismatches(failed_cases))
    lines.extend(_render_tool_problems(failed_cases))
    lines.extend(_render_case_details(failed_cases))
    return "\n".join(lines) + "\n"


def _render_intent_confusion_matrix(
    failed_cases: Sequence[Mapping[str, Any]],
) -> list[str]:
    """混淆矩阵只统计整体判定为 FAIL 的 Case。"""
    pairs = []
    for row in failed_cases:
        evaluation = row["behavior_evaluation"]
        expected = evaluation["expected"].get("intent")
        actual = evaluation["actual"].get("intent")
        if expected is not None and actual is not None:
            pairs.append((str(expected), str(actual)))
    expected_labels = sorted({expected for expected, _ in pairs})
    actual_labels = sorted({actual for _, actual in pairs})
    lines = [
        "",
        "## Intent Confusion Matrix",
        "",
        "仅统计本次报告中的 FAIL Case；行是 Expected，列是 Actual。",
        "",
    ]
    if not expected_labels or not actual_labels:
        lines.append("无可统计的 FAIL Case Intent。")
        return lines
    matrix = Counter(pairs)
    lines.append(
        "| Expected \\ Actual | "
        + " | ".join(_markdown(label) for label in actual_labels)
        + " |"
    )
    lines.append("|---|" + "---:|" * len(actual_labels))
    for expected in expected_labels:
        values = " | ".join(
            str(matrix[(expected, actual)]) for actual in actual_labels
        )
        lines.append(f"| {_markdown(expected)} | {values} |")
    return lines


def _render_decision_mismatches(
    failed_cases: Sequence[Mapping[str, Any]],
) -> list[str]:
    lines = [
        "",
        "## HITL / Approval Mismatch",
        "",
        "| Decision | Case ID | Expected | Actual | Trace ID |",
        "|---|---|---:|---:|---|",
    ]
    mismatches = []
    for row in failed_cases:
        evaluation = row["behavior_evaluation"]
        for metric, field, label in (
            ("hitl_accuracy", "hitl", "HITL"),
            ("approval_accuracy", "approval", "Approval"),
        ):
            if _metric_failed(row, metric):
                mismatches.append(
                    (
                        label,
                        row["id"],
                        evaluation["expected"].get(field),
                        evaluation["actual"].get(field),
                        row.get("trace_id"),
                    )
                )
    if not mismatches:
        lines.append("| - | - | - | - | - |")
        return lines
    for label, case_id, expected, actual, trace_id in mismatches:
        lines.append(
            f"| {label} | {_markdown(case_id)} | {expected} | {actual} "
            f"| `{trace_id or 'unavailable'}` |"
        )
    return lines


def _render_tool_problems(failed_cases: Sequence[Mapping[str, Any]]) -> list[str]:
    lines = [
        "",
        "## Tool 问题",
        "",
        "| Case ID | Missing Required Tools | Forbidden Tool Violations | Actual Called Tools | Trace ID |",
        "|---|---|---|---|---|",
    ]
    problems = []
    for row in failed_cases:
        evaluation = row["behavior_evaluation"]
        required = set(evaluation["expected"].get("required_tools", []))
        forbidden = set(evaluation["expected"].get("forbidden_tools", []))
        called = set(evaluation["actual"].get("tools", []))
        missing = sorted(required - called)
        violations = sorted(forbidden & called)
        if missing or violations:
            problems.append((row, missing, violations, sorted(called)))
    if not problems:
        lines.append("| - | - | - | - | - |")
        return lines
    for row, missing, violations, called in problems:
        lines.append(
            f"| {_markdown(row['id'])} | {_markdown(missing)} "
            f"| {_markdown(violations)} | {_markdown(called)} "
            f"| `{row.get('trace_id') or 'unavailable'}` |"
        )
    return lines


def _render_case_details(failed_cases: Sequence[Mapping[str, Any]]) -> list[str]:
    lines = ["", "## FAIL Case 详情", ""]
    if not failed_cases:
        lines.append("本次没有 FAIL Case。")
        return lines
    for row in failed_cases:
        evaluation = row["behavior_evaluation"]
        query = row.get("dataset_case", {}).get("query", "")
        reasons = evaluation.get("failures", [])
        lines.extend(
            [
                f"### `{row['id']}`",
                "",
                f"- Query：{_markdown(query)}",
                f"- Failed Metrics：{', '.join(f'`{item}`' for item in _failed_metrics(row))}",
                f"- Failure Reasons：{_markdown(reasons)}",
                f"- Trace ID：`{row.get('trace_id') or 'unavailable'}`",
                "",
                "Expected：",
                "",
                "```json",
                json.dumps(
                    evaluation.get("expected", {}),
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                ),
                "```",
                "",
                "Actual：",
                "",
                "```json",
                json.dumps(
                    evaluation.get("actual", {}),
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                ),
                "```",
                "",
            ]
        )
    return lines


def _failed_metrics(row: Mapping[str, Any]) -> list[str]:
    return [metric for metric in METRIC_TARGETS if _metric_failed(row, metric)]


def _metric_failed(row: Mapping[str, Any], metric: str) -> bool:
    value = row["behavior_evaluation"]["checks"].get(metric)
    return value is not None and float(value) != METRIC_TARGETS[metric]


def _validate_report(report: Mapping[str, Any]) -> None:
    if report.get("evaluation_type") != "baseline_workflow_replay_v1":
        raise ValueError("Error Analysis requires a Baseline Workflow Replay V1 report.")
    if not report.get("run_id"):
        raise ValueError("Baseline report must contain run_id.")
    cases = report.get("cases")
    if not isinstance(cases, list):
        raise ValueError("Baseline report must contain a cases list.")
    for row in cases:
        evaluation = row.get("behavior_evaluation")
        if not isinstance(evaluation, Mapping):
            raise ValueError("Each Baseline case must contain behavior_evaluation.")


def _write_immutable_snapshot(path: Path, content: str) -> None:
    """已存在的同名快照只允许内容完全一致。"""
    if path.exists():
        if path.read_text(encoding="utf-8") != content:
            raise FileExistsError(f"Refusing to overwrite immutable snapshot: {path}")
        return
    path.write_text(content, encoding="utf-8")


def _replace_latest_copy(latest: Path, snapshot: Path) -> None:
    """原子替换 latest 普通文件，不使用符号链接。"""
    temporary = latest.with_name(f".{latest.name}.tmp")
    if temporary.exists() or temporary.is_symlink():
        temporary.unlink()
    try:
        shutil.copy2(snapshot, temporary)
        os.replace(temporary, latest)
    finally:
        if temporary.exists() or temporary.is_symlink():
            temporary.unlink()


def _metric(value: Any) -> str:
    return "N/A" if value is None else f"{float(value):.4f}"


def _markdown(value: Any) -> str:
    rendered = (
        value
        if isinstance(value, str)
        else json.dumps(
            value, ensure_ascii=False, separators=(",", ":"), sort_keys=True
        )
    )
    return str(rendered).replace("|", "\\|").replace("\n", " ")
