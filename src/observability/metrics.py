from prometheus_client import Counter, Histogram, Gauge, REGISTRY
from src.config import settings

# Prevent double registration of metrics if reloading
def safe_register(metric_cls, name, *args, **kwargs):
    try:
        return metric_cls(name, *args, **kwargs)
    except ValueError:
        # If already registered, find in registry
        for collector in REGISTRY._names_to_collectors.values():
            if hasattr(collector, "_name") and collector._name == name:
                return collector
            # Gauge/Counter names might map slightly differently
            if name in REGISTRY._names_to_collectors:
                return REGISTRY._names_to_collectors[name]
        # Fallback to recreate if anything fails
        return metric_cls(name, *args, **kwargs)

# HTTP metrics
HTTP_REQUESTS_TOTAL = safe_register(
    Counter, "http_requests_total",
    "Total HTTP requests received",
    ["method", "endpoint", "status"]
)

HTTP_REQUEST_DURATION_SECONDS = safe_register(
    Histogram, "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"]
)

# LLM metrics
LLM_TOKENS_TOTAL = safe_register(
    Counter, "llm_tokens_total",
    "Total tokens consumed by LLM transactions",
    ["model", "type"]  # input, output
)

LLM_COST_TOTAL = safe_register(
    Counter, "llm_cost_total",
    "Total estimated cost in USD of LLM transactions",
    ["model"]
)

LLM_LATENCY_SECONDS = safe_register(
    Histogram, "llm_latency_seconds",
    "LLM API latency in seconds",
    ["model", "operation"]
)

# Agent Execution metrics
AGENT_EXECUTION_DURATION_SECONDS = safe_register(
    Histogram, "agent_execution_duration_seconds",
    "Agent execution time in seconds",
    ["agent_name"]
)

AGENT_EXECUTION_COUNT = safe_register(
    Counter, "agent_execution_total",
    "Total agent executions count",
    ["agent_name", "status"]
)

AGENT_REQUESTS_TOTAL = safe_register(
    Counter, "agent_requests_total",
    "Total end-to-end Agent workflow requests",
    ["status"]
)

AGENT_NODE_EXECUTIONS_TOTAL = safe_register(
    Counter, "agent_node_executions_total",
    "Total Agent node executions",
    ["node", "status"]
)

AGENT_NODE_DURATION_SECONDS = safe_register(
    Histogram, "agent_node_duration_seconds",
    "Agent node execution duration in seconds",
    ["node"]
)

TOOL_CALLS_TOTAL = safe_register(
    Counter, "agent_tool_calls_total",
    "Total ToolRegistry calls by tool and result status",
    ["tool_name", "status"]
)

TOOL_CALL_DURATION_SECONDS = safe_register(
    Histogram, "agent_tool_call_duration_seconds",
    "ToolRegistry call duration in seconds",
    ["tool_name"]
)

HUMAN_APPROVALS_TOTAL = safe_register(
    Counter, "human_approvals_total",
    "Total human approval workflow events",
    ["status"]
)

# Business-level metrics
TICKET_SENTIMENT_TOTAL = safe_register(
    Counter, "ticket_sentiment_total",
    "Total processed tickets by detected sentiment",
    ["sentiment"]
)

TICKET_ESCALATIONS_TOTAL = safe_register(
    Counter, "ticket_escalations_total",
    "Total ticket escalations recommended",
    ["department", "priority"]
)

ACTIVE_SESSIONS = safe_register(
    Gauge, "active_sessions_count",
    "Number of active user sessions in memory"
)

QA_SCORE_HISTOGRAM = safe_register(
    Histogram, "qa_score_ratio",
    "Distribution of quality assurance scores",
    buckets=[0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 1.0]
)

GUARDRAIL_VIOLATIONS_TOTAL = safe_register(
    Counter, "guardrail_violations_total",
    "Total guardrail violations caught",
    ["guardrail_type"] # pii, prompt_injection, jailbreak, response_filter
)
