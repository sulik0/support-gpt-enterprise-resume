from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, EmailStr, Field


# --- AUTH SCHEMAS ---
class UserCreate(BaseModel):
    """定义用户注册时提交的账号、密码和角色。"""

    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)
    role: str = Field(default="agent", pattern="^(admin|manager|agent)$")


class UserResponse(BaseModel):
    """定义对外返回的用户基础信息。"""

    id: int
    username: str
    role: str
    created_at: datetime

    class Config:
        """允许响应模型从 ORM 对象读取字段。"""

        from_attributes = True


class LoginRequest(BaseModel):
    """定义用户登录凭据。"""

    username: str
    password: str


class Token(BaseModel):
    """定义登录成功后返回的访问令牌信息。"""

    access_token: str
    token_type: str
    role: str


class TokenData(BaseModel):
    """定义从 JWT 载荷解析出的用户身份信息。"""

    username: Optional[str] = None
    role: Optional[str] = None


# --- CHAT SCHEMAS ---
class ChatMessage(BaseModel):
    """定义单条标准化对话消息。"""

    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str


class ChatRequest(BaseModel):
    """定义客服对话入口的会话、客户和知识库参数。"""

    session_id: str
    customer_id: str
    message: str
    kb_version: str = Field(default="v1")


class Citation(BaseModel):
    """定义回复引用的知识来源、正文片段和相关性信息。"""

    source: str
    text: str
    score: Optional[float] = None
    version: Optional[str] = None


class CostMetadata(BaseModel):
    """定义单次 Agent 请求的 token、成本和延迟统计。"""

    tokens_input: int = 0
    tokens_output: int = 0
    cost_usd: float = 0.0
    latency_seconds: float = 0.0


class ToolCallTrace(BaseModel):
    """定义返回给调用方的 Tool 调用审计摘要。"""

    tool_name: str
    role: str
    ticket_id: Optional[int] = None
    allowed: bool
    status: str
    latency_ms: float
    mocked: bool = True
    error: Optional[str] = None


class ChatResponse(BaseModel):
    """定义客服 Agent 对话的完整业务响应。"""

    session_id: str
    response: str
    sentiment: str
    priority: str
    tool_context: Dict[str, Any] = Field(default_factory=dict)
    tool_calls: List[ToolCallTrace] = Field(default_factory=list)
    citations: List[Citation]
    escalation_recommended: bool
    escalation_reason: Optional[str] = None
    analyzer_confidence: float = 1.0
    risk_level: str = "low"
    risk_score: float = 0.0
    risk_reasons: List[str] = Field(default_factory=list)
    cost_metadata: CostMetadata
    approval_required: bool = False
    approval_id: Optional[int] = None
    agent_run_id: Optional[str] = None
    feedback_token: Optional[str] = None


# --- TICKET SCHEMAS ---
class TicketCreate(BaseModel):
    """定义创建客服工单所需的基础字段。"""

    customer_id: str
    subject: str
    description: str


class TicketResponse(BaseModel):
    """定义包含状态、分析结果和时间信息的工单响应。"""

    id: int
    customer_id: str
    subject: str
    description: str
    status: str
    priority: str
    sentiment: Optional[str]
    department: Optional[str]
    sla_hours: Optional[float]
    created_at: datetime
    updated_at: datetime

    class Config:
        """允许响应模型从 ORM 工单对象读取字段。"""

        from_attributes = True


class TicketSummaryResponse(BaseModel):
    """定义工单摘要、关键问题和紧急程度结果。"""

    ticket_id: int
    summary: str
    key_issues: List[str]
    sentiment: str
    priority: str
    urgency_score: float


class TicketSentimentResponse(BaseModel):
    """定义工单情绪、置信度和优先级分析结果。"""

    ticket_id: int
    sentiment: str
    confidence_score: float
    detected_emotions: List[str]
    priority: str


class TicketEscalationResponse(BaseModel):
    """定义工单升级建议、目标部门和 SLA 信息。"""

    ticket_id: int
    escalation_recommended: bool
    escalation_reason: str
    suggested_department: str
    sla_hours: float


# --- RESOLUTION SCHEMAS ---
class SuggestResponseRequest(BaseModel):
    """定义生成工单建议回复所需的请求参数。"""

    ticket_id: int
    kb_version: str = Field(default="v1")


class SuggestResponseResponse(BaseModel):
    """定义建议回复、引用、工具上下文和 QA 结果。"""

    ticket_id: int
    suggested_response: str
    tool_context: Dict[str, Any] = Field(default_factory=dict)
    tool_calls: List[ToolCallTrace] = Field(default_factory=list)
    citations: List[Citation]
    qa_score: float
    hallucination_detected: bool
    analyzer_confidence: float = 1.0
    risk_level: str = "low"
    risk_score: float = 0.0
    risk_reasons: List[str] = Field(default_factory=list)
    cost_metadata: CostMetadata
    agent_run_id: Optional[str] = None
    feedback_token: Optional[str] = None


