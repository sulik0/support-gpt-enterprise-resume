from pydantic import BaseModel, Field, EmailStr
from typing import List, Dict, Any, Optional
from datetime import datetime

# --- AUTH SCHEMAS ---
class UserCreate(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6)
    role: str = Field(default="agent", pattern="^(admin|manager|agent)$")

class UserResponse(BaseModel):
    id: int
    username: str
    role: str
    created_at: datetime

    class Config:
        from_attributes = True

class LoginRequest(BaseModel):
    username: str
    password: str

class Token(BaseModel):
    access_token: str
    token_type: str
    role: str

class TokenData(BaseModel):
    username: Optional[str] = None
    role: Optional[str] = None


# --- CHAT SCHEMAS ---
class ChatMessage(BaseModel):
    role: str = Field(..., pattern="^(user|assistant|system)$")
    content: str

class ChatRequest(BaseModel):
    session_id: str
    customer_id: str
    message: str
    kb_version: str = Field(default="v1")

class Citation(BaseModel):
    source: str
    text: str
    score: Optional[float] = None
    version: Optional[str] = None

class CostMetadata(BaseModel):
    tokens_input: int = 0
    tokens_output: int = 0
    cost_usd: float = 0.0
    latency_seconds: float = 0.0

class ChatResponse(BaseModel):
    session_id: str
    response: str
    sentiment: str
    priority: str
    tool_context: Dict[str, Any] = Field(default_factory=dict)
    citations: List[Citation]
    escalation_recommended: bool
    escalation_reason: Optional[str] = None
    cost_metadata: CostMetadata
    approval_required: bool = False
    approval_id: Optional[int] = None


# --- TICKET SCHEMAS ---
class TicketCreate(BaseModel):
    customer_id: str
    subject: str
    description: str

class TicketResponse(BaseModel):
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
        from_attributes = True

class TicketSummaryResponse(BaseModel):
    ticket_id: int
    summary: str
    key_issues: List[str]
    sentiment: str
    priority: str
    urgency_score: float

class TicketSentimentResponse(BaseModel):
    ticket_id: int
    sentiment: str
    confidence_score: float
    detected_emotions: List[str]
    priority: str

class TicketEscalationResponse(BaseModel):
    ticket_id: int
    escalation_recommended: bool
    escalation_reason: str
    suggested_department: str
    sla_hours: float


# --- RESOLUTION SCHEMAS ---
class SuggestResponseRequest(BaseModel):
    ticket_id: int
    kb_version: str = Field(default="v1")

class SuggestResponseResponse(BaseModel):
    ticket_id: int
    suggested_response: str
    tool_context: Dict[str, Any] = Field(default_factory=dict)
    citations: List[Citation]
    qa_score: float
    hallucination_detected: bool
    cost_metadata: CostMetadata


# --- CUSTOMER CONTEXT SCHEMAS ---
class CustomerContextRequest(BaseModel):
    customer_id: str

class OrderInfo(BaseModel):
    order_id: str
    status: str
    items: List[str]
    total_amount: float
    order_date: datetime

class CustomerContextResponse(BaseModel):
    customer_id: str
    name: str
    tier: str  # VIP, Standard, Enterprise
    open_tickets_count: int
    recent_orders: List[OrderInfo]
    last_interaction: Optional[datetime] = None


# --- EVALUATION SCHEMAS ---
class EvaluateResponseRequest(BaseModel):
    query: str
    context: List[str]
    response: str

class EvaluateResponseResponse(BaseModel):
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
    approval_id: int
    modified_response: Optional[str] = None
    status: str = Field(..., pattern="^(approved|modified|rejected)$")

class ResponseApprovalResponse(BaseModel):
    id: int
    ticket_id: int
    status: str
    final_response: str
    latency_seconds: float
    approved_at: datetime
