"""Qwen3Guard-Gen-0.6B 语义安全分类 Adapter。"""

import logging
import re
import time
from dataclasses import dataclass
from typing import Any, Mapping

from src.config import settings
from src.observability.metrics import (
    GUARDRAIL_VIOLATIONS_TOTAL,
    SEMANTIC_GUARD_CHECKS_TOTAL,
    SEMANTIC_GUARD_DURATION_SECONDS,
)
from src.observability.tracing import get_tracer, observed_span, set_span_attributes

logger = logging.getLogger("supportgpt.guardrails.qwen3_guard")
tracer = get_tracer(__name__)

_SAFETY_PATTERN = re.compile(
    r"Safety\s*[:：]\s*(Safe|Unsafe|Controversial)", re.IGNORECASE
)
_CATEGORIES_PATTERN = re.compile(r"Categories?\s*[:：]\s*([^\r\n]+)", re.IGNORECASE)
_SEVERITY_RANK = {"not_run": -1, "safe": 0, "controversial": 1, "unsafe": 2}
_POLICY_SCORES = {"not_run": 0.0, "safe": 0.0, "controversial": 0.75, "unsafe": 0.95}


@dataclass(frozen=True)
class Qwen3GuardResult:
    """保存语义安全结论，不包含原始输入或模型原文。"""

    enabled: bool
    available: bool
    severity: str
    categories: tuple[str, ...]
    source: str
    model: str
    latency_seconds: float
    block_recommended: bool
    error_code: str | None = None

    @property
    def degraded(self) -> bool:
        return self.enabled and not self.available

    @property
    def policy_score(self) -> float:
        return _POLICY_SCORES.get(self.severity, 0.0)

    def audit_record(self) -> dict[str, Any]:
        """输出可写入 State 和 Trace 的最小审计记录。"""
        return {
            "source": self.source,
            "status": (
                "disabled"
                if not self.enabled
                else "success" if self.available else "error"
            ),
            "severity": self.severity,
            "categories": list(self.categories),
            "model": self.model,
            "latency_seconds": self.latency_seconds,
            "block_recommended": self.block_recommended,
            "error_code": self.error_code,
        }