# --- CUSTOMER CONTEXT SCHEMAS ---
class CustomerContextRequest(BaseModel):
    """定义查询客户业务上下文的请求。"""

    customer_id: str


class OrderInfo(BaseModel):
    """定义客户近期订单的结构化摘要。"""

    order_id: str
    status: str
    items: List[str]
    total_amount: float
    order_date: datetime


class CustomerContextResponse(BaseModel):
    """定义客户画像、工单数量和近期订单上下文。"""

    customer_id: str
    name: str
    tier: str  # VIP, Standard, Enterprise
    open_tickets_count: int
    recent_orders: List[OrderInfo]
    last_interaction: Optional[datetime] = None


# --- EVALUATION SCHEMAS ---
class EvaluateResponseRequest(BaseModel):
    """定义回复质量评测所需的问题、上下文和答案。"""

    query: str
    context: List[str]
    response: str
    agent_run_id: Optional[str] = None
    external_ref: Optional[str] = Field(default=None, max_length=160)


class EvaluateResponseResponse(BaseModel):
    """定义回复评测的各项分数、结论和报告摘要。"""

    faithfulness_score: float
    context_precision: float
    context_recall: float
    hallucination_rate: float
    answer_relevance: float
    overall_quality_score: float
    passed_evaluation: bool
    report_summary: str


# --- HUMAN IN THE LOOP APPROVAL SCHEMAS ---
class ResponseApprovalRequest(BaseModel):
    """定义人工审批动作及可选的修改后回复。"""

    approval_id: int
    modified_response: Optional[str] = None
    status: str = Field(..., pattern="^(approved|modified|rejected)$")


class ResponseApprovalResponse(BaseModel):
    """定义人工审批完成后的最终回复和处理信息。"""

    id: int
    ticket_id: int
    status: str
    final_response: str
    latency_seconds: float
    approved_at: datetime


# --- FEEDBACK PIPELINE SCHEMAS ---
class UserFeedbackRequest(BaseModel):
    """定义用户针对一次 Agent Run 提交的评分和文字评价。"""

    agent_run_id: str = Field(..., min_length=1, max_length=36)
    feedback_token: str = Field(..., min_length=32, max_length=128)
    rating: int = Field(..., ge=1, le=5)
    comment: Optional[str] = Field(default=None, max_length=2000)
    idempotency_key: str = Field(..., min_length=8, max_length=120)


class FeedbackEventResponse(BaseModel):
    """返回反馈事件与 Agent Run、Trace 的关联信息。"""

    id: str
    agent_run_id: str
    ticket_id: Optional[int]
    trace_id: Optional[str]
    sequence: Optional[int]
    source: str
    feedback_type: str
    rating: Optional[int]
    comment: Optional[str]
    corrected_response: Optional[str]
    evaluation_metrics: Optional[Dict[str, Any]]
    evaluation_passed: Optional[bool]
    training_eligible: bool
    exclusion_reason: Optional[str]
    created_at: datetime

    class Config:
        """允许响应模型从 ORM 对象读取字段。"""

        from_attributes = True


class AgentRunResponse(BaseModel):
    """返回一次 Agent 执行快照及其全部反馈事件。"""

    id: str
    ticket_id: Optional[int]
    request_id: str
    trace_id: Optional[str]
    endpoint: str
    workflow_version: str
    prompt_version: str
    model_provider: str
    model_name: str
    kb_version: str
    input_text: str
    output_text: str
    workflow_path: List[str]
    tool_calls: List[Dict[str, Any]]
    citations: List[Dict[str, Any]]
    qa_score: Optional[float]
    hallucination_detected: bool
    escalation_recommended: bool
    approval_required: bool
    workflow_errors: List[str]
    tokens_input: int
    tokens_output: int
    latency_seconds: float
    created_at: datetime
    feedback_events: List[FeedbackEventResponse] = Field(default_factory=list)

    class Config:
        """允许响应模型从 ORM 对象读取字段。"""

        from_attributes = True


class AgentRunSummaryResponse(BaseModel):
    """定义可观测页面列表所需的低敏 Agent Run 摘要。"""

    id: str
    ticket_id: Optional[int]
    request_id: str
    trace_id: Optional[str]
    endpoint: str
    workflow_version: str
    prompt_version: str
    model_provider: str
    model_name: str
    kb_version: str
    workflow_path: List[str]
    qa_score: Optional[float]
    hallucination_detected: bool
    escalation_recommended: bool
    approval_required: bool
    workflow_errors: List[str]
    tokens_input: int
    tokens_output: int
    latency_seconds: float
    created_at: datetime

    class Config:
        """允许从 AgentRun ORM 实例读取摘要字段。"""

        from_attributes = True


class AgentRunPageResponse(BaseModel):
    """返回 Agent Run 分页结果与总数。"""

    items: List[AgentRunSummaryResponse]
    total: int
    limit: int
    offset: int
