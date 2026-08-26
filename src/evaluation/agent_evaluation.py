"""Dataset-driven Agent 行为评测器。"""

import asyncio
import json
import os
from dataclasses import dataclass, field
from statistics import mean
from typing import Any, Dict, List, Mapping, Sequence

from src.evaluation.response_metrics import response_metrics_evaluator
from src.models.intents import IntentType, normalize_intent


AGENT_METRIC_KEYS = (
    "task_completion",
    "policy_compliance",
    "routing_correctness",
    "tool_correctness",
    "workflow_correctness",
    "escalation_correctness",
)


@dataclass(frozen=True)
class AgentExpectations:
    """声明一条 Dataset 用例期望满足的 Agent 行为。"""

    expected_department: str | None = None
    expected_intent: IntentType | None = None
    expected_priority: str | None = None
    required_tools: List[str] = field(default_factory=list)
    forbidden_tools: List[str] = field(default_factory=list)
    expected_nodes: List[str] = field(default_factory=list)
    should_escalate: bool | None = None
    should_require_approval: bool | None = None
    max_workflow_errors: int = 0
    pass_threshold: float = 0.8

    @classmethod
    def from_mapping(cls, value: Mapping[str, Any] | None) -> "AgentExpectations":
        normalized = dict(value or {})
        if normalized.get("expected_intent") is not None:
            normalized["expected_intent"] = normalize_intent(
                normalized["expected_intent"]
            )
        expectations = cls(**normalized)
        if not 0.0 <= expectations.pass_threshold <= 1.0:
            raise ValueError("agent pass_threshold must be between 0 and 1.")
        if expectations.max_workflow_errors < 0:
            raise ValueError("max_workflow_errors cannot be negative.")
        return expectations


@dataclass
class AgentEvaluationResult:
    """保存 Agent 行为指标、硬性断言和最终通过结论。"""

    metrics: Dict[str, float]
    passed: bool
    failures: List[str]


async def score_agent_behavior(
    *,
    query: str,
    reference_answer: str,
    contexts: Sequence[str],
    workflow_output: Mapping[str, Any],
    expectations: AgentExpectations,
    engine: str,
) -> AgentEvaluationResult:
    """组合 DeepEval 语义评分与确定性 Workflow 行为断言。"""
    if engine not in {"deepeval", "local"}:
        raise ValueError("agent engine must be either 'deepeval' or 'local'.")

    deterministic, failures = _deterministic_scores(workflow_output, expectations)
    if engine == "deepeval":
        semantic = await _run_deepeval(
            query=query,
            reference_answer=reference_answer,
            contexts=contexts,
            workflow_output=workflow_output,
            expectations=expectations,
        )
    else:
        response = str(workflow_output.get("suggested_response", ""))
        task_completion = response_metrics_evaluator.calculate_relevance(
            query, response
        )
        semantic = {
            "task_completion": task_completion,
            "policy_compliance": deterministic["escalation_correctness"],
        }

    if engine == "deepeval":
        for metric in ("task_completion", "policy_compliance"):
            if semantic.get(metric, 0.0) < expectations.pass_threshold:
                failures.append(
                    f"DeepEval {metric} score {semantic.get(metric, 0.0):.4f} "
                    f"is below {expectations.pass_threshold:.4f}."
                )

    metrics = {**deterministic, **semantic}
    metrics["policy_compliance"] = mean(
        [
            semantic.get("policy_compliance", 0.0),
            deterministic.get("policy_compliance", 0.0),
        ]
    )
    metrics = {key: round(float(metrics.get(key, 0.0)), 4) for key in AGENT_METRIC_KEYS}
    overall = mean(metrics.values()) if metrics else 0.0
    passed = not failures and overall >= expectations.pass_threshold
    if overall < expectations.pass_threshold:
        failures.append(
            f"Agent overall score {overall:.4f} is below "
            f"{expectations.pass_threshold:.4f}."
        )
    return AgentEvaluationResult(metrics=metrics, passed=passed, failures=failures)


