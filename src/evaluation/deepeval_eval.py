import os
import logging
from typing import List, Dict, Any
from src.evaluation.hallucination import hallucination_evaluator
from src.evaluation.response_metrics import response_metrics_evaluator

logger = logging.getLogger("supportgpt.evaluation.deepeval")

class DeepEvalEvaluator:
    """封装 DeepEval 回复质量评测流程。

    外部条件不满足时回退本地确定性评测器。
    """
    def __init__(self):
        self.api_key = os.getenv("OPENAI_API_KEY")

    async def run_evaluation(
        self, query: str, context: List[str], response: str
    ) -> Dict[str, Any]:
        if self.api_key and not self.api_key.startswith("your-"):
            try:
                # Real DeepEval execution
                from deepeval.test_case import LLMTestCase
                from deepeval.metrics import HallucinationMetric, AnswerRelevancyMetric

                test_case = LLMTestCase(
                    input=query,
                    actual_output=response,
                    retrieval_context=context
                )

                hallucination_metric = HallucinationMetric(threshold=0.5)
                answer_relevancy = AnswerRelevancyMetric(threshold=0.5)

                logger.info("Triggering real DeepEval test case checks...")
                hallucination_metric.measure(test_case)
                answer_relevancy.measure(test_case)

                return {
                    "hallucination_score": float(hallucination_metric.score),
                    "hallucination_passed": bool(hallucination_metric.is_successful()),
                    "answer_relevancy": float(answer_relevancy.score)
                }
            except Exception as e:
                logger.warning(f"DeepEval execution failed, using local metric fallbacks. Error: {e}")

        # Local heuristics fallback
        h_rate = hallucination_evaluator.evaluate(context, response)
        rel_score = response_metrics_evaluator.calculate_relevance(query, response)

        return {
            "hallucination_score": h_rate,
            "hallucination_passed": h_rate < 0.5,
            "answer_relevancy": rel_score
        }

deepeval_evaluator = DeepEvalEvaluator()
