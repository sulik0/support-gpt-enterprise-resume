from typing import List
from src.evaluation.hallucination import hallucination_evaluator

class ResponseMetricsEvaluator:
    """计算回答的 Faithfulness 和 Answer Relevance 指标。"""
    def calculate_faithfulness(self, context: List[str], response: str) -> float:
        """
        Faithfulness is the inverse of hallucination.
        Returns a score from 0.0 (low trust) to 1.0 (highly faithful).
        """
        rate = hallucination_evaluator.evaluate(context, response)
        return round(1.0 - rate, 2)

    def calculate_relevance(self, query: str, response: str) -> float:
        """
        Answer Relevance: Check if response contains words similar/relevant to the query.
        """
        if not query or not response:
            return 0.0

        query_words = set(w for w in query.lower().split() if len(w) > 3)
        if not query_words:
            return 1.0

        response_lower = response.lower()
        matched = sum(1 for kw in query_words if kw in response_lower)

        return round(matched / len(query_words), 2)

response_metrics_evaluator = ResponseMetricsEvaluator()
