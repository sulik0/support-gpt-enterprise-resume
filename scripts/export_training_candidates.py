import argparse
import asyncio
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.database import AsyncSessionLocal, init_db
from src.feedback.service import feedback_service


def parse_args() -> argparse.Namespace:
    """解析训练候选集导出目录。"""
    parser = argparse.ArgumentParser(
        description="Export PII-redacted SFT and DPO candidate datasets."
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "evaluation" / "training_candidates",
    )
    return parser.parse_args()


async def main() -> None:
    """初始化数据表并导出通过质量门控的 JSONL 候选集。"""
    args = parse_args()
    await init_db()
    async with AsyncSessionLocal() as db:
        summary = await feedback_service.export_training_candidates(db, args.output_dir)
    print(f"SFT candidates: {summary['sft_count']} -> {summary['sft_path']}")
    print(f"DPO candidates: {summary['dpo_count']} -> {summary['dpo_path']}")
    print(f"Manifest: {summary['manifest_path']}")


if __name__ == "__main__":
    asyncio.run(main())
