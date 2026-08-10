from src.config import settings
from src.observability.metrics import GUARDRAIL_VIOLATIONS_TOTAL

INJECTION_SIGNATURES = [
    "ignore previous instructions",
    "ignore all previous",
    "forget your previous",
    "forget the instructions",
    "system prompt",
    "you are now in developer mode",
    "you are now a developer",
    "bypass constraints",
    "override guidelines",
    "output the system prompt",
    "reveal your prompt",
    "print your system instructions",
    "forget your rules",
    "do not follow safety",
]


def detect_prompt_injection(text: str) -> bool:
    """
    Check if a text contains common prompt injection attack signatures.
    Returns True if an injection attempt is detected.
    """
    if not settings.PROMPT_INJECTION_PROTECTION_ENABLED or not text:
        return False

    text_lower = text.lower()
    for signature in INJECTION_SIGNATURES:
        if signature in text_lower:
            # Increment prometheus counter
            GUARDRAIL_VIOLATIONS_TOTAL.add(1, {"guardrail_type": "prompt_injection"})
            return True

    return False
