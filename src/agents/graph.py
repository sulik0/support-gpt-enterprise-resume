import time
import logging
from typing import TypedDict, List, Dict, Any, Optional
from langgraph.graph import StateGraph, END

from src.config import settings
from src.agents.analyzer import ticket_analyzer_agent
from src.agents.retriever import knowledge_retriever_agent
from src.agents.tooling import tooling_agent
from src.agents.resolver import resolution_agent
from src.agents.quality_assurance import quality_assurance_agent
from src.agents.escalation import escalation_agent
from src.observability.cost_tracking import calculate_llm_cost
from src.observability.metrics import LLM_TOKENS_TOTAL, LLM_COST_TOTAL

logger = logging.getLogger("supportgpt.agents.graph")

class AgentState(TypedDict):
    ticket_id: int
    customer_id: str
    subject: str
    description: str
    kb_version: str
    sentiment: str
    priority: str
    intent: str
    department: str
    tool_context: Dict[str, Any]
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
async def analyze_node(state: AgentState) -> Dict[str, Any]:
    return await ticket_analyzer_agent.analyze(state)

async def retrieve_node(state: AgentState) -> Dict[str, Any]:
    return await knowledge_retriever_agent.retrieve(state)

async def tooling_node(state: AgentState) -> Dict[str, Any]:
    return await tooling_agent.enrich(state)

async def resolve_node(state: AgentState) -> Dict[str, Any]:
    return await resolution_agent.resolve(state)

async def qa_node(state: AgentState) -> Dict[str, Any]:
    return await quality_assurance_agent.verify(state)

async def escalate_node(state: AgentState) -> Dict[str, Any]:
    return await escalation_agent.evaluate(state)


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
        "ticket_id": initial_state.get("ticket_id", 0),
        "customer_id": initial_state.get("customer_id", ""),
        "subject": initial_state.get("subject", ""),
        "description": initial_state.get("description", ""),
        "kb_version": initial_state.get("kb_version", "v1"),
        "sentiment": "neutral",
        "priority": "medium",
        "intent": "general",
        "department": "general",
        "tool_context": {},
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
        "errors": []
    }

    logger.info(f"Invoking LangGraph flow for ticket ID {state_input['ticket_id']}")
    final_output = await compiled_graph.ainvoke(state_input)

    # Compute execution costs
    tokens_in = final_output.get("tokens_input", 0)
    tokens_out = final_output.get("tokens_output", 0)
    cost = calculate_llm_cost(settings.LLM_PROVIDER, tokens_in, tokens_out)
    
    final_output["cost_usd"] = cost
    final_output["latency_seconds"] = round(time.time() - start_time, 4)

    # Determine if human approval is required
    # Escalation needed or low QA score triggers approval
    if final_output.get("escalation_recommended") or final_output.get("qa_score", 1.0) < 0.8:
         final_output["approval_required"] = True

    # Record Prometheus telemetry metrics
    LLM_TOKENS_TOTAL.labels(model=settings.LLM_PROVIDER, type="input").inc(tokens_in)
    LLM_TOKENS_TOTAL.labels(model=settings.LLM_PROVIDER, type="output").inc(tokens_out)
    LLM_COST_TOTAL.labels(model=settings.LLM_PROVIDER).inc(cost)

    logger.info(f"LangGraph completed in {final_output['latency_seconds']}s. Cost: ${final_output['cost_usd']}.")
    return final_output