class Qwen3GuardClient:
    """通过独立 OpenAI-compatible 端点调用 Qwen3Guard。"""

    def __init__(self, client: Any | None = None):
        self._client = client

    def _get_client(self) -> Any:
        if self._client is None:
            from openai import AsyncOpenAI

            self._client = AsyncOpenAI(
                api_key=settings.QWEN3_GUARD_API_KEY,
                base_url=settings.QWEN3_GUARD_BASE_URL,
                timeout=settings.QWEN3_GUARD_TIMEOUT_SECONDS,
                max_retries=settings.QWEN3_GUARD_MAX_RETRIES,
            )
        return self._client

    async def classify(self, text: str, *, source: str) -> Qwen3GuardResult:
        """对单个信任边界的内容执行语义安全检查。"""
        model = settings.QWEN3_GUARD_MODEL_NAME
        if not settings.QWEN3_GUARD_ENABLED:
            return Qwen3GuardResult(
                enabled=False,
                available=False,
                severity="not_run",
                categories=(),
                source=source,
                model=model,
                latency_seconds=0.0,
                block_recommended=False,
            )
        if not text.strip():
            return Qwen3GuardResult(
                enabled=True,
                available=True,
                severity="safe",
                categories=(),
                source=source,
                model=model,
                latency_seconds=0.0,
                block_recommended=False,
            )

        started = time.perf_counter()
        try:
            with observed_span(
                tracer,
                "supportgpt.guardrails.qwen3guard",
                {
                    "guardrail.source": source,
                    "guardrail.model": model,
                    "guardrail.input_length": min(
                        len(text), settings.QWEN3_GUARD_MAX_INPUT_CHARS
                    ),
                },
            ) as span:
                response = await self._get_client().chat.completions.create(
                    model=model,
                    messages=[
                        {
                            "role": "user",
                            "content": text[: settings.QWEN3_GUARD_MAX_INPUT_CHARS],
                        }
                    ],
                    temperature=0.0,
                    max_tokens=128,
                )
                content = response.choices[0].message.content or ""
                severity, categories = parse_qwen3_guard_output(content)
                block = severity == "unsafe" or "jailbreak" in {
                    category.lower() for category in categories
                }
                if (
                    severity == "controversial"
                    and settings.QWEN3_GUARD_BLOCK_CONTROVERSIAL
                ):
                    block = True
                result = Qwen3GuardResult(
                    enabled=True,
                    available=True,
                    severity=severity,
                    categories=categories,
                    source=source,
                    model=model,
                    latency_seconds=round(time.perf_counter() - started, 4),
                    block_recommended=block,
                )
                set_span_attributes(
                    span,
                    {
                        "guardrail.status": "success",
                        "guardrail.severity": result.severity,
                        "guardrail.categories": list(result.categories),
                        "guardrail.block_recommended": result.block_recommended,
                    },
                )
        except Exception as exc:
            result = Qwen3GuardResult(
                enabled=True,
                available=False,
                severity="not_run",
                categories=(),
                source=source,
                model=model,
                latency_seconds=round(time.perf_counter() - started, 4),
                block_recommended=False,
                error_code=exc.__class__.__name__,
            )
            logger.warning(
                "qwen3guard unavailable",
                extra={
                    "security_source": source,
                    "guard_model": model,
                    "error_code": result.error_code,
                },
            )

        self._record_metrics(result)
        logger.info(
            "qwen3guard completed",
            extra={
                "security_source": source,
                "severity": result.severity,
                "categories": ",".join(result.categories),
                "block_recommended": result.block_recommended,
                "degraded": result.degraded,
            },
        )
        return result

    @staticmethod
    def _record_metrics(result: Qwen3GuardResult) -> None:
        """观测失败不影响安全决策或业务主流程。"""
        try:
            status = "success" if result.available else "error"
            SEMANTIC_GUARD_CHECKS_TOTAL.add(
                1,
                {
                    "source": result.source,
                    "status": status,
                    "severity": result.severity,
                },
            )
            SEMANTIC_GUARD_DURATION_SECONDS.record(
                result.latency_seconds, {"source": result.source, "status": status}
            )
            if result.block_recommended:
                GUARDRAIL_VIOLATIONS_TOTAL.add(
                    1, {"guardrail_type": f"qwen3guard_{result.source}"}
                )
        except Exception:
            logger.debug("Unable to record Qwen3Guard metrics")


def parse_qwen3_guard_output(content: str) -> tuple[str, tuple[str, ...]]:
    """解析官方 `Safety` / `Categories` 结构化输出。"""
    safety_match = _SAFETY_PATTERN.search(content or "")
    if not safety_match:
        raise ValueError("Qwen3Guard response did not contain a Safety label.")
    severity = safety_match.group(1).lower()
    categories_match = _CATEGORIES_PATTERN.search(content or "")
    raw_categories = categories_match.group(1) if categories_match else ""
    categories = []
    for item in re.split(r"[,;，；|]", raw_categories):
        category = re.sub(r"[^\w\s&\-]", "", item, flags=re.UNICODE).strip()
        if category and category.lower() != "none":
            categories.append(category[:80])
    return severity, tuple(dict.fromkeys(categories[:10]))


def merge_qwen3_guard_result(
    state: Mapping[str, Any], result: Qwen3GuardResult
) -> dict[str, Any]:
    """将多个信任边界的结论聚合到 Agent State。"""
    if not result.enabled:
        return dict(state)

    current_label = str(state.get("semantic_guard_label", "not_run"))
    worst_label = max(
        (current_label, result.severity), key=lambda item: _SEVERITY_RANK.get(item, -1)
    )
    categories = list(state.get("semantic_guard_categories", []))
    categories.extend(result.categories)
    checks = list(state.get("semantic_guard_checks", []))
    checks.append(result.audit_record())
    return {
        **state,
        "semantic_guard_label": worst_label,
        "semantic_guard_categories": list(dict.fromkeys(categories)),
        "semantic_guard_checks": checks,
        "semantic_guard_degraded": bool(state.get("semantic_guard_degraded"))
        or result.degraded,
        "semantic_guard_model": result.model,
    }


qwen3_guard = Qwen3GuardClient()
