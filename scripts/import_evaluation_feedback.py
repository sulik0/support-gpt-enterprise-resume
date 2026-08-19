import argparse
import asyncio
import json
import sys
from pathlib import Path
from statistics import mean


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.database import AsyncSessionLocal, init_db
from src.config import settings
from src.feedback.service import feedback_service


RAG_METRICS = (
    "faithfulness",
    "answer_relevancy",
    "context_precision",
    "context_recall",
)


def build_feedback_evaluation(case: dict) -> tuple[dict, bool]:
    """生成回写数据，安全用例失败时禁止进入训练候选。"""
    rag = case.get("rag_evaluation", {})
    agent = case.get("agent_evaluation", {})
    security = case.get("security_evaluation", {})
    rag_scores = [
        float(rag.get("metrics", {}).get(metric, 0.0)) for metric in RAG_METRICS
    ]
    security_passed = bool(security.get("passed", True))
    passed = (
        bool(agent.get("passed"))
        and bool(rag.get("citation_hit"))
        and mean(rag_scores) >= settings.FEEDBACK_TRAINING_MIN_RAG_SCORE
        and security_passed
    )
    metrics = {
        "rag": rag.get("metrics", {}),
        "agent": agent.get("metrics", {}),
        "security": security,
        "citation_hit": rag.get("citation_hit"),
        "rag_average": round(mean(rag_scores), 4),
    }
    return metrics, passed


def parse_args() -> argparse.Namespace:
    """解析统一离线评测报告路径。"""
    parser = argparse.ArgumentParser(
        description="Import offline evaluation results as Feedback Events."
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=PROJECT_ROOT / "evaluation" / "reports" / "evaluation_latest.json",
    )
    return parser.parse_args()


async def main() -> None:
    """把带 Agent Run ID 的离线评测结果批量回写 Feedback Pipeline。"""
    args = parse_args()
    report = json.loads(args.report.read_text(encoding="utf-8"))
    imported = 0
    skipped = 0
    failed = 0
    await init_db()
    async with AsyncSessionLocal() as db:
        for case in report.get("cases", []):
            run_id = case.get("agent_run_id")
            if not run_id:
                skipped += 1
                continue
            try:
                metrics, passed = build_feedback_evaluation(case)
                async with db.begin_nested():
                    await feedback_service.record_evaluation(
                        db,
                        agent_run_id=run_id,
                        metrics=metrics,
                        passed=passed,
                        external_ref=(f"{report.get('generated_at')}:{case.get('id')}"),
                    )
                imported += 1
            except Exception as exc:
                failed += 1
                print(
                    f"Failed to import case {case.get('id')} for run {run_id}: "
                    f"{exc.__class__.__name__}"
                )
        await db.commit()
    print(
        f"Imported evaluation feedback: {imported}; "
        f"skipped: {skipped}; failed: {failed}"
    )


if __name__ == "__main__":
    asyncio.run(main())
