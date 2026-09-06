"""复用 Baseline 门禁，保存可验证的实验与发布证据。"""

from __future__ import annotations

import json
import subprocess
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.evaluation.baseline_diff import build_baseline_diff
from src.evaluation.quality_gate import evaluate_quality_gate
from src.promptops.registry import PromptBundle, PromptRegistry, atomic_json, canonical_hash


def source_state() -> dict[str, Any]:
    """记录工作树是否干净；未提交代码的报告只能用于开发验证。"""
    root = Path(__file__).resolve().parents[2]
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=root, check=True,
        capture_output=True, text=True, timeout=5,
    ).stdout.strip()
    dirty = subprocess.run(
        ["git", "status", "--porcelain"], cwd=root, check=True,
        capture_output=True, text=True, timeout=5,
    ).stdout.strip()
    diff = subprocess.run(
        ["git", "diff", "HEAD", "--binary"], cwd=root, check=True,
        capture_output=True, text=True, timeout=5,
    ).stdout
    untracked = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard", "-z"],
        cwd=root, check=True, capture_output=True, timeout=5,
    ).stdout.decode().split("\0")
    files = {name: (root / name).read_bytes().hex() for name in untracked if name and (root / name).is_file()}
    return {"revision": revision, "dirty": bool(dirty), "worktree_sha256": canonical_hash([diff, files])}


def validate_report_prompt(report: dict[str, Any], bundle: PromptBundle) -> None:
    """同时校验内容快照与 Hash，拒绝只修改版本标签的报告。"""
    prompts = report["experiment_config"].get("prompts", {})
    if prompts != {**bundle.metadata(), "snapshot": bundle.payload()}:
        raise ValueError("Evaluation report does not match the exact Prompt Bundle.")
    if not report.get("cases") or any(
        case.get("prompt_bundle_id") != bundle.bundle_id for case in report["cases"]
    ):
        raise ValueError("Case Prompt bindings do not match the experiment Bundle.")


def assess_experiment(
    *, report: dict[str, Any], policy: dict[str, Any], bundle: PromptBundle,
    baseline: dict[str, Any] | None, environment: str, expected_current: str,
) -> dict[str, Any]:
    """确定性检查质量门禁与实验可比性，不执行 Workflow 或调用模型。"""
    PromptRegistry._environment(environment)
    validate_report_prompt(report, bundle)
    mock = report["experiment_config"]["models"]["provider"] == "mock"
    profile = "pull_request" if mock else "release"
    gate = evaluate_quality_gate(report, policy, profile=profile)
    reasons = [] if gate["passed"] else ["quality_gate_failed"]
    diff = None
    if environment == "production" and mock:
        reasons.append("production_requires_real_llm_evaluation")
    if environment == "production" and baseline is None:
        reasons.append("production_requires_current_baseline")
    if baseline is not None:
        before = baseline["experiment_config"]
        after = report["experiment_config"]
        baseline_bundle = PromptBundle(before.get("prompts", {}).get("snapshot", {}))
        validate_report_prompt(baseline, baseline_bundle)
        if baseline_bundle.bundle_id != expected_current:
            reasons.append("baseline_is_not_current_prompt")
        for section in ("dataset", "evaluator", "models", "limits", "risk_thresholds"):
            if before.get(section) != after.get(section):
                reasons.append(f"incomparable_{section}")
        for key in ("source_revision", "version"):
            if before.get("workflow", {}).get(key) != after.get("workflow", {}).get(key):
                reasons.append(f"incomparable_workflow_{key}")
        # Hash/Case 不一致时仍保存失败报告，但不生成误导性的对比。
        try:
            diff = build_baseline_diff(baseline, report)
            if diff["case_transitions"]["PASS→FAIL"]["count"]:
                reasons.append("new_failed_cases")
        except (ValueError, KeyError, TypeError):
            reasons.append("incomparable_case_results")
    return {
        "passed": not reasons, "reasons": reasons, "quality_gate": gate,
        "comparison": diff,
        "scope": "Baseline V1 六项确定性行为指标与现有性能门禁；不代表语义质量认证。",
    }


