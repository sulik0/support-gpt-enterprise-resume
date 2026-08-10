from pydantic import BaseModel, Field, EmailStr
from typing import List, Dict, Any, Optional
from datetime import datetime

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
    cost_metadata: CostMetadata
    approval_required: bool = False
    approval_id: Optional[int] = None


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
    cost_metadata: CostMetadata


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
