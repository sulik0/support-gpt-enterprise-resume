import json
import logging
from pathlib import Path

import pytest
from src.observability.token_tracking import estimate_tokens
from src.observability.cost_tracking import calculate_llm_cost
from src.observability.metrics import (
    AGENT_NODE_DURATION_SECONDS,
    AGENT_REQUESTS_TOTAL,
    FEEDBACK_EVENTS_TOTAL,
    HUMAN_APPROVALS_TOTAL,
    LLM_TOKENS_TOTAL,
    TOOL_CALLS_TOTAL,
    TRAINING_CANDIDATES_TOTAL,
)
from src.observability.sanitization import sanitize_attributes, sanitize_value
from src.observability.logging_config import configure_logging
from src.observability.tracing import (
    bind_request_id,
    get_request_id,
    reset_request_id,
    set_span_attributes,
)
from src.main import _route_template


def test_token_estimation():
    assert estimate_tokens("") == 0
    assert estimate_tokens("hello") > 0
    # Approx 4 characters per token check
    assert (
        estimate_tokens("hello world supportgpt") == len("hello world supportgpt") // 4
    )


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


def test_otel_metric_instruments_record_natively():
    # SDK 初始化前 Instrument 是 Proxy，初始化后才暴露公开 name。
    def instrument_name(instrument):
        return getattr(instrument, "name", getattr(instrument, "_name", None))

    assert instrument_name(LLM_TOKENS_TOTAL) == "llm_tokens"
    assert instrument_name(AGENT_REQUESTS_TOTAL) == "agent_requests"
    assert instrument_name(AGENT_NODE_DURATION_SECONDS) == "agent_node_duration_seconds"
    assert instrument_name(TOOL_CALLS_TOTAL) == "agent_tool_calls"
    assert instrument_name(HUMAN_APPROVALS_TOTAL) == "human_approvals"
    assert instrument_name(FEEDBACK_EVENTS_TOTAL) == "feedback_events"
    assert instrument_name(TRAINING_CANDIDATES_TOTAL) == "training_candidates"
    AGENT_REQUESTS_TOTAL.add(1, {"status": "success"})
    AGENT_NODE_DURATION_SECONDS.record(0.01, {"node": "retriever"})


def test_metric_route_uses_template_instead_of_raw_identifier():
    class Route:
        path = "/tickets/{ticket_id}"

    class Request:
        scope = {"route": Route()}

    assert _route_template(Request()) == "/tickets/{ticket_id}"


def test_observability_sanitizes_pii_secrets_and_business_fields():
    payload = sanitize_value(
        {
            "message": (
                "Email alice@example.com, card 4111 1111 1111 1111, "
                "api_key=sk-abcdefghijklmnopqrstuvwxyz"
            ),
            "authorization": "Bearer secret",
            "total_amount": 199.0,
            "tokens_input": 42,
        }
    )

    assert "alice@example.com" not in payload["message"]
    assert "4111 1111 1111 1111" not in payload["message"]
    assert "sk-abcdefghijklmnopqrstuvwxyz" not in payload["message"]
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


def test_application_logging_configuration_is_idempotent():
    application_logger = logging.getLogger("supportgpt")
    configure_logging("INFO")
    configure_logging("INFO")

    handlers = [
        handler
        for handler in application_logger.handlers
        if getattr(handler, "_supportgpt_console_handler", False)
    ]
    assert application_logger.level == logging.INFO
    assert len(handlers) == 1


def test_otel_attribute_values_are_compatible():
    attributes = sanitize_attributes(
        {
            "tool.payload_keys": ["customer_id", "order_id"],
            "context": {"email": "a@b.com"},
        }
    )
    assert attributes["tool.payload_keys"] == ["customer_id", "order_id"]
    assert "a@b.com" not in attributes["context"]


def test_grafana_dashboard_covers_phase_one_metrics():
    dashboard_path = (
        Path(__file__).resolve().parents[1] / "monitoring" / "grafana-dashboard.json"
    )
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
        "feedback_events_total",
        "training_candidates_total",
    ):
        assert metric in expressions


def test_metrics_flow_only_through_otel_collector():
    root = Path(__file__).resolve().parents[1]
    prometheus_config = (root / "monitoring" / "prometheus.yml").read_text(
        encoding="utf-8"
    )
    compose_config = (root / "deployment" / "docker-compose.yml").read_text(
        encoding="utf-8"
    )
    requirements = (root / "requirements" / "base.txt").read_text(encoding="utf-8")

    assert "backend:8000" not in prometheus_config
    assert "otel-collector:8889" in prometheus_config
    assert "OTEL_EXPORTER_OTLP_METRICS_ENDPOINT" in compose_config
    assert "prometheus-client" not in requirements


def test_trace_flow_has_no_langsmith_sdk_dual_path():
    root = Path(__file__).resolve().parents[1]
    source = "\n".join(
        path.read_text(encoding="utf-8") for path in (root / "src").rglob("*.py")
    )
    requirements = (root / "requirements" / "base.txt").read_text(encoding="utf-8")

    assert not (root / "src" / "observability" / "langsmith_tracing.py").exists()
    assert "from langsmith import traceable" not in source
    assert "LANGCHAIN_TRACING_V2" not in source
    assert not any(line.startswith("langsmith") for line in requirements.splitlines())
