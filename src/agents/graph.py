import time
import logging
from typing import Awaitable, Callable, TypedDict, List, Dict, Any, Optional
from langgraph.graph import StateGraph, END

from src.config import settings
from src.agents.analyzer import ticket_analyzer_agent
from src.agents.retriever import knowledge_retriever_agent
from src.agents.tooling import tooling_agent
from src.agents.resolver import resolution_agent
from src.agents.quality_assurance import quality_assurance_agent
from src.agents.escalation import escalation_agent
from src.observability.cost_tracking import calculate_llm_cost
from src.observability.metrics import (
    AGENT_NODE_DURATION_SECONDS,
    AGENT_NODE_EXECUTIONS_TOTAL,
    AGENT_REQUESTS_TOTAL,
    LLM_COST_TOTAL,
    LLM_TOKENS_TOTAL,
)
from src.observability.tracing import get_request_id, get_tracer, observed_span

logger = logging.getLogger("supportgpt.agents.graph")
tracer = get_tracer(__name__)


class AgentState(TypedDict):
    request_id: str
    ticket_id: int
    customer_id: str
    subject: str
    description: str
    kb_version: str
    sentiment: str
    priority: str
    intent: str
    department: str
    operator_role: str
    tool_context: Dict[str, Any]
    tool_calls: List[Dict[str, Any]]
    context_citations: List[Any]
    suggested_response: str
    qa_score: float
    hallucination_detected: bool
    escalation_recommended: bool
    escalation_reason: Optional[str]
    tokens_input: int
    tokens_output: int
    cost_usd: float
    latency_seconds: float
    approval_required: bool
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
    with observed_span(tracer, "agent.analyzer", _trace_attrs(state, node="analyzer")):
        return await _run_node("ticket_analyzer", ticket_analyzer_agent.analyze, state)


async def retrieve_node(state: AgentState) -> Dict[str, Any]:
    with observed_span(
        tracer, "agent.retriever", _trace_attrs(state, node="retriever")
    ):
        return await _run_node("retriever", knowledge_retriever_agent.retrieve, state)


async def tooling_node(state: AgentState) -> Dict[str, Any]:
    with observed_span(tracer, "agent.tooling", _trace_attrs(state, node="tooling")):
        return await _run_node("tool_call", tooling_agent.enrich, state)


async def resolve_node(state: AgentState) -> Dict[str, Any]:
    with observed_span(tracer, "agent.resolver", _trace_attrs(state, node="resolver")):
        return await _run_node("llm_generation", resolution_agent.resolve, state)


async def qa_node(state: AgentState) -> Dict[str, Any]:
    with observed_span(tracer, "agent.qa", _trace_attrs(state, node="qa")):
        return await _run_node("qa", quality_assurance_agent.verify, state)


async def escalate_node(state: AgentState) -> Dict[str, Any]:
    with observed_span(
        tracer, "agent.escalation", _trace_attrs(state, node="escalation")
    ):
        return await _run_node("escalation", escalation_agent.evaluate, state)


def _trace_attrs(state: Dict[str, Any], node: str) -> Dict[str, Any]:
    return {
        "agent.node": node,
        "request.id": state.get("request_id"),
        "ticket.id": state.get("ticket_id"),
        "kb.version": state.get("kb_version"),
        "ticket.department": state.get("department"),
        "ticket.priority": state.get("priority"),
        "operator.role": state.get("operator_role"),
    }


def route_after_analyzer(state: AgentState) -> str:
    """Route security-blocked tickets directly to escalation."""
    if "Security threat" in "".join(state.get("errors", [])):
        return "escalation"
    return "tooling"


def create_agent_graph() -> StateGraph:
    """Build and compile the LangGraph workflow."""
    workflow = StateGraph(AgentState)

    # Register Nodes
    workflow.add_node("analyzer", analyze_node)
    workflow.add_node("tooling", tooling_node)
    workflow.add_node("retriever", retrieve_node)
    workflow.add_node("resolver", resolve_node)
    workflow.add_node("qa", qa_node)
    workflow.add_node("escalation", escalate_node)

    # Establish Transitions
    workflow.set_entry_point("analyzer")
    workflow.add_conditional_edges(
        "analyzer",
        route_after_analyzer,
        {
            "tooling": "tooling",
            "escalation": "escalation",
        },
    )
    workflow.add_edge("tooling", "retriever")
    workflow.add_edge("retriever", "resolver")
    workflow.add_edge("resolver", "qa")
    workflow.add_edge("qa", "escalation")
    workflow.add_edge("escalation", END)

    return workflow.compile()


compiled_graph = create_agent_graph()


async def run_agent_workflow(initial_state: Dict[str, Any]) -> Dict[str, Any]:
    """
    Executes the multi-agent workflow sequentially using LangGraph.
    Estimates latency, total tokens, and USD costs.
    """
    start_time = time.time()

    # Initialize state fields if missing
    state_input: AgentState = {
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
        "intent": "general",
        "department": "general",
        "operator_role": initial_state.get("operator_role", "agent"),
        "tool_context": {},
        "tool_calls": [],
        "context_citations": [],
        "suggested_response": "",
        "qa_score": 1.0,
        "hallucination_detected": False,
        "escalation_recommended": False,
        "escalation_reason": None,
        "tokens_input": 0,
        "tokens_output": 0,
        "cost_usd": 0.0,
        "latency_seconds": 0.0,
        "approval_required": False,
        "errors": [],
    }

    logger.info(f"Invoking LangGraph flow for ticket ID {state_input['ticket_id']}")
    try:
        with observed_span(
            tracer,
            "supportgpt.langgraph.workflow",
            _trace_attrs(state_input, node="workflow"),
        ):
            final_output = await compiled_graph.ainvoke(state_input)
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
    cost = calculate_llm_cost(settings.LLM_PROVIDER, tokens_in, tokens_out)

    final_output["cost_usd"] = cost
    final_output["latency_seconds"] = round(time.time() - start_time, 4)
    span_attrs = {
        "llm.provider": settings.LLM_PROVIDER,
        "llm.tokens_input": tokens_in,
        "llm.tokens_output": tokens_out,
        "llm.cost_usd": cost,
        "agent.latency_seconds": final_output["latency_seconds"],
        "agent.approval_required": final_output.get("approval_required", False),
        "agent.escalation_recommended": final_output.get(
            "escalation_recommended", False
        ),
    }

    # Determine if human approval is required
    # Escalation needed or low QA score triggers approval
    if (
        final_output.get("escalation_recommended")
        or final_output.get("qa_score", 1.0) < 0.8
    ):
        final_output["approval_required"] = True
        span_attrs["agent.approval_required"] = True

    with observed_span(tracer, "agent.workflow.summary", span_attrs):
        pass

    # Record OpenTelemetry usage metrics.
    try:
        LLM_TOKENS_TOTAL.add(
            tokens_in, {"model": settings.LLM_PROVIDER, "type": "input"}
        )
        LLM_TOKENS_TOTAL.add(
            tokens_out, {"model": settings.LLM_PROVIDER, "type": "output"}
        )
        LLM_COST_TOTAL.add(cost, {"model": settings.LLM_PROVIDER})
    except Exception:
        logger.debug("Unable to record LLM usage metrics")

    logger.info(
        f"LangGraph completed in {final_output['latency_seconds']}s. Cost: ${final_output['cost_usd']}."
    )
    return final_output
