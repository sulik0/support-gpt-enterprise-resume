"""基于两份不可变 Baseline JSON 生成纯离线对比报告。"""

import json
import shutil
from pathlib import Path
from typing import Any, Mapping, Optional


_METRICS = (
    ("Intent Accuracy", ("behavior_summary", "intent_accuracy")),
    ("Department Accuracy", ("behavior_summary", "department_accuracy")),
    ("Required Tool Hit Rate", ("behavior_summary", "required_tool_hit_rate")),
    (
        "Forbidden Tool Violation Rate",
        ("behavior_summary", "forbidden_tool_violation_rate"),
    ),
    ("HITL Accuracy", ("behavior_summary", "hitl_accuracy")),
    ("Approval Accuracy", ("behavior_summary", "approval_accuracy")),
    ("Case Pass Rate", ("behavior_summary", "case_pass_rate")),
    (
        "Average Latency",
        ("performance_summary", "end_to_end_latency_seconds", "average"),
    ),
    (
        "P50 Latency",
        ("performance_summary", "end_to_end_latency_seconds", "p50"),
    ),
    (
        "P95 Latency",
        ("performance_summary", "end_to_end_latency_seconds", "p95"),
    ),
    ("Average Tokens", ("performance_summary", "tokens", "average_total")),
    ("LLM Calls", ("performance_summary", "llm", "call_count")),
    (
        "Analyzer Rule Hit Rate",
        ("performance_summary", "analyzer", "rule_hit_rate"),
    ),
)
_TRANSITION_ORDER = ("FAIL→PASS", "PASS→FAIL", "FAIL→FAIL", "PASS→PASS")