def _deterministic_scores(
    output: Mapping[str, Any], expectations: AgentExpectations
) -> tuple[Dict[str, float], List[str]]:
    """对路由、工具、节点顺序和升级策略执行可复现断言。"""
    failures: List[str] = []
    routing_checks = []
    for field_name, expected in (
        ("department", expectations.expected_department),
        ("intent", expectations.expected_intent),
        ("priority", expectations.expected_priority),
    ):
        if expected is None:
            continue
        matched = output.get(field_name) == expected
        routing_checks.append(1.0 if matched else 0.0)
        if not matched:
            failures.append(
                f"Expected {field_name}={expected}, got {output.get(field_name)}."
            )

    actual_tools = [
        str(call.get("tool_name", ""))
        for call in output.get("tool_calls", [])
        if isinstance(call, Mapping)
    ]
    missing_tools = sorted(set(expectations.required_tools) - set(actual_tools))
    forbidden_tools = sorted(set(expectations.forbidden_tools) & set(actual_tools))
    if missing_tools:
        failures.append(f"Missing required tools: {', '.join(missing_tools)}.")
    if forbidden_tools:
        failures.append(f"Forbidden tools called: {', '.join(forbidden_tools)}.")
    tool_checks = len(expectations.required_tools) + len(expectations.forbidden_tools)
    tool_failures = len(missing_tools) + len(forbidden_tools)
    tool_score = 1.0 if tool_checks == 0 else max(0.0, 1 - tool_failures / tool_checks)

    actual_nodes = list(output.get("workflow_path", []))
    workflow_score = 1.0
    if expectations.expected_nodes:
        workflow_score = 1.0 if actual_nodes == expectations.expected_nodes else 0.0
        if workflow_score == 0.0:
            failures.append(
                f"Expected workflow path {expectations.expected_nodes}, "
                f"got {actual_nodes}."
            )

    escalation_checks = []
    for field_name, expected in (
        ("escalation_recommended", expectations.should_escalate),
        ("approval_required", expectations.should_require_approval),
    ):
        if expected is None:
            continue
        matched = bool(output.get(field_name, False)) is expected
        escalation_checks.append(1.0 if matched else 0.0)
        if not matched:
            failures.append(
                f"Expected {field_name}={expected}, got {output.get(field_name)}."
            )

    error_count = len(output.get("errors", []))
    if error_count > expectations.max_workflow_errors:
        failures.append(
            f"Workflow errors {error_count} exceed {expectations.max_workflow_errors}."
        )

    routing_score = mean(routing_checks) if routing_checks else 1.0
    escalation_score = mean(escalation_checks) if escalation_checks else 1.0
    policy_score = mean(
        [escalation_score, tool_score, 1.0 if not forbidden_tools else 0.0]
    )
    return {
        "policy_compliance": policy_score,
        "routing_correctness": routing_score,
        "tool_correctness": tool_score,
        "workflow_correctness": workflow_score,
        "escalation_correctness": escalation_score,
    }, failures


async def _run_deepeval(
    *,
    query: str,
    reference_answer: str,
    contexts: Sequence[str],
    workflow_output: Mapping[str, Any],
    expectations: AgentExpectations,
) -> Dict[str, float]:
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key or api_key.startswith("your-"):
        raise RuntimeError(
            "DeepEval engine requires a valid OPENAI_API_KEY. "
            "Use --agent-engine local only for deterministic smoke tests."
        )
    return await asyncio.to_thread(
        _measure_deepeval,
        query,
        reference_answer,
        list(contexts),
        workflow_output,
        expectations,
    )


def _measure_deepeval(
    query: str,
    reference_answer: str,
    contexts: List[str],
    workflow_output: Mapping[str, Any],
    expectations: AgentExpectations,
) -> Dict[str, float]:
    """通过 DeepEval GEval 评估任务完成度和策略合规性。"""
    try:
        from deepeval.metrics import GEval
        from deepeval.test_case import LLMTestCase, LLMTestCaseParams
    except ImportError as exc:
        raise RuntimeError(
            "DeepEval dependencies are unavailable. Install requirements/eval.txt."
        ) from exc

    actual_output = json.dumps(
        {
            "response": workflow_output.get("suggested_response", ""),
            "routing": {
                "department": workflow_output.get("department"),
                "intent": workflow_output.get("intent"),
                "priority": workflow_output.get("priority"),
            },
            "tool_calls": [
                call.get("tool_name")
                for call in workflow_output.get("tool_calls", [])
                if isinstance(call, Mapping)
            ],
            "workflow_path": workflow_output.get("workflow_path", []),
            "escalation_recommended": workflow_output.get(
                "escalation_recommended", False
            ),
            "approval_required": workflow_output.get("approval_required", False),
            "errors": workflow_output.get("errors", []),
        },
        ensure_ascii=False,
    )
    expected_behavior = json.dumps(
        {
            "reference_answer": reference_answer,
            "agent_expectations": expectations.__dict__,
        },
        ensure_ascii=False,
    )
    test_case = LLMTestCase(
        input=query,
        actual_output=actual_output,
        expected_output=expected_behavior,
        retrieval_context=contexts,
    )
    task_completion = GEval(
        name="Agent Task Completion",
        criteria=(
            "Determine whether the Agent resolved the user's task accurately "
            "and completely "
            "using the reference answer and retrieval context."
        ),
        evaluation_params=[
            LLMTestCaseParams.INPUT,
            LLMTestCaseParams.ACTUAL_OUTPUT,
            LLMTestCaseParams.EXPECTED_OUTPUT,
            LLMTestCaseParams.RETRIEVAL_CONTEXT,
        ],
        threshold=0.8,
    )
    policy_compliance = GEval(
        name="Agent Policy Compliance",
        criteria=(
            "Determine whether the Agent response follows the declared routing, tool, "
            "escalation and approval expectations without making unauthorized "
            "commitments."
        ),
        evaluation_params=[
            LLMTestCaseParams.INPUT,
            LLMTestCaseParams.ACTUAL_OUTPUT,
            LLMTestCaseParams.EXPECTED_OUTPUT,
        ],
        threshold=0.8,
    )
    task_completion.measure(test_case)
    policy_compliance.measure(test_case)
    return {
        "task_completion": _score(task_completion.score),
        "policy_compliance": _score(policy_compliance.score),
    }


def _score(value: Any) -> float:
    try:
        score = float(value)
    except (TypeError, ValueError):
        return 0.0
    return max(0.0, min(1.0, score))
