"""对已有 Baseline JSON 执行纯离线质量门禁。"""

import argparse
import os
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.evaluation.quality_gate import (
    QualityGateError,
    evaluate_quality_gate,
    load_json_object,
    write_quality_gate_report,
)


def parse_args() -> argparse.Namespace:
    """解析候选报告、策略和门禁 Profile。"""
    parser = argparse.ArgumentParser(
        description="Apply a deterministic quality gate to a Baseline report."
    )
    parser.add_argument("--report", type=Path, required=True)
    parser.add_argument(
        "--policy",
        type=Path,
        default=PROJECT_ROOT / "evaluation" / "quality_gate_policy.json",
    )
    parser.add_argument(
        "--profile", choices=("pull_request", "release"), required=True
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "evaluation" / "reports" / "quality_gate",
    )
    return parser.parse_args()


def main() -> int:
    """门禁失败返回非零退出码，并保留完整检查报告。"""
    args = parse_args()
    try:
        report = load_json_object(args.report)
        policy = load_json_object(args.policy)
        result = evaluate_quality_gate(report, policy, profile=args.profile)
        paths = write_quality_gate_report(result, args.output_dir)
    except QualityGateError as exc:
        print(f"Quality gate configuration error: {exc}", file=sys.stderr)
        return 2

    status = "PASS" if result["passed"] else "FAIL"
    print(f"Quality gate: {status}")
    print(f"JSON report: {paths['json']}")
    print(f"Markdown report: {paths['markdown']}")
    _append_github_summary(paths["markdown"])
    if not result["passed"]:
        for check in result["checks"]:
            if not check["passed"]:
                print(
                    "FAILED: "
                    f"{check['name']} expected={check.get('expected')} "
                    f"actual={check.get('actual')}",
                    file=sys.stderr,
                )
        return 1
    return 0


def _append_github_summary(markdown_path: Path) -> None:
    """在 GitHub Actions 页面直接展示门禁结果。"""
    summary_path = os.getenv("GITHUB_STEP_SUMMARY")
    if not summary_path:
        return
    with Path(summary_path).open("a", encoding="utf-8") as stream:
        stream.write(markdown_path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    raise SystemExit(main())
