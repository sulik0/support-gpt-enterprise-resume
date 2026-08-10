import json
from pathlib import Path

import pytest
from src.observability.token_tracking import estimate_tokens
from src.observability.cost_tracking import calculate_llm_cost
from src.observability.metrics import (
    AGENT_NODE_DURATION_SECONDS,
    AGENT_REQUESTS_TOTAL,
    HUMAN_APPROVALS_TOTAL,
    LLM_TOKENS_TOTAL,
    TOOL_CALLS_TOTAL,
)
from src.observability.sanitization import sanitize_attributes, sanitize_value
from src.observability.tracing import (
    bind_request_id,
    get_request_id,
    reset_request_id,
    set_span_attributes,
)

def test_token_estimation():
    assert estimate_tokens("") == 0
    assert estimate_tokens("hello") > 0
    # Approx 4 characters per token check
    assert estimate_tokens("hello world supportgpt") == len("hello world supportgpt") // 4

def test_cost_calculation():
    # gpt-4 cost: $0.03 input, $0.06 output per 1k tokens
    cost = calculate_llm_cost("gpt-4", 1000, 1000)
    assert cost == 0.09
    
    # gpt-4-turbo cost: $0.01 input, $0.03 output per 1k tokens
    cost_turbo = calculate_llm_cost("gpt-4-turbo", 1000, 1000)
    assert cost_turbo == 0.04
    
    # Mock cost: $0
    cost_mock = calculate_llm_cost("mock", 1000, 1000)
    assert cost_mock == 0.0

def test_prometheus_metrics_registry():
    # Verify metric label dimensions are defined
    assert "model" in LLM_TOKENS_TOTAL._labelnames
    assert "type" in LLM_TOKENS_TOTAL._labelnames
    assert "status" in AGENT_REQUESTS_TOTAL._labelnames
    assert "node" in AGENT_NODE_DURATION_SECONDS._labelnames
    assert set(TOOL_CALLS_TOTAL._labelnames) == {"tool_name", "status"}
    assert "status" in HUMAN_APPROVALS_TOTAL._labelnames


def test_observability_sanitizes_pii_secrets_and_business_fields():
    payload = sanitize_value(
        {
            "message": "Email alice@example.com, card 4111 1111 1111 1111",
            "authorization": "Bearer secret",
            "total_amount": 199.0,
            "tokens_input": 42,
        }
    )

    assert "alice@example.com" not in payload["message"]
    assert "4111 1111 1111 1111" not in payload["message"]
    assert payload["authorization"] == "[FILTERED]"
    assert payload["total_amount"] == "[FILTERED]"
    assert payload["tokens_input"] == 42


def test_span_attributes_fail_open():
    class BrokenSpan:
        def set_attributes(self, attributes):
            raise RuntimeError("exporter unavailable")

    set_span_attributes(BrokenSpan(), {"email": "alice@example.com"})


def test_request_id_context_is_scoped():
    token = bind_request_id("request-123")
    try:
        assert get_request_id() == "request-123"
    finally:
        reset_request_id(token)
    assert get_request_id() is None


def test_otel_attribute_values_are_compatible():
    attributes = sanitize_attributes(
        {"tool.payload_keys": ["customer_id", "order_id"], "context": {"email": "a@b.com"}}
    )
    assert attributes["tool.payload_keys"] == ["customer_id", "order_id"]
    assert "a@b.com" not in attributes["context"]


def test_grafana_dashboard_covers_phase_one_metrics():
    dashboard_path = Path(__file__).resolve().parents[1] / "monitoring" / "grafana-dashboard.json"
    dashboard = json.loads(dashboard_path.read_text(encoding="utf-8"))
    expressions = " ".join(
        target["expr"]
        for panel in dashboard["panels"]
        for target in panel.get("targets", [])
    )

    for metric in (
        "agent_requests_total",
        "agent_node_duration_seconds_bucket",
        "llm_tokens_total",
        "agent_tool_calls_total",
        "qa_score_ratio_bucket",
        "human_approvals_total",
    ):
        assert metric in expressions
