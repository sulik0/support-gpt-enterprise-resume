import os
import logging
from typing import List, Dict, Any
from src.evaluation.response_metrics import response_metrics_evaluator
from src.evaluation.retrieval_metrics import retrieval_metrics_evaluator

logger = logging.getLogger("supportgpt.evaluation.ragas")

class RagasEvaluator:
    """封装 Ragas 的 RAG 质量评测流程。

    缺少真实模型凭据时回退本地语义指标。
    """
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")

    async def run_evaluation(
        self, query: str, context: List[str], response: str
    ) -> Dict[str, float]:
        if self.api_key and not self.api_key.startswith("your-"):
            try:
                # Real Ragas metrics computation
                from ragas import evaluate
                from ragas.metrics import faithfulness, answer_relevance, context_precision, context_recall
                from datasets import Dataset

                data = {
                    "question": [query],
                    "contexts": [context],
                    "answer": [response],
                    "ground_truths": [[query]] # Ground truth default to query for simplified mapping
                }
                dataset = Dataset.from_dict(data)
                
                logger.info("Triggering real Ragas dataset evaluation...")
                result = evaluate(
                    dataset=dataset,
                    metrics=[faithfulness, answer_relevance, context_precision, context_recall]
                )
                return {
                    "faithfulness": float(result["faithfulness"]),
                    "answer_relevance": float(result["answer_relevance"]),
                    "context_precision": float(result["context_precision"]),
                    "context_recall": float(result["context_recall"])
                }
            except Exception as e:
                logger.warning(f"Ragas execution failed, using local metric fallbacks. Error: {e}")

        # Local heuristics fallback
        faithfulness_score = response_metrics_evaluator.calculate_faithfulness(context, response)
        relevance_score = response_metrics_evaluator.calculate_relevance(query, response)
        precision_score = retrieval_metrics_evaluator.calculate_precision(query, context)
        recall_score = retrieval_metrics_evaluator.calculate_recall(query, context)

        return {
            "faithfulness": faithfulness_score,
            "answer_relevance": relevance_score,
            "context_precision": precision_score,
            "context_recall": recall_score
        }

ragas_evaluator = RagasEvaluator()
