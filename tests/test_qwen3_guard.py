from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from src.guardrails.qwen3_guard import (
    Qwen3GuardClient,
    Qwen3GuardResult,
    merge_qwen3_guard_result,
    parse_qwen3_guard_output,
)


def _completion(content: str):
    return SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content=content))]
    )


@pytest.mark.parametrize(
    ("content", "severity", "categories"),
    [
        ("Safety: Safe\nCategories: None", "safe", ()),
        (
            "Safety: Controversial\nCategories: Politically Sensitive Topics",
            "controversial",
            ("Politically Sensitive Topics",),
        ),
        (
            "Safety：Unsafe\nCategories：Jailbreak, PII",
            "unsafe",
            ("Jailbreak", "PII"),
        ),
    ],
)
def test_qwen3_guard_parses_official_output(content, severity, categories):
    assert parse_qwen3_guard_output(content) == (severity, categories)


def test_qwen3_guard_rejects_unstructured_output():
    with pytest.raises(ValueError, match="Safety label"):
        parse_qwen3_guard_output("The content may be risky.")


@pytest.mark.asyncio
async def test_qwen3_guard_is_disabled_without_network_call(monkeypatch):
    client = SimpleNamespace()
    client.chat = SimpleNamespace()
    client.chat.completions = SimpleNamespace(create=AsyncMock())
    guard = Qwen3GuardClient(client=client)
    monkeypatch.setattr(
        "src.guardrails.qwen3_guard.settings.QWEN3_GUARD_ENABLED", False
    )

    result = await guard.classify("hello", source="user_input")

    assert result.enabled is False
    assert result.severity == "not_run"
    client.chat.completions.create.assert_not_awaited()


@pytest.mark.asyncio
async def test_qwen3_guard_blocks_unsafe_and_jailbreak(monkeypatch):
    create = AsyncMock(
        return_value=_completion("Safety: Unsafe\nCategories: Jailbreak")
    )
    client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    guard = Qwen3GuardClient(client=client)
    monkeypatch.setattr("src.guardrails.qwen3_guard.settings.QWEN3_GUARD_ENABLED", True)
    monkeypatch.setattr(
        "src.guardrails.qwen3_guard.settings.QWEN3_GUARD_BLOCK_CONTROVERSIAL",
        False,
    )

    result = await guard.classify("semantic attack", source="user_input")

    assert result.available is True
    assert result.severity == "unsafe"
    assert result.categories == ("Jailbreak",)
    assert result.block_recommended is True
    assert result.policy_score == 0.95
    request = create.await_args.kwargs
    assert request["model"] == "Qwen/Qwen3Guard-Gen-0.6B"
    assert request["messages"] == [{"role": "user", "content": "semantic attack"}]


@pytest.mark.asyncio
async def test_qwen3_guard_controversial_policy_is_configurable(monkeypatch):
    create = AsyncMock(
        return_value=_completion("Safety: Controversial\nCategories: Unethical Acts")
    )
    client = SimpleNamespace(
        chat=SimpleNamespace(completions=SimpleNamespace(create=create))
    )
    guard = Qwen3GuardClient(client=client)
    monkeypatch.setattr("src.guardrails.qwen3_guard.settings.QWEN3_GUARD_ENABLED", True)
    monkeypatch.setattr(
        "src.guardrails.qwen3_guard.settings.QWEN3_GUARD_BLOCK_CONTROVERSIAL",
        False,
    )
    review = await guard.classify("borderline", source="user_input")

    monkeypatch.setattr(
        "src.guardrails.qwen3_guard.settings.QWEN3_GUARD_BLOCK_CONTROVERSIAL",
        True,
    )
    blocked = await guard.classify("borderline", source="user_input")

    assert review.block_recommended is False
    assert review.policy_score == 0.75
    assert blocked.block_recommended is True


@pytest.mark.asyncio
async def test_qwen3_guard_failure_degrades_without_leaking_exception(monkeypatch):
    client = SimpleNamespace(
        chat=SimpleNamespace(
            completions=SimpleNamespace(
                create=AsyncMock(side_effect=RuntimeError("secret upstream detail"))
            )
        )
    )
    guard = Qwen3GuardClient(client=client)
    monkeypatch.setattr("src.guardrails.qwen3_guard.settings.QWEN3_GUARD_ENABLED", True)

    result = await guard.classify("customer content", source="rag_document")

    assert result.degraded is True
    assert result.error_code == "RuntimeError"
    assert "secret" not in str(result.audit_record())


def test_qwen3_guard_results_merge_without_raw_content():
    first = Qwen3GuardResult(
        enabled=True,
        available=True,
        severity="safe",
        categories=(),
        source="user_input",
        model="guard-test",
        latency_seconds=0.01,
        block_recommended=False,
    )
    second = Qwen3GuardResult(
        enabled=True,
        available=True,
        severity="controversial",
        categories=("PII",),
        source="tool_result",
        model="guard-test",
        latency_seconds=0.02,
        block_recommended=False,
    )

    state = merge_qwen3_guard_result({}, first)
    state = merge_qwen3_guard_result(state, second)

    assert state["semantic_guard_label"] == "controversial"
    assert state["semantic_guard_categories"] == ["PII"]
    assert len(state["semantic_guard_checks"]) == 2
    assert "content" not in state["semantic_guard_checks"][0]
