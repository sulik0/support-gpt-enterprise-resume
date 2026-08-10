from typing import List

class RetrievalMetricsEvaluator:
    """计算检索上下文的 Context Precision 和 Context Recall。"""
    def calculate_precision(self, query: str, context: List[str]) -> float:
        """
        Context Precision: check if retrieved chunks contain query keywords.
        """
        if not context:
            return 0.0

        query_keywords = set(w for w in query.lower().split() if len(w) > 3)
        if not query_keywords:
            return 1.0

        relevant_chunks = 0
        for chunk in context:
            chunk_lower = chunk.lower()
            if any(k in chunk_lower for k in query_keywords):
                relevant_chunks += 1

        return round(relevant_chunks / len(context), 2)

    def calculate_recall(self, query: str, context: List[str]) -> float:
        """
        Context Recall: check what percentage of query keywords are covered in the context.
        """
        if not context:
            return 0.0

        query_keywords = list(w for w in query.lower().split() if len(w) > 3)
        if not query_keywords:
            return 1.0

        covered = 0
        combined_context = " ".join(context).lower()
        for kw in query_keywords:
            if kw in combined_context:
                covered += 1

        return round(covered / len(query_keywords), 2)

retrieval_metrics_evaluator = RetrievalMetricsEvaluator()
