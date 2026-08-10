"""Independent, dataset-driven offline evaluation for the support RAG workflow."""

import asyncio
import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from statistics import mean
from typing import Any, Awaitable, Callable, Dict, List, Optional, Sequence

from src.evaluation.response_metrics import response_metrics_evaluator
from src.evaluation.retrieval_metrics import retrieval_metrics_evaluator


METRIC_KEYS = (
    "faithfulness",
    "answer_relevancy",
    "context_precision",
    "context_recall",
)


@dataclass(frozen=True)
class EvaluationCase:
    """定义一条离线 RAG 评测样本及其标准答案和期望来源。"""

    id: str
    query: str
    reference_answer: str
    expected_sources: List[str]
    category: str
    risk_level: str
    kb_version: str = "v1"


@dataclass
class EvaluationRecord:
    """保存单条样本的 Workflow 输出、检索上下文和指标结果。"""

    case: EvaluationCase
    response: str
    contexts: List[str]
    retrieved_sources: List[str]
    metrics: Dict[str, float]
    workflow_errors: List[str]


WorkflowRunner = Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]]


def load_evaluation_dataset(path: Path) -> List[EvaluationCase]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    raw_cases = payload.get("cases", payload) if isinstance(payload, dict) else payload
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ValueError("Evaluation dataset must contain a non-empty 'cases' list.")

    cases = [EvaluationCase(**item) for item in raw_cases]
    ids = [case.id for case in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("Evaluation case ids must be unique.")
    return cases


async def collect_workflow_records(
    cases: Sequence[EvaluationCase],
    workflow_runner: Optional[WorkflowRunner] = None,
) -> List[EvaluationRecord]:
    if workflow_runner is None:
        from src.agents.graph import run_agent_workflow

        workflow_runner = run_agent_workflow

    records: List[EvaluationRecord] = []
    for index, case in enumerate(cases):
        output = await workflow_runner(
            {
                "ticket_id": 10000 + index,
                "customer_id": f"offline_eval_{case.id}",
                "subject": f"Offline evaluation: {case.category}",
                "description": case.query,
                "kb_version": case.kb_version,
                "operator_role": "agent",
            }
        )
        citations = output.get("context_citations", [])
        records.append(
            EvaluationRecord(
                case=case,
                response=output.get("suggested_response", ""),
                contexts=[_citation_field(citation, "text") for citation in citations],
                retrieved_sources=[_citation_field(citation, "source") for citation in citations],
                metrics={},
                workflow_errors=list(output.get("errors", [])),
            )
        )
    return records


def _citation_field(citation: Any, field: str) -> str:
    if isinstance(citation, dict):
        return str(citation.get(field, ""))
    return str(getattr(citation, field, ""))


async def score_records(records: Sequence[EvaluationRecord], engine: str) -> None:
    if engine == "local":
        for record in records:
            record.metrics = _local_scores(record)
        return
    if engine != "ragas":
        raise ValueError("engine must be either 'ragas' or 'local'.")
    _validate_ragas_environment()
    scores = await asyncio.to_thread(_run_ragas, records)
    if len(scores) != len(records):
        raise RuntimeError(
            f"Ragas returned {len(scores)} result rows for {len(records)} evaluation cases."
        )
    for record, row in zip(records, scores):
        record.metrics = row


def _validate_ragas_environment() -> None:
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key or api_key.startswith("your-"):
        raise RuntimeError(
            "Ragas engine requires a valid OPENAI_API_KEY for its evaluator LLM and embeddings. "
            "Use --engine local only for an offline smoke test."
        )


def _run_ragas(records: Sequence[EvaluationRecord]) -> List[Dict[str, float]]:
    """Run the version-pinned Ragas 0.1 batch API and normalize its column names."""
    try:
        from datasets import Dataset
        from ragas import evaluate
        from ragas.metrics import (
            answer_relevancy,
            context_precision,
            context_recall,
            faithfulness,
        )
    except ImportError as exc:
        raise RuntimeError(
            "Ragas dependencies are unavailable or incompatible. Install requirements/eval.txt."
        ) from exc

    dataset = Dataset.from_dict(
        {
            "question": [record.case.query for record in records],
            "answer": [record.response for record in records],
            "contexts": [record.contexts for record in records],
            "ground_truth": [record.case.reference_answer for record in records],
        }
    )
    result = evaluate(
        dataset=dataset,
        metrics=[faithfulness, answer_relevancy, context_precision, context_recall],
        raise_exceptions=False,
    )
    rows = result.to_pandas().to_dict(orient="records")
    return [
        {
            "faithfulness": _finite_score(row.get("faithfulness")),
            "answer_relevancy": _finite_score(
                row.get("answer_relevancy", row.get("answer_relevance"))
            ),
            "context_precision": _finite_score(row.get("context_precision")),
            "context_recall": _finite_score(row.get("context_recall")),
        }
        for row in rows
    ]


def _finite_score(value: Any) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0
    return round(score, 4) if score == score else 0.0


def _local_scores(record: EvaluationRecord) -> Dict[str, float]:
    """Deterministic proxies for CI; these are explicitly not reported as Ragas."""
    return {
        "faithfulness": response_metrics_evaluator.calculate_faithfulness(
            record.contexts, record.response
        ),
        "answer_relevancy": response_metrics_evaluator.calculate_relevance(
            record.case.query, record.response
        ),
        "context_precision": retrieval_metrics_evaluator.calculate_precision(
            record.case.query, record.contexts
        ),
        "context_recall": retrieval_metrics_evaluator.calculate_recall(
            record.case.reference_answer, record.contexts
        ),
    }


def build_report(
    records: Sequence[EvaluationRecord],
    *,
    engine: str,
    dataset_path: Path,
) -> Dict[str, Any]:
    aggregates = {
        metric: round(mean(record.metrics.get(metric, 0.0) for record in records), 4)
        for metric in METRIC_KEYS
    }
    case_rows = []
    for record in records:
        expected = set(record.case.expected_sources)
        actual = set(record.retrieved_sources)
        case_rows.append(
            {
                **asdict(record.case),
                "response": record.response,
                "contexts": record.contexts,
                "retrieved_sources": record.retrieved_sources,
                "citation_hit": not expected or bool(expected & actual),
                "metrics": record.metrics,
                "workflow_errors": record.workflow_errors,
            }
        )

    return {
        "schema_version": "1.0",
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "engine": engine,
        "dataset": str(dataset_path),
        "case_count": len(records),
        "aggregates": aggregates,
        "citation_hit_rate": round(
            mean(1.0 if row["citation_hit"] else 0.0 for row in case_rows), 4
        ),
        "cases": case_rows,
    }


def write_report(report: Dict[str, Any], output_dir: Path) -> Dict[str, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / "agent_eval_latest.json"
    markdown_path = output_dir / "agent_eval_latest.md"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown_path.write_text(_render_markdown(report), encoding="utf-8")
    return {"json": json_path, "markdown": markdown_path}


def _render_markdown(report: Dict[str, Any]) -> str:
    aggregates = report["aggregates"]
    lines = [
        "# Agent Evaluation 评测报告",
        "",
        f"- 生成时间：`{report['generated_at']}`",
        f"- 评测引擎：`{report['engine']}`",
        f"- 数据集：`{report['dataset']}`",
        f"- 用例数：`{report['case_count']}`",
        "",
        "## 汇总指标",
        "",
        "| Faithfulness | Answer Relevancy | Context Precision | Context Recall | Citation Hit Rate |",
        "|---:|---:|---:|---:|---:|",
        (
            f"| {aggregates['faithfulness']:.4f} | {aggregates['answer_relevancy']:.4f} "
            f"| {aggregates['context_precision']:.4f} | {aggregates['context_recall']:.4f} "
            f"| {report['citation_hit_rate']:.4f} |"
        ),
        "",
        "## 用例明细",
        "",
        "| ID | 类别 | KB | Faithfulness | Relevancy | Precision | Recall | Citation |",
        "|---|---|---|---:|---:|---:|---:|---|",
    ]
    for row in report["cases"]:
        metrics = row["metrics"]
        lines.append(
            f"| {row['id']} | {row['category']} | {row['kb_version']} "
            f"| {metrics['faithfulness']:.4f} | {metrics['answer_relevancy']:.4f} "
            f"| {metrics['context_precision']:.4f} | {metrics['context_recall']:.4f} "
            f"| {'hit' if row['citation_hit'] else 'miss'} |"
        )
    lines.extend(
        [
            "",
            "> `ragas` 表示正式 Ragas 指标；`local` 仅是无网络回归烟测的确定性 proxy，不得作为 Ragas 结果对外引用。",
            "",
        ]
    )
    return "\n".join(lines)


async def run_offline_evaluation(
    dataset_path: Path,
    output_dir: Path,
    *,
    engine: str = "ragas",
    limit: Optional[int] = None,
    workflow_runner: Optional[WorkflowRunner] = None,
) -> Dict[str, Path]:
    cases = load_evaluation_dataset(dataset_path)
    if limit is not None:
        if limit < 1:
            raise ValueError("limit must be greater than zero.")
        cases = cases[:limit]
    records = await collect_workflow_records(cases, workflow_runner)
    await score_records(records, engine)
    report = build_report(records, engine=engine, dataset_path=dataset_path)
    return write_report(report, output_dir)
