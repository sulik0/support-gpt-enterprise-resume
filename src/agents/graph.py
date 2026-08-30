import asyncio
import logging
import time
from typing import Any, Awaitable, Callable, Dict, List, Optional, TypedDict

from langgraph.graph import END, StateGraph

from src.agents.analyzer import ticket_analyzer_agent
from src.agents.escalation import escalation_agent
from src.agents.quality_assurance import quality_assurance_agent
from src.agents.resolver import resolution_agent
from src.agents.retriever import knowledge_retriever_agent
from src.agents.tooling import tooling_agent
from src.config import settings
from src.models.intents import DEFAULT_INTENT, IntentType
from src.observability.cost_tracking import calculate_llm_cost
from src.observability.metrics import (
    AGENT_NODE_DURATION_SECONDS,
    AGENT_NODE_EXECUTIONS_TOTAL,
    AGENT_REQUESTS_TOTAL,
    LLM_COST_TOTAL,
)
from src.observability.tracing import (
    get_current_trace_id,
    get_request_id,
    get_tracer,
    langsmith_agent_trace_context,
    langsmith_span_attributes,
    observed_span,
    set_agent_trace_id,
    set_span_attributes,
)
from src.risk.engine import risk_engine

logger = logging.getLogger("supportgpt.agents.graph")
tracer = get_tracer(__name__)


class AgentState(TypedDict):
    """定义 LangGraph 各节点共享的客服任务状态。

    字段覆盖请求标识、分析结果、检索上下文、回复质量和升级决策。
    """

    request_id: str
    ticket_id: int
    customer_id: str
    subject: str
    description: str
    kb_version: str
    sentiment: str
    priority: str
    intent: IntentType
    department: str
    analyzer_confidence: float
    analyzer_strategy: str
    security_threat_detected: bool
    security_risk_score: float
    security_source: Optional[str]
    security_findings: List[str]
    semantic_guard_label: str
    semantic_guard_categories: List[str]
    semantic_guard_checks: List[Dict[str, Any]]
    semantic_guard_degraded: bool
    semantic_guard_model: Optional[str]
    risk_level: str
    risk_score: float
    risk_reasons: List[str]
    risk_requires_human: bool
    risk_block_automation: bool
    operator_role: str
    tool_context: Dict[str, Any]
    tool_calls: List[Dict[str, Any]]
    context_citations: List[Any]
    suggested_response: str
    qa_score: float
    hallucination_detected: bool
    citation_verified: bool
    response_grounded: bool
    response_requires_human: bool
    qa_strategy: str
    escalation_recommended: bool
    escalation_reason: Optional[str]
    sla_hours: float
    tokens_input: int
    tokens_output: int
    cost_usd: float
    latency_seconds: float
    approval_required: bool
    workflow_path: List[str]
    errors: List[str]


# --- Node Wrappers ---
async def _run_node(
    node: str,
    handler: Callable[[Dict[str, Any]], Awaitable[Dict[str, Any]]],
    state: AgentState,
) -> Dict[str, Any]:
    started = time.perf_counter()
    status = "success"
    try:
        result = await handler(state)
        result = {
            **result,
            "workflow_path": [*state.get("workflow_path", []), node],
        }
        if len(result.get("errors", [])) > len(state.get("errors", [])):
            status = "error"
        return result
    except BaseException:
        status = "error"
        raise
    finally:
        try:
            AGENT_NODE_EXECUTIONS_TOTAL.add(1, {"node": node, "status": status})
            AGENT_NODE_DURATION_SECONDS.record(
                time.perf_counter() - started, {"node": node}
            )
        except Exception:
            logger.debug("Unable to record metrics for Agent node %s", node)


