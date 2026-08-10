from src.config import settings
from src.observability.metrics import GUARDRAIL_VIOLATIONS_TOTAL

JAILBREAK_SIGNATURES = [
    "dan mode",
    "do anything now",
    "jailbreak",
    "sudo command",
    "bypass safety",
    "ignore safety guidelines",
    "override safety",
    "unfiltered model",
    "unlocked model",
    "root access",
    "run in sandbox mode",
]


def detect_jailbreak(text: str) -> bool:
    """
    Check if a text contains common jailbreak payload signatures.
    Returns True if a jailbreak attempt is detected.
    """
    if not settings.JAILBREAK_DETECTION_ENABLED or not text:
        return False

    text_lower = text.lower()
    for signature in JAILBREAK_SIGNATURES:
        if signature in text_lower:
            # Increment prometheus counter
            GUARDRAIL_VIOLATIONS_TOTAL.add(1, {"guardrail_type": "jailbreak"})
            return True

    return False
