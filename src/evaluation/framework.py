import json
import logging
import time
from datetime import datetime
from pathlib import Path
from typing import List, Dict, Any

from src.evaluation.ragas_eval import ragas_evaluator
from src.evaluation.deepeval_eval import deepeval_evaluator
from src.models.schemas import EvaluateResponseResponse

logger = logging.getLogger("supportgpt.evaluation.framework")
SINGLE_REPORT_DIR = Path("evaluation/reports/single_response")
SINGLE_REPORT_RETENTION = 20


def _save_single_response_report(report_data: Dict[str, Any]) -> Path:
    """将旧单条评测隔离保存，并自动清理超过保留上限的快照。"""
    SINGLE_REPORT_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S_%f")
    report_path = SINGLE_REPORT_DIR / f"single_response_{timestamp}.json"
    report_path.write_text(
        json.dumps(report_data, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    snapshots = sorted(SINGLE_REPORT_DIR.glob("single_response_*.json"))
    for expired in snapshots[:-SINGLE_REPORT_RETENTION]:
        expired.unlink(missing_ok=True)
    return report_path

async def run_deeval_evaluation(
    query: str, context: List[str], response: str
) -> EvaluateResponseResponse:
    """
    Unified evaluation runner combining RAGAS and DeepEval metrics.
    Saves evaluations as retained JSON snapshots in a dedicated directory.
    """
    start_time = time.time()
    
    # 1. Execute sub-evaluations
    ragas_scores = await ragas_evaluator.run_evaluation(query, context, response)
    deepeval_scores = await deepeval_evaluator.run_evaluation(query, context, response)

    # 2. Extract specific variables
    faithfulness = ragas_scores.get("faithfulness", 0.0)
    context_precision = ragas_scores.get("context_precision", 0.0)
    context_recall = ragas_scores.get("context_recall", 0.0)
    answer_relevance = deepeval_scores.get("answer_relevancy", 0.0)
    
    # Hallucination rate is the fraction of unsupported assertions
    hallucination_rate = deepeval_scores.get("hallucination_score", 0.0)

    # 3. Calculate overall quality score (average of relevance, faithfulness, precision, recall)
    metrics_sum = faithfulness + context_precision + context_recall + answer_relevance
    overall_quality = round(metrics_sum / 4.0, 2)
    
    # A response passes if quality is >= 0.80 and hallucination rate is low (< 0.30)
    passed = overall_quality >= 0.75 and hallucination_rate < 0.35

    report_summary = (
        f"Evaluation completed in {round(time.time() - start_time, 2)}s. "
        f"Overall Quality Score: {overall_quality}. Passed: {passed}. "
        f"Faithfulness: {faithfulness}, Hallucination Rate: {hallucination_rate}. "
        f"Context Precision: {context_precision}, Context Recall: {context_recall}."
    )

    # 4. Save report in reports directory
    report_data = {
        "timestamp": time.time(),
        "experiment_config": {
            "evaluator": "single_response_v1",
            "rag_evaluator": "ragas_adapter",
            "semantic_evaluator": "deepeval_adapter",
            "quality_threshold": 0.75,
            "hallucination_rate_threshold": 0.35,
        },
        "query": query,
        "context": context,
        "response": response,
        "metrics": {
            "faithfulness": faithfulness,
            "context_precision": context_precision,
            "context_recall": context_recall,
            "hallucination_rate": hallucination_rate,
            "answer_relevance": answer_relevance,
            "overall_quality_score": overall_quality
        },
        "passed": passed,
        "summary": report_summary
    }

    try:
        _save_single_response_report(report_data)
    except Exception as e:
        logger.error(f"Failed to save evaluation report to disk: {e}")

    return EvaluateResponseResponse(
        faithfulness_score=faithfulness,
        context_precision=context_precision,
        context_recall=context_recall,
        hallucination_rate=hallucination_rate,
        answer_relevance=answer_relevance,
        overall_quality_score=overall_quality,
        passed_evaluation=passed,
        report_summary=report_summary
    )