async def analyze_node(state: AgentState) -> Dict[str, Any]:
    with observed_span(
        tracer, "agent.analyzer", _trace_attrs(state, node="analyzer")
    ) as span:
        result = await _run_node(
            "ticket_analyzer", ticket_analyzer_agent.analyze, state
        )
        set_span_attributes(
            span, {"analyzer.strategy": result.get("analyzer_strategy", "unknown")}
        )
        logger.info(
            "analyzer completed",
            extra={
                "ticket_id": result.get("ticket_id"),
                "intent": result.get("intent"),
                "priority": result.get("priority"),
                "strategy": result.get("analyzer_strategy"),
                "risk_level": result.get("risk_level"),
                "risk_score": result.get("risk_score"),
            },
        )
        return result


async def retrieve_node(state: AgentState) -> Dict[str, Any]:
    with observed_span(
        tracer, "agent.retriever", _trace_attrs(state, node="retriever")
    ):
        result = await _run_node("retriever", knowledge_retriever_agent.retrieve, state)
        logger.info(
            "retriever completed",
            extra={
                "ticket_id": result.get("ticket_id"),
                "citations": len(result.get("context_citations", [])),
                "risk_level": result.get("risk_level"),
                "risk_score": result.get("risk_score"),
            },
        )
        return result


async def tooling_node(state: AgentState) -> Dict[str, Any]:
    with observed_span(tracer, "agent.tooling", _trace_attrs(state, node="tooling")):
        result = await _run_node("tool_call", tooling_agent.enrich, state)
        tool_calls = result.get("tool_calls", [])
        logger.info(
            "tool completed",
            extra={
                "ticket_id": result.get("ticket_id"),
                "tool": ",".join(
                    call.get("tool_name", "unknown") for call in tool_calls
                ),
                "tool_count": len(tool_calls),
                "risk_level": result.get("risk_level"),
                "risk_score": result.get("risk_score"),
            },
        )
        return result


def _unique_values(*groups: List[Any]) -> List[Any]:
    """合并并行分支的列表结果并保留顺序。"""
    output = []
    seen = set()
    for group in groups:
        for value in group:
            marker = repr(value)
            if marker not in seen:
                seen.add(marker)
                output.append(value)
    return output


def _merge_context_results(
    state: AgentState,
    tool_result: Dict[str, Any],
    retrieval_result: Dict[str, Any],
) -> Dict[str, Any]:
    """安全合并 Tool 与 RAG 并行结果，风险信号只升不降。"""
    label_rank = {"not_run": 0, "safe": 1, "controversial": 2, "unsafe": 3}
    labels = [
        str(tool_result.get("semantic_guard_label", "not_run")),
        str(retrieval_result.get("semantic_guard_label", "not_run")),
    ]
    semantic_label = max(labels, key=lambda item: label_rank.get(item.lower(), 0))
    merged = {
        **state,
        "tool_context": tool_result.get("tool_context", {}),
        "tool_calls": tool_result.get("tool_calls", []),
        "context_citations": retrieval_result.get("context_citations", []),
        "errors": _unique_values(
            state.get("errors", []),
            tool_result.get("errors", []),
            retrieval_result.get("errors", []),
        ),
        "security_threat_detected": bool(
            tool_result.get("security_threat_detected")
            or retrieval_result.get("security_threat_detected")
        ),
        "security_risk_score": max(
            float(tool_result.get("security_risk_score", 0.0) or 0.0),
            float(retrieval_result.get("security_risk_score", 0.0) or 0.0),
        ),
        "security_source": tool_result.get("security_source")
        or retrieval_result.get("security_source"),
        "security_findings": _unique_values(
            tool_result.get("security_findings", []),
            retrieval_result.get("security_findings", []),
        ),
        "semantic_guard_label": semantic_label,
        "semantic_guard_categories": _unique_values(
            tool_result.get("semantic_guard_categories", []),
            retrieval_result.get("semantic_guard_categories", []),
        ),
        "semantic_guard_checks": _unique_values(
            tool_result.get("semantic_guard_checks", []),
            retrieval_result.get("semantic_guard_checks", []),
        ),
        "semantic_guard_degraded": bool(
            tool_result.get("semantic_guard_degraded")
            or retrieval_result.get("semantic_guard_degraded")
        ),
        "semantic_guard_model": tool_result.get("semantic_guard_model")
        or retrieval_result.get("semantic_guard_model"),
        "risk_score": max(
            float(tool_result.get("risk_score", 0.0) or 0.0),
            float(retrieval_result.get("risk_score", 0.0) or 0.0),
        ),
        "risk_reasons": _unique_values(
            tool_result.get("risk_reasons", []),
            retrieval_result.get("risk_reasons", []),
        ),
        "risk_requires_human": bool(
            tool_result.get("risk_requires_human")
            or retrieval_result.get("risk_requires_human")
        ),
        "risk_block_automation": bool(
            tool_result.get("risk_block_automation")
            or retrieval_result.get("risk_block_automation")
        ),
        "tokens_input": (
            state.get("tokens_input", 0)
            + max(
                tool_result.get("tokens_input", 0) - state.get("tokens_input", 0),
                0,
            )
            + max(
                retrieval_result.get("tokens_input", 0)
                - state.get("tokens_input", 0),
                0,
            )
        ),
        "tokens_output": (
            state.get("tokens_output", 0)
            + max(
                tool_result.get("tokens_output", 0) - state.get("tokens_output", 0),
                0,
            )
            + max(
                retrieval_result.get("tokens_output", 0)
                - state.get("tokens_output", 0),
                0,
            )
        ),
        "workflow_path": [
            *state.get("workflow_path", []),
            "tool_call",
            "retriever",
        ],
    }
    assessment = risk_engine.assess(merged, stage="input")
    merged = {**merged, **assessment.state_updates()}
    if merged.get("risk_block_automation"):
        merged["tool_context"] = {}
        merged["context_citations"] = []
    return merged


