"""运行固定 100 条 Baseline 的第一版真实 Workflow Replay 评测。"""

import argparse
import asyncio
import json
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))
BASELINE_PATH = (
    PROJECT_ROOT / "evaluation" / "baseline" / "supportgpt_baseline_100.json"
)

from src.config import settings
from src.database import init_db
from src.evaluation.baseline_evaluation import run_baseline_evaluation_v1
from src.evaluation.offline_rag import load_evaluation_dataset
from src.evaluation.real_llm_regression import (
    build_real_llm_run_plan,
    require_live_confirmation,
)
from src.observability.tracing import init_tracing


def parse_args() -> argparse.Namespace:
    """解析真实回放的成本确认、输出目录和开发抽样参数。"""
    parser = argparse.ArgumentParser(
        description="Replay the fixed 100-case Baseline against the real Workflow."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "evaluation" / "reports" / "baseline_v1",
    )
    parser.add_argument(
        "--max-workflow-calls",
        type=int,
        default=300,
        help="Maximum estimated paid Workflow LLM calls.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Development-only prefix sample; omit to replay all 100 cases.",
    )
    parser.add_argument(
        "--confirm-live",
        action="store_true",
        help="Acknowledge real model calls and possible cost.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate the real-model plan without replaying Workflow cases.",
    )
    return parser.parse_args()


async def main() -> None:
    """校验固定 Dataset 和调用预算后执行真实 LangGraph 回放。"""
    args = parse_args()
    cases = load_evaluation_dataset(
        BASELINE_PATH, validate_agent=False, validate_security=False
    )
    if len(cases) != 100:
        raise ValueError("Baseline Evaluation V1 requires exactly 100 cases.")
    if args.limit is not None and not 1 <= args.limit <= 100:
        raise ValueError("--limit must be between 1 and 100.")

    selected_ids = (
        [case.id for case in cases[: args.limit]] if args.limit is not None else None
    )
    plan = build_real_llm_run_plan(
        settings=settings,
        cases=cases,
        suite="full",
        explicit_case_ids=selected_ids,
        max_workflow_calls=args.max_workflow_calls,
    )
    metadata = {
        **plan.report_metadata(),
        "evaluation_version": "baseline_v1",
        "dataset_case_count": 100,
        "replay_case_count": len(plan.case_ids),
        "otel_enabled": settings.OTEL_ENABLED,
        "langsmith_via_otlp": bool(settings.OTEL_COLLECTOR_LANGSMITH_API_KEY),
    }
    print(json.dumps(metadata, ensure_ascii=False, indent=2))
    if args.dry_run:
        print("Dry run completed; no Workflow or model request was sent.")
        return

    require_live_confirmation(args.confirm_live)
    init_tracing()
    await init_db()
    paths = await run_baseline_evaluation_v1(
        BASELINE_PATH,
        args.output_dir,
        limit=args.limit,
        execution_metadata=metadata,
    )
    print(f"JSON report: {paths['json']}")
    print(f"Markdown report: {paths['markdown']}")
    print(f"JSON snapshot: {paths['snapshot_json']}")
    print(f"Markdown snapshot: {paths['snapshot_markdown']}")


if __name__ == "__main__":
    asyncio.run(main())
