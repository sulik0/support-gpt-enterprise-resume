import asyncio
from uuid import uuid4

import pytest
from pydantic import BaseModel

from src.config import settings
from src.rag.vector_store import vector_store
from src.resilience.circuit_breaker import circuit_breakers
from src.resilience.context import begin_resilience_scope, finish_resilience_scope
from src.resilience.executor import resilience_executor
from src.resilience.models import (
    DegradationLevel,
    OperationType,
    ResiliencePolicy,
)
from src.risk.engine import RiskEngine
from src.tools.registry import ToolDefinition, ToolRegistry


def _policy(**overrides):
    values = {
        "timeout_seconds": 0.2,
        "max_retries": 0,
        "circuit_failure_threshold": 3,
        "circuit_recovery_seconds": 30.0,
        "failure_degradation": DegradationLevel.PARTIAL,
    }
    values.update(overrides)
    return ResiliencePolicy(**values)


@pytest.fixture(autouse=True)
def configure_resilience(monkeypatch):
    monkeypatch.setattr(settings, "RESILIENCE_ENABLED", True)
    monkeypatch.setattr(settings, "RESILIENCE_RETRY_BASE_DELAY_SECONDS", 0.0)


@pytest.mark.asyncio
async def test_transient_failure_retries_once_and_recovers():
    attempts = 0

    async def flaky_call():
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise TimeoutError("temporary")
        return "ok"

    result = await resilience_executor.execute(
        component="llm",
        operation="qa",
        call=flaky_call,
        policy=_policy(max_retries=1),
        circuit_key=f"test:{uuid4()}",
    )

    assert result.unwrap() == "ok"
    assert result.event.status == "recovered"
    assert result.event.attempts == 2


@pytest.mark.asyncio
async def test_non_retryable_failure_is_not_retried():
    attempts = 0

    async def invalid_call():
        nonlocal attempts
        attempts += 1
        raise ValueError("invalid request")

    result = await resilience_executor.execute(
        component="tool",
        operation="invalid",
        call=invalid_call,
        policy=_policy(max_retries=2),
        circuit_key=f"test:{uuid4()}",
    )

    assert result.success is False
    assert result.event.attempts == 1
    assert attempts == 1


@pytest.mark.asyncio
async def test_fallback_returns_degraded_success_and_collects_event():
    async def unavailable():
        raise ConnectionError("primary unavailable")

    token = begin_resilience_scope()
    result = await resilience_executor.execute(
        component="llm",
        operation="resolver",
        call=unavailable,
        policy=_policy(),
        fallback=lambda: "backup reply",
        fallback_name="backup-model",
        circuit_key=f"test:{uuid4()}",
    )
    events = finish_resilience_scope(token)

    assert result.unwrap() == "backup reply"
    assert result.event.degradation_level is DegradationLevel.PARTIAL
    assert result.event.fallback_used == "backup-model"
    assert [event.status for event in events] == ["fallback"]


@pytest.mark.asyncio
async def test_circuit_opens_and_fast_fails_after_threshold():
    key = f"test:{uuid4()}"

    async def unavailable():
        raise TimeoutError("down")

    policy = _policy(circuit_failure_threshold=2)
    first = await resilience_executor.execute(
        component="rag", operation="vector", call=unavailable, policy=policy,
        circuit_key=key,
    )
    second = await resilience_executor.execute(
        component="rag", operation="vector", call=unavailable, policy=policy,
        circuit_key=key,
    )
    third = await resilience_executor.execute(
        component="rag", operation="vector", call=unavailable, policy=policy,
        circuit_key=key,
    )

    assert first.event.status == "failed"
    assert second.event.circuit_state == "open"
    assert third.event.status == "circuit_open"
    assert third.event.attempts == 0


def test_non_idempotent_write_cannot_enable_retry():
    with pytest.raises(ValueError, match="cannot be retried"):
        ResiliencePolicy(
            timeout_seconds=1.0,
            max_retries=1,
            operation_type=OperationType.WRITE,
            idempotent=False,
        )


