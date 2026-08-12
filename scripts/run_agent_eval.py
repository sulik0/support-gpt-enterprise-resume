import argparse
import asyncio
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.database import init_db
from src.evaluation.offline_rag import run_offline_evaluation
from src.observability.tracing import init_tracing


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Dataset + Workflow Replay RAG/Agent evaluation."
    )
    parser.add_argument(
        "--dataset",
        type=Path,
        default=PROJECT_ROOT / "evaluation" / "golden" / "support_qa_golden.json",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "evaluation" / "reports",
    )
    parser.add_argument(
        "--rag-engine", choices=("ragas", "local"), default="ragas"
    )
    parser.add_argument(
        "--agent-engine", choices=("deepeval", "local"), default="deepeval"
    )
    parser.add_argument(
        "--engine",
        choices=("ragas", "local"),
        default=None,
        help="Deprecated compatibility option; prefer separate engine flags.",
    )
    parser.add_argument("--limit", type=int, default=None)
    return parser.parse_args()


async def main() -> None:
    args = parse_args()
    if args.engine is not None:
        args.rag_engine = args.engine
        if args.engine == "local":
            args.agent_engine = "local"
    init_tracing()
    await init_db()
    paths = await run_offline_evaluation(
        dataset_path=args.dataset,
        output_dir=args.output_dir,
        rag_engine=args.rag_engine,
        agent_engine=args.agent_engine,
        limit=args.limit,
    )
    print(f"JSON report: {paths['json']}")
    print(f"Markdown report: {paths['markdown']}")


if __name__ == "__main__":
    asyncio.run(main())
