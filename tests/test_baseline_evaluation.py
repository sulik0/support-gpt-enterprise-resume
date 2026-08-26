import json
from pathlib import Path

import pytest

from src.evaluation.baseline_evaluation import (
    BaselineExpectations,
    aggregate_behavior,
    evaluate_baseline_behavior,
    run_baseline_evaluation_v1,
)
from src.models.intents import IntentType
from src.observability.tracing import get_tracer, observed_span, trace_operation


PROJECT_ROOT = Path(__file__).resolve().parents[1]
BASELINE_PATH = (
    PROJECT_ROOT / "evaluation" / "baseline" / "supportgpt_baseline_100.json"
)


def test_v1_behavior_pass_ignores_future_dataset_fields():
    """Priority、节点、安全和语义字段暂时不得影响第一版 Case Pass。"""
    expectations = BaselineExpectations.from_mapping(
        {
            "expected_department": "billing",
            "expected_intent": "billing_dispute",
            "required_tools": ["crm.get_customer_profile"],
            "forbidden_tools": ["orders.check_refund_eligibility"],
            "should_escalate": True,
            "should_require_approval": True,
            "expected_priority": {"invalid": "ignored"},
            "expected_nodes": "not-read-by-v1",
            "security_label": object(),
        }
    )
    output = {
        "department": "billing",
        "intent": IntentType.BILLING_DISPUTE,
        "priority": "low",
        "workflow_path": ["different-node"],
        "tool_calls": [{"tool_name": "crm.get_customer_profile"}],
        "escalation_recommended": True,
        "approval_required": True,
        "errors": ["ignored in V1 pass"],
    }

    result = evaluate_baseline_behavior(output, expectations)

    assert result.passed is True
    assert result.failures == ()
    assert set(result.checks) == {
        "intent_accuracy",
        "department_accuracy",
        "required_tool_hit_rate",
        "forbidden_tool_violation_rate",
        "hitl_accuracy",
        "approval_accuracy",
    }


def test_v1_behavior_aggregates_using_real_check_denominators():
    expectations = BaselineExpectations(
        expected_department="billing",
        expected_intent=IntentType.BILLING_DISPUTE,
        required_tools=["crm", "orders"],
        forbidden_tools=["refund_execute"],
        should_escalate=True,
        should_require_approval=True,
    )
    passed = evaluate_baseline_behavior(
        {
            "department": "billing",
            "intent": "billing_dispute",
            "tool_calls": [{"tool_name": "crm"}, {"tool_name": "orders"}],
            "escalation_recommended": True,
            "approval_required": True,
        },
        expectations,
    )
    failed = evaluate_baseline_behavior(
        {
            "department": "general",
            "intent": "information_request",
            "tool_calls": [
                {"tool_name": "crm"},
                {"tool_name": "refund_execute"},
            ],
            "escalation_recommended": False,
            "approval_required": False,
        },
        expectations,
    )

    summary = aggregate_behavior([passed, failed])

    assert summary["intent_accuracy"] == 0.5
    assert summary["department_accuracy"] == 0.5
    assert summary["required_tool_hit_rate"] == 0.75
    assert summary["forbidden_tool_violation_rate"] == 0.5
    assert summary["hitl_accuracy"] == 0.5
    assert summary["approval_accuracy"] == 0.5
    assert summary["case_pass_rate"] == 0.5


@pytest.mark.asyncio
async def test_v1_replays_full_ticket_state_and_records_trace_performance(tmp_path):
    tracer = get_tracer("tests.baseline_v1")

    @trace_operation(name="supportgpt.llm.generate_resolution", component="llm")
    async def fake_resolution():
        return "Refund guidance", 10, 5

    async def fake_workflow(state):
        with observed_span(tracer, "agent.analyzer"):
            pass
        with observed_span(tracer, "agent.tooling"):
            pass
        with observed_span(tracer, "agent.retriever"):
            pass
        with observed_span(tracer, "agent.resolver"):
            response, _, _ = await fake_resolution()
        with observed_span(tracer, "agent.qa"):
            pass
        return {
            **state,
            "trace_id": "c" * 32,
            "suggested_response": response,
            "context_citations": [],
            "department": "billing",
            "intent": IntentType.BILLING_DISPUTE,
            "priority": "high",
            "tool_calls": [
                {"tool_name": "crm.get_customer_profile"},
                {"tool_name": "tickets.get_past_tickets"},
                {"tool_name": "orders.get_order_history"},
            ],
            "workflow_path": [
                "ticket_analyzer",
                "tool_call",
                "retriever",
                "llm_generation",
                "qa",
                "escalation",
            ],
            "escalation_recommended": True,
            "approval_required": True,
            "analyzer_strategy": "rule",
            "tokens_input": 10,
            "tokens_output": 5,
            "latency_seconds": 0.25,
            "errors": [],
        }

    paths = await run_baseline_evaluation_v1(
        BASELINE_PATH,
        tmp_path,
        limit=1,
        execution_metadata={"llm_model": "test-model"},
        workflow_runner=fake_workflow,
    )

    report = json.loads(paths["json"].read_text(encoding="utf-8"))
    row = report["cases"][0]
    assert report["evaluation_type"] == "baseline_workflow_replay_v1"
    assert report["case_count"] == 1
    assert "rag_evaluation" not in report
    assert "security_evaluation" not in report
    assert row["behavior_evaluation"]["passed"] is True
    assert row["dataset_case"]["reference_answer"]
    assert row["dataset_case"]["agent_expectations"]["expected_priority"] == "high"
    assert row["ticket_state"]["request_id"].startswith("offline-eval-")
    assert row["ticket_state"]["intent"] == "information_request"
    assert row["trace_id"] == "c" * 32
    assert row["performance"]["tokens"]["total"] == 15
    assert row["performance"]["llm_call_count"] == 1
    assert row["performance"]["analyzer_strategy"] == "rule"
    assert all(
        row["performance"]["node_latency_seconds"][node] is not None
        for node in ("analyzer", "tool", "rag", "resolver", "qa")
    )
    assert report["performance_summary"]["analyzer"]["rule_hit_rate"] == 1.0
    assert "reference_answer" in report["ignored_dataset_fields"]
    markdown = paths["markdown"].read_text(encoding="utf-8")
    assert "Baseline Workflow Replay V1" in markdown
    assert "Analyzer Rule Hit Rate" in markdown