@pytest.mark.asyncio
async def test_cancellation_is_never_swallowed():
    async def cancelled():
        raise asyncio.CancelledError()

    with pytest.raises(asyncio.CancelledError):
        await resilience_executor.execute(
            component="llm",
            operation="chat",
            call=cancelled,
            policy=_policy(max_retries=2),
            circuit_key=f"test:{uuid4()}",
        )


@pytest.mark.asyncio
async def test_low_risk_read_tool_retries_but_high_risk_tool_does_not(monkeypatch):
    class ToolInput(BaseModel):
        value: str

    attempts = {"read": 0, "high": 0}

    def flaky_read(value: str):
        attempts["read"] += 1
        if attempts["read"] == 1:
            raise TimeoutError("temporary")
        return {"value": value}

    def failing_high_risk(value: str):
        attempts["high"] += 1
        raise TimeoutError("temporary")

    monkeypatch.setattr(settings, "RESILIENCE_TOOL_READ_MAX_RETRIES", 1)
    registry = ToolRegistry()
    registry.register(
        ToolDefinition(
            name="test.read",
            description="read",
            input_schema=ToolInput,
            output_schema={"value": "str"},
            min_role="agent",
            timeout_seconds=0.2,
            mocked=True,
            handler=flaky_read,
        )
    )
    registry.register(
        ToolDefinition(
            name="test.high",
            description="high risk",
            input_schema=ToolInput,
            output_schema={"value": "str"},
            min_role="agent",
            timeout_seconds=0.2,
            mocked=True,
            handler=failing_high_risk,
            risk_level="high",
        )
    )

    read_result = await registry.call_tool("test.read", {"value": "ok"})
    high_result = await registry.call_tool(
        "test.high", {"value": "x"}, request_risk_level="high"
    )

    assert read_result["status"] == "success"
    assert read_result["attempts"] == 2
    assert attempts["read"] == 2
    assert high_result["status"] == "timeout"
    assert high_result["attempts"] == 1
    assert attempts["high"] == 1


@pytest.mark.asyncio
async def test_hybrid_rag_uses_lexical_results_when_vector_path_fails(monkeypatch):
    async def embedding(_query: str):
        return [0.1, 0.2]

    def broken_vector_query(**_kwargs):
        raise ConnectionError("vector unavailable")

    def lexical_records(**_kwargs):
        return {
            "documents": ["Refund requests must be submitted within 30 days."],
            "metadatas": [
                {
                    "doc_id": "refund",
                    "chunk_index": 0,
                    "title": "Refund Policy",
                    "version": "v1",
                }
            ],
        }

    await circuit_breakers.clear()
    monkeypatch.setattr(
        "src.rag.vector_store.embedding_provider.get_embedding", embedding
    )
    monkeypatch.setattr(vector_store.collection, "query", broken_vector_query)
    monkeypatch.setattr(vector_store.collection, "get", lexical_records)

    citations = await vector_store.query_kb("refund within 30 days", version="v1")

    assert len(citations) == 1
    assert citations[0].source == "Refund Policy (v1)"
    await circuit_breakers.clear()


def test_risk_engine_routes_required_dependency_degradation_to_human():
    assessment = RiskEngine().assess(
        {"degradation_level": "human_required"}, stage="final"
    )

    assert assessment.requires_human is True
    assert "dependency_requires_human" in assessment.reasons


@pytest.mark.asyncio
async def test_agent_node_collects_dependency_degradation_in_state():
    from src.agents.graph import _run_node, build_ticket_state

    async def handler(state):
        async def unavailable():
            raise ConnectionError("primary unavailable")

        result = await resilience_executor.execute(
            component="llm",
            operation="resolver",
            call=unavailable,
            policy=_policy(),
            fallback=lambda: "backup reply",
            fallback_name="backup-model",
            circuit_key=f"test:{uuid4()}",
        )
        assert result.success is True
        return state

    state = build_ticket_state({"ticket_id": 1, "description": "help"})
    result = await _run_node("test_node", handler, state)

    assert result["degradation_level"] == "partial"
    assert result["fallbacks_used"] == ["backup-model"]
    assert result["dependency_events"][0]["status"] == "fallback"
