from src.config import settings
from src.observability.metrics import GUARDRAIL_VIOLATIONS_TOTAL

LEAK_SIGNATURES = [
    "system prompt",
    "retrieved context",
    "rag pipeline",
    "agent state",
    "langgraph",
    "vector store",
    "you are a ticket analysis agent",
    "you are a knowledge retrieval agent",
    "you are a quality assurance agent",
    "you are an escalation agent",
    "you are a resolution agent",
]

FALLBACK_RESPONSE = (
    "I apologize for the inconvenience. Let me look up the details in our documentation "
    "and get back to you with the correct guidance."
)


def filter_response(text: str) -> str:
    """
    Filter LLM response content to avoid leaking system instructions or internal architecture.
    """
    if not settings.RESPONSE_FILTERING_ENABLED or not text:
        return text

    text_lower = text.lower()
    leaked = False

    for signature in LEAK_SIGNATURES:
        if signature in text_lower:
            leaked = True
            break

    if leaked:
        # Increment prometheus counter
        GUARDRAIL_VIOLATIONS_TOTAL.add(1, {"guardrail_type": "response_filter"})
        return FALLBACK_RESPONSE

    return text