def save_experiment(
    registry: PromptRegistry, *, bundle: PromptBundle, report: dict[str, Any],
    policy: dict[str, Any], baseline: dict[str, Any] | None,
    environment: str, expected_current: str, source: dict[str, Any],
) -> Path:
    """保存独立实验目录；latest 只是普通索引文件，发布读取固定快照。"""
    assessment = assess_experiment(
        report=report, policy=policy, bundle=bundle, baseline=baseline,
        environment=environment, expected_current=expected_current,
    )
    experiment_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:12]
    directory = registry.root / "experiments" / experiment_id
    directory.mkdir(parents=True, exist_ok=False)
    evidence = {
        "schema_version": "1.0", "experiment_id": experiment_id,
        "environment": environment, "expected_current": expected_current,
        "bundle_id": bundle.bundle_id, "source": source,
        "report_sha256": canonical_hash(report),
        "policy_sha256": canonical_hash(policy),
        "baseline_sha256": canonical_hash(baseline) if baseline else None,
        "assessment": assessment,
    }
    atomic_json(directory / "candidate.json", report)
    atomic_json(directory / "policy.json", policy)
    if baseline is not None:
        atomic_json(directory / "baseline.json", baseline)
    atomic_json(directory / "experiment.json", evidence)
    (directory / "experiment.md").write_text(render_experiment(evidence), encoding="utf-8")
    atomic_json(registry.root / "experiments" / "latest.json", {"experiment_id": experiment_id})
    return directory / "experiment.json"


def promote_experiment(
    registry: PromptRegistry, *, experiment_id: str, policy: dict[str, Any],
    actor: str, reason: str,
) -> dict[str, Any]:
    """晋级前重新读取证据并计算门禁，不信任预先写好的 passed 字段。"""
    import re

    if not re.fullmatch(r"[0-9]{8}_[0-9]{6}_[0-9a-f]{12}", experiment_id):
        raise ValueError("Invalid experiment ID.")
    directory = registry.root / "experiments" / experiment_id
    evidence = json.loads((directory / "experiment.json").read_text(encoding="utf-8"))
    report = json.loads((directory / "candidate.json").read_text(encoding="utf-8"))
    baseline_path = directory / "baseline.json"
    baseline = json.loads(baseline_path.read_text(encoding="utf-8")) if baseline_path.exists() else None
    if (
        canonical_hash(report) != evidence["report_sha256"]
        or canonical_hash(policy) != evidence["policy_sha256"]
        or (canonical_hash(baseline) if baseline else None) != evidence["baseline_sha256"]
    ):
        raise ValueError("Experiment evidence or quality gate policy changed.")
    current_source = source_state()
    if evidence["environment"] == "production":
        if evidence["source"]["dirty"] or current_source != evidence["source"]:
            raise ValueError("Production promotion requires the same clean evaluated Git revision.")
        revision = report["experiment_config"]["workflow"]["source_revision"]
        if revision != current_source["revision"]:
            raise ValueError("Report source revision does not match the deployed code.")
    bundle = registry.load(evidence["bundle_id"])
    assessment = assess_experiment(
        report=report, policy=policy, bundle=bundle, baseline=baseline,
        environment=evidence["environment"], expected_current=evidence["expected_current"],
    )
    if not assessment["passed"]:
        raise ValueError("Prompt promotion blocked: " + ", ".join(assessment["reasons"]))
    return registry._release(
        environment=evidence["environment"], bundle_id=bundle.bundle_id,
        expected_current=evidence["expected_current"], actor=actor, reason=reason,
        evidence={"experiment_id": experiment_id, "report_sha256": evidence["report_sha256"],
                  "policy_sha256": evidence["policy_sha256"]},
    )


def render_experiment(evidence: dict[str, Any]) -> str:
    """输出实验配置、门禁原因以及逐 Case 变化索引。"""
    result = evidence["assessment"]
    lines = [
        "# PromptOps 实验报告", "", f"- 实验：`{evidence['experiment_id']}`",
        f"- 目标环境：{evidence['environment']}",
        f"- 候选 Bundle：`{evidence['bundle_id']}`",
        f"- 当前 Bundle：`{evidence['expected_current']}`",
        f"- 代码：`{evidence['source']['revision']}`；未提交改动：{evidence['source']['dirty']}",
        f"- 门禁：{'PASS' if result['passed'] else 'FAIL'}",
        f"- 原因：{', '.join(result['reasons']) or '无'}", "", result["scope"], "",
        "完整 Prompt、模型、Dataset、阈值和逐 Case Trace 见同目录 candidate.json。",
    ]
    diff = result.get("comparison")
    if diff:
        lines.extend(["", "## 指标变化", "", "| 指标 | 当前 | 候选 | 差值 |", "|---|---:|---:|---:|"])
        for row in diff["metrics"]:
            lines.append(f"| {row['metric']} | {row['previous']} | {row['current']} | {row['delta']} |")
        lines.extend(["", "## Case 变化", ""])
        for transition, value in diff["case_transitions"].items():
            lines.append(f"- {transition}：{', '.join(value['case_ids']) or '无'}")
    return "\n".join(lines) + "\n"
