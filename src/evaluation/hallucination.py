from typing import List

class HallucinationEvaluator:
    """通过回答与上下文的词项覆盖率估算幻觉风险。"""
    def _get_stem(self, word: str) -> str:
        """Lightweight stemmer to normalize plurals and basic verb inflections."""
        w = word.lower()
        if w.endswith("ies"):
            w = w[:-3] + "y"
        elif w.endswith("s") and not w.endswith("ss"):
            w = w[:-1]
        if w.endswith("ing"):
            w = w[:-3]
        elif w.endswith("ed"):
            w = w[:-2]
        return w

    def evaluate(self, context: List[str], response: str) -> float:
        """
        Calculate a hallucination rate (0.0 means no hallucination, 1.0 means fully hallucinated).
        """
        if not context:
            return 1.0  # If no context is provided, we assume the response is hallucinated or unsupported.
            
        if not response:
            return 0.0

        # Heuristic word overlap checking
        context_stems = set()
        for doc in context:
            for word in doc.lower().split():
                # Clean word
                clean = "".join(c for c in word if c.isalnum())
                if len(clean) > 3:
                    context_stems.add(self._get_stem(clean))

        response_words = response.lower().split()
        unsupported_count = 0
        total_evaluable = 0

        for word in response_words:
            clean = "".join(c for c in word if c.isalnum())
            if len(clean) > 3:
                total_evaluable += 1
                stem = self._get_stem(clean)
                if stem not in context_stems:
                    unsupported_count += 1

        if total_evaluable == 0:
            return 0.0

        rate = unsupported_count / total_evaluable
        return round(min(1.0, rate), 2)

hallucination_evaluator = HallucinationEvaluator()