async def context_enrichment_node(state: AgentState) -> Dict[str, Any]:
    """并行执行 Tool Calling 和 RAG Retrieval。"""
    with observed_span(
        tracer,
        "agent.context_enrichment",
        _trace_attrs(state, node="context_enrichment"),
    ):
        tool_result, retrieval_result = await asyncio.gather(
            tooling_node(state), retrieve_node(state)
        )
        return _merge_context_results(state, tool_result, retrieval_result)


async def resolve_node(state: AgentState) -> Dict[str, Any]:
    with observed_span(tracer, "agent.resolver", _trace_attrs(state, node="resolver")):
        result = await _run_node("llm_generation", resolution_agent.resolve, state)
        logger.info(
            "generation completed",
            extra={
                "ticket_id": result.get("ticket_id"),
                "generated": bool(result.get("suggested_response")),
            },
        )
        return result


async def qa_node(state: AgentState) -> Dict[str, Any]:
    with observed_span(tracer, "agent.qa", _trace_attrs(state, node="qa")) as span:
        result = await _run_node("qa", quality_assurance_agent.verify, state)
        set_span_attributes(span, {"qa.strategy": result.get("qa_strategy", "unknown")})
        logger.info(
            "qa completed",
            extra={
                "ticket_id": result.get("ticket_id"),
                "score": result.get("qa_score"),
                "hallucination_detected": result.get("hallucination_detected", False),
                "strategy": result.get("qa_strategy"),
                "risk_level": result.get("risk_level"),
                "risk_score": result.get("risk_score"),
            },
        )
        return result


async def escalate_node(state: AgentState) -> Dict[str, Any]:
    with observed_span(
        tracer, "agent.escalation", _trace_attrs(state, node="escalation")
    ):
        result = await _run_node("escalation", escalation_agent.evaluate, state)
        logger.info(
            "escalation decided",
            extra={
                "ticket_id": result.get("ticket_id"),
                "required": result.get("escalation_recommended", False),
                "risk_level": result.get("risk_level"),
                "risk_score": result.get("risk_score"),
            },
        )
        return result


