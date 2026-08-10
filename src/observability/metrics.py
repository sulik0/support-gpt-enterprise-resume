"""Application metrics backed exclusively by the OpenTelemetry Metrics API."""

from opentelemetry import metrics


meter = metrics.get_meter("supportgpt.observability.metrics", "1.0.0")

# Counter names omit ``_total`` because the Collector Prometheus exporter adds
# the conventional suffix when translating OpenTelemetry monotonic sums.
HTTP_REQUESTS_TOTAL = meter.create_counter(
    "http_requests", description="Total HTTP requests received"
)
HTTP_REQUEST_DURATION_SECONDS = meter.create_histogram(
    "http_request_duration_seconds", unit="s", description="HTTP request duration"
)
LLM_TOKENS_TOTAL = meter.create_counter(
    "llm_tokens", unit="{token}", description="Total tokens consumed by LLM calls"
)
LLM_COST_TOTAL = meter.create_counter(
    "llm_cost", unit="USD", description="Total estimated LLM cost"
)
LLM_LATENCY_SECONDS = meter.create_histogram(
    "llm_latency_seconds", unit="s", description="LLM API latency"
)
AGENT_EXECUTION_DURATION_SECONDS = meter.create_histogram(
    "agent_execution_duration_seconds", unit="s", description="Agent execution time"
)
AGENT_EXECUTION_COUNT = meter.create_counter(
    "agent_execution", description="Total agent executions"
)
AGENT_REQUESTS_TOTAL = meter.create_counter(
    "agent_requests", description="Total end-to-end Agent workflow requests"
)
AGENT_NODE_EXECUTIONS_TOTAL = meter.create_counter(
    "agent_node_executions", description="Total Agent node executions"
)
AGENT_NODE_DURATION_SECONDS = meter.create_histogram(
    "agent_node_duration_seconds",
    unit="s",
    description="Agent node execution duration",
)
TOOL_CALLS_TOTAL = meter.create_counter(
    "agent_tool_calls", description="Total ToolRegistry calls"
)
TOOL_CALL_DURATION_SECONDS = meter.create_histogram(
    "agent_tool_call_duration_seconds",
    unit="s",
    description="ToolRegistry call duration",
)
HUMAN_APPROVALS_TOTAL = meter.create_counter(
    "human_approvals", description="Total human approval workflow events"
)
TICKET_SENTIMENT_TOTAL = meter.create_counter(
    "ticket_sentiment", description="Total processed tickets by sentiment"
)
TICKET_ESCALATIONS_TOTAL = meter.create_counter(
    "ticket_escalations", description="Total ticket escalations"
)
ACTIVE_SESSIONS = meter.create_up_down_counter(
    "active_sessions_count", description="Number of active user sessions in memory"
)
QA_SCORE_HISTOGRAM = meter.create_histogram(
    "qa_score_ratio", description="Distribution of quality assurance scores"
)
GUARDRAIL_VIOLATIONS_TOTAL = meter.create_counter(
    "guardrail_violations", description="Total guardrail violations"
)
