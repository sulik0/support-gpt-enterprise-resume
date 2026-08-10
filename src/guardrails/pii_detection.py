import re
from src.config import settings
from src.observability.metrics import GUARDRAIL_VIOLATIONS_TOTAL

# Regular expressions for common PII
EMAIL_REGEX = re.compile(r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+")
PHONE_REGEX = re.compile(
    r"\b(?:\+?(\d{1,3}))?[-. (]*(\d{3})[-. )]*(\d{3})[-. ]*(\d{4})\b|\b\d{3}[-.]\d{4}\b"
)
SSN_REGEX = re.compile(r"\b\d{3}-\d{2}-\d{4}\b")
CREDIT_CARD_REGEX = re.compile(r"\b(?:\d[ -]*?){13,16}\b")


def anonymize_pii(text: str) -> str:
    """
    Anonymize sensitive customer PII from incoming tickets or text.
    Replaces emails, phone numbers, SSNs, and credit cards with placeholders.
    """
    if not settings.PII_ANONYMIZATION_ENABLED or not text:
        return text

    anonymized = text

    # Track violations for prometheus
    violations_detected = False

    if EMAIL_REGEX.search(anonymized):
        anonymized = EMAIL_REGEX.sub("[EMAIL]", anonymized)
        violations_detected = True

    if PHONE_REGEX.search(anonymized):
        anonymized = PHONE_REGEX.sub("[PHONE]", anonymized)
        violations_detected = True

    if SSN_REGEX.search(anonymized):
        anonymized = SSN_REGEX.sub("[SSN]", anonymized)
        violations_detected = True

    if CREDIT_CARD_REGEX.search(anonymized):
        anonymized = CREDIT_CARD_REGEX.sub("[CREDIT_CARD]", anonymized)
        violations_detected = True

    if violations_detected:
        GUARDRAIL_VIOLATIONS_TOTAL.add(1, {"guardrail_type": "pii"})

    return anonymized