def _trace_attrs(state: Dict[str, Any], node: str) -> Dict[str, Any]:
    return {
        **langsmith_span_attributes("chain"),
        "agent.node": node,
        "request.id": state.get("request_id"),
        "ticket.id": state.get("ticket_id"),
        "kb.version": state.get("kb_version"),
        "ticket.department": state.get("department"),
        "ticket.priority": state.get("priority"),
        "operator.role": state.get("operator_role"),
        "risk.level": state.get("risk_level"),
        "risk.score": state.get("risk_score"),
        "risk.requires_human": state.get("risk_requires_human"),
        "security.threat_detected": state.get("security_threat_detected"),
        "guardrail.semantic_label": state.get("semantic_guard_label", "not_run"),
        "guardrail.semantic_degraded": state.get("semantic_guard_degraded", False),
        "guardrail.semantic_check_count": len(state.get("semantic_guard_checks", [])),
    }


def _configured_llm_model_name() -> str:
    """返回当前 Workflow 实际使用的模型或 Azure deployment 名。"""
    provider = settings.LLM_PROVIDER.lower()
    if provider == "openai":
        return settings.LLM_MODEL_NAME or provider
    if provider == "azure":
        return settings.AZURE_OPENAI_DEPLOYMENT or provider
    return provider


def _is_automation_blocked(state: AgentState) -> bool:
    """对安全威胁使用统一的自动化阻断条件。"""
    return (
        bool(state.get("risk_block_automation"))
        or bool(state.get("security_threat_detected"))
        or "Security threat" in "".join(state.get("errors", []))
    )


def route_after_analyzer(state: AgentState) -> str:
    """输入安全检查失败时直接进入人工升级。"""
    if _is_automation_blocked(state):
        return "escalation"
    return "context_enrichment"


def route_after_context_enrichment(state: AgentState) -> str:
    """Tool 或 RAG 任一分支高风险时跳过生成。"""
    if _is_automation_blocked(state):
        return "escalation"
    return "resolver"


def create_agent_graph() -> StateGraph:
    """Build and compile the LangGraph workflow."""
    workflow = StateGraph(AgentState)

    # Register Nodes
    workflow.add_node("analyzer", analyze_node)
    workflow.add_node("context_enrichment", context_enrichment_node)
    workflow.add_node("resolver", resolve_node)
    workflow.add_node("qa", qa_node)
    workflow.add_node("escalation", escalate_node)

    # Establish Transitions
    workflow.set_entry_point("analyzer")
    workflow.add_conditional_edges(
        "analyzer",
        route_after_analyzer,
        {
            "context_enrichment": "context_enrichment",
            "escalation": "escalation",
        },
    )
    workflow.add_conditional_edges(
        "context_enrichment",
        route_after_context_enrichment,
        {
            "resolver": "resolver",
            "escalation": "escalation",
        },
    )
    workflow.add_edge("resolver", "qa")
    workflow.add_edge("qa", "escalation")
    workflow.add_edge("escalation", END)

    return workflow.compile()


compiled_graph = create_agent_graph()


def build_ticket_state(initial_state: Dict[str, Any]) -> AgentState:
    """根据业务输入构造可直接交给 LangGraph 的完整 Ticket State。"""
    return {
        "request_id": initial_state.get("request_id")
        or get_request_id()
        or "background",
        "ticket_id": initial_state.get("ticket_id", 0),
        "customer_id": initial_state.get("customer_id", ""),
        "subject": initial_state.get("subject", ""),
        "description": initial_state.get("description", ""),
        "kb_version": initial_state.get("kb_version", "v1"),
        "sentiment": "neutral",
        "priority": "medium",
        "intent": DEFAULT_INTENT,
        "department": "general",
        "analyzer_confidence": 1.0,
        "analyzer_strategy": "not_run",
        "security_threat_detected": False,
        "security_risk_score": 0.0,
        "security_source": None,
        "security_findings": [],
        "semantic_guard_label": "not_run",
        "semantic_guard_categories": [],
        "semantic_guard_checks": [],
        "semantic_guard_degraded": False,
        "semantic_guard_model": None,
        "risk_level": "low",
        "risk_score": 0.0,
        "risk_reasons": [],
        "risk_requires_human": False,
        "risk_block_automation": False,
        "operator_role": initial_state.get("operator_role", "agent"),
        "tool_context": {},
        "tool_calls": [],
        "context_citations": [],
        "suggested_response": "",
        "qa_score": 1.0,
        "hallucination_detected": False,
        "citation_verified": False,
        "response_grounded": False,
        "response_requires_human": False,
        "qa_strategy": "not_run",
        "escalation_recommended": False,
        "escalation_reason": None,
        "sla_hours": 24.0,
        "tokens_input": 0,
        "tokens_output": 0,
        "cost_usd": 0.0,
        "latency_seconds": 0.0,
        "approval_required": False,
        "workflow_path": [],
        "errors": [],
    }