def generate_baseline_diff(
    current_snapshot: Path, output_dir: Path
) -> Optional[dict[str, Path]]:
    """选择最近的可比历史快照，生成 JSON/Markdown 快照与 latest 副本。"""
    current = _load_report(current_snapshot)
    previous_path = _find_previous_snapshot(current_snapshot, output_dir, current)
    if previous_path is None:
        return None
    previous = _load_report(previous_path)
    diff = build_baseline_diff(previous, current)
    previous_run = str(previous["run_id"])
    current_run = str(current["run_id"])
    stem = f"baseline_diff_{previous_run}_to_{current_run}"
    snapshot_json = output_dir / f"{stem}.json"
    snapshot_markdown = output_dir / f"{stem}.md"
    latest_json = output_dir / "baseline_diff_latest.json"
    latest_markdown = output_dir / "baseline_diff_latest.md"
    diff["artifacts"] = {
        "snapshot_json": snapshot_json.name,
        "snapshot_markdown": snapshot_markdown.name,
        "latest_json": latest_json.name,
        "latest_markdown": latest_markdown.name,
    }
    snapshot_json.write_text(
        json.dumps(diff, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    snapshot_markdown.write_text(_render_markdown(diff), encoding="utf-8")
    _replace_copy(latest_json, snapshot_json)
    _replace_copy(latest_markdown, snapshot_markdown)
    return {
        "json": latest_json,
        "markdown": latest_markdown,
        "snapshot_json": snapshot_json,
        "snapshot_markdown": snapshot_markdown,
        "previous_snapshot_json": previous_path,
    }


def build_baseline_diff(
    previous: Mapping[str, Any], current: Mapping[str, Any]
) -> dict[str, Any]:
    """校验固定 Dataset 后计算指标变化和四种 Case 转移。"""
    previous_cases = {str(case["id"]): case for case in previous["cases"]}
    current_cases = {str(case["id"]): case for case in current["cases"]}
    previous_sha = _dataset_sha(previous)
    current_sha = _dataset_sha(current)
    if not previous_sha or previous_sha != current_sha:
        raise ValueError("Baseline Diff requires identical Dataset SHA256 values.")
    if previous_cases.keys() != current_cases.keys():
        raise ValueError("Baseline Diff requires an identical set of Case IDs.")

    metric_rows = []
    for label, path in _METRICS:
        before = float(_nested(previous, path))
        after = float(_nested(current, path))
        metric_rows.append(
            {
                "metric": label,
                "previous": round(before, 6),
                "current": round(after, 6),
                "delta": round(after - before, 6),
            }
        )

    transitions = {name: [] for name in _TRANSITION_ORDER}
    changes = []
    for case_id in sorted(previous_cases):
        before_case = previous_cases[case_id]
        after_case = current_cases[case_id]
        before_pass = bool(before_case["behavior_evaluation"]["passed"])
        after_pass = bool(after_case["behavior_evaluation"]["passed"])
        transition = f"{'PASS' if before_pass else 'FAIL'}→{'PASS' if after_pass else 'FAIL'}"
        transitions[transition].append(case_id)
        if before_pass != after_pass:
            changes.append(
                {
                    "case_id": case_id,
                    "transition": transition,
                    "query": after_case.get("dataset_case", {}).get("query", ""),
                    "previous_failures": before_case["behavior_evaluation"].get(
                        "failures", []
                    ),
                    "current_failures": after_case["behavior_evaluation"].get(
                        "failures", []
                    ),
                    "previous_trace_id": before_case.get("trace_id"),
                    "current_trace_id": after_case.get("trace_id"),
                }
            )

    return {
        "schema_version": "1.0",
        "evaluation_type": "baseline_workflow_replay_v1_diff",
        "dataset_sha256": current_sha,
        "case_count": len(current_cases),
        "previous": {
            "run_id": previous["run_id"],
            "generated_at": previous.get("generated_at"),
            "experiment_config": previous.get("experiment_config", {}),
        },
        "current": {
            "run_id": current["run_id"],
            "generated_at": current.get("generated_at"),
            "experiment_config": current.get("experiment_config", {}),
        },
        "metrics": metric_rows,
        "case_transitions": {
            name: {"count": len(case_ids), "case_ids": case_ids}
            for name, case_ids in transitions.items()
        },
        "changed_cases": changes,
    }


def _find_previous_snapshot(
    current_snapshot: Path, output_dir: Path, current: Mapping[str, Any]
) -> Optional[Path]:
    """只从完整、Dataset 和 Case ID 都相同的历史快照中选最新一份。"""
    current_ids = {str(case["id"]) for case in current.get("cases", [])}
    current_sha = _dataset_sha(current)
    candidates = []
    for path in output_dir.glob("baseline_v1_*.json"):
        if path.name == "baseline_v1_latest.json" or path == current_snapshot:
            continue
        try:
            report = _load_report(path)
        except (OSError, ValueError, KeyError, json.JSONDecodeError):
            continue
        case_ids = {str(case["id"]) for case in report.get("cases", [])}
        if _dataset_sha(report) == current_sha and case_ids == current_ids:
            candidates.append(path)
    return max(candidates, key=lambda path: path.name) if candidates else None


def _dataset_sha(report: Mapping[str, Any]) -> str:
    return str(
        report.get("experiment_config", {}).get("dataset", {}).get("sha256", "")
    )


def _load_report(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Baseline report must be an object: {path}")
    return value


def _nested(value: Mapping[str, Any], path: tuple[str, ...]) -> Any:
    current: Any = value
    for key in path:
        current = current[key]
    return current


def _replace_copy(latest: Path, snapshot: Path) -> None:
    if latest.is_symlink() or latest.exists():
        latest.unlink()
    shutil.copyfile(snapshot, latest)


def _render_markdown(diff: Mapping[str, Any]) -> str:
    lines = [
        "# Baseline V1 Diff Report",
        "",
        f"- Previous Run：`{diff['previous']['run_id']}`",
        f"- Current Run：`{diff['current']['run_id']}`",
        f"- Dataset SHA256：`{diff['dataset_sha256']}`",
        f"- Case 数：{diff['case_count']}",
        "- 本报告纯离线生成，未重放 Workflow，未调用 LLM。",
        "",
        "## 指标对比",
        "",
        "| Metric | Previous | Current | Delta |",
        "|---|---:|---:|---:|",
    ]
    for row in diff["metrics"]:
        lines.append(
            f"| {row['metric']} | {row['previous']:.6f} | "
            f"{row['current']:.6f} | {row['delta']:+.6f} |"
        )
    lines.extend(
        [
            "",
            "## Case 状态转移",
            "",
            "| Transition | Count | Case IDs |",
            "|---|---:|---|",
        ]
    )
    for name in _TRANSITION_ORDER:
        item = diff["case_transitions"][name]
        case_ids = ", ".join(item["case_ids"]) or "-"
        lines.append(f"| {name} | {item['count']} | {case_ids} |")

    lines.extend(["", "## 通过状态发生变化的 Case", ""])
    if not diff["changed_cases"]:
        lines.append("本次没有 `FAIL↔PASS` 变化。")
    else:
        lines.extend(
            [
                "| Case ID | Transition | Previous Failures | Current Failures | Previous Trace | Current Trace |",
                "|---|---|---|---|---|---|",
            ]
        )
        for case in diff["changed_cases"]:
            before = "<br>".join(case["previous_failures"]) or "-"
            after = "<br>".join(case["current_failures"]) or "-"
            lines.append(
                f"| {case['case_id']} | {case['transition']} | {before} | {after} | "
                f"`{case['previous_trace_id'] or '-'}` | `{case['current_trace_id'] or '-'}` |"
            )

    lines.extend(
        [
            "",
            "## Previous 实验配置",
            "",
            "```json",
            json.dumps(
                diff["previous"]["experiment_config"], ensure_ascii=False, indent=2
            ),
            "```",
            "",
            "## Current 实验配置",
            "",
            "```json",
            json.dumps(
                diff["current"]["experiment_config"], ensure_ascii=False, indent=2
            ),
            "```",
            "",
        ]
    )
    return "\n".join(lines)