async def run_agent_workflow(initial_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executes the Agent workflow with parallel context enrichment using LangGraph.
    Estimates latency, total tokens, and USD costs.
    """
    start_time = time.time()
    state_input = build_ticket_state(initial_state)

    logger.info(f"Invoking LangGraph flow for ticket ID {state_input['ticket_id']}")
    try:
        with langsmith_agent_trace_context():
            with observed_span(
                tracer,
                "supportgpt.langgraph.workflow",
                {
                    **_trace_attrs(state_input, node="workflow"),
                    **langsmith_span_attributes(
                        "chain",
                        trace_name="SupportGPT Agent Workflow",
                        force=True,
                    ),
                },
                root=True,
            ):
                final_output = await compiled_graph.ainvoke(state_input)
                final_output["trace_id"] = get_current_trace_id()
                set_agent_trace_id(final_output["trace_id"])
        try:
            AGENT_REQUESTS_TOTAL.add(1, {"status": "success"})
        except Exception:
            logger.debug("Unable to record successful Agent request metric")
    except BaseException:
        try:
            AGENT_REQUESTS_TOTAL.add(1, {"status": "error"})
        except Exception:
            logger.debug("Unable to record failed Agent request metric")
        raise

    # Compute execution costs
    tokens_in = final_output.get("tokens_input", 0)
    tokens_out = final_output.get("tokens_output", 0)
    model_name = _configured_llm_model_name()
    cost = calculate_llm_cost(model_name, tokens_in, tokens_out)

    final_output["cost_usd"] = cost
    final_output["latency_seconds"] = round(time.time() - start_time, 4)
    span_attrs = {
        "llm.provider": settings.LLM_PROVIDER,
        "llm.model": model_name,
        "llm.tokens_input": tokens_in,
        "llm.tokens_output": tokens_out,
        "llm.cost_usd": cost,
        "agent.latency_seconds": final_output["latency_seconds"],
        "agent.approval_required": final_output.get("approval_required", False),
        "agent.escalation_recommended": final_output.get(
            "escalation_recommended", False
        ),
        "risk.level": final_output.get("risk_level", "low"),
        "risk.score": final_output.get("risk_score", 0.0),
        "risk.requires_human": final_output.get("risk_requires_human", False),
        "risk.block_automation": final_output.get("risk_block_automation", False),
        "security.threat_detected": final_output.get("security_threat_detected", False),
        "security.source": final_output.get("security_source"),
    }

    # Determine if human approval is required
    # Escalation needed or low QA score triggers approval
    if (
        final_output.get("escalation_recommended")
        or final_output.get("qa_score", 1.0) < settings.RISK_QA_SCORE_THRESHOLD
        or final_output.get("risk_requires_human", False)
    ):
        final_output["approval_required"] = True
        span_attrs["agent.approval_required"] = True

    with observed_span(tracer, "agent.workflow.summary", span_attrs):
        pass

    # Record OpenTelemetry usage metrics.
    try:
        LLM_COST_TOTAL.add(cost, {"model": model_name})
    except Exception:
        logger.debug("Unable to record LLM usage metrics")

    logger.info(
        f"LangGraph completed in {final_output['latency_seconds']}s. Cost: ${final_output['cost_usd']}."
    )
    return final_output
