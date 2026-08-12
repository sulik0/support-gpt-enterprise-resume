import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    JSON,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from src.database import Base


class User(Base):
    """保存系统用户、登录凭据摘要及 RBAC 角色。"""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(100), unique=True, index=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role = Column(String(50), nullable=False, default="agent")  # admin, manager, agent
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    approvals = relationship("ResponseApproval", back_populates="agent")


class Ticket(Base):
    """保存客服工单主体、分析结果和当前处理状态。"""

    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(String(100), index=True, nullable=False)
    subject = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    status = Column(
        String(50), nullable=False, default="open"
    )  # open, in_progress, resolved
    priority = Column(
        String(50), nullable=False, default="medium"
    )  # low, medium, high, urgent
    sentiment = Column(String(50), nullable=True)  # positive, neutral, negative
    department = Column(String(100), nullable=True)  # billing, technical, returns, etc.
    sla_hours = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)
    updated_at = Column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )

    approvals = relationship(
        "ResponseApproval", back_populates="ticket", cascade="all, delete-orphan"
    )
    agent_runs = relationship("AgentRun", back_populates="ticket")


class SessionMemory(Base):
    """持久化会话标识及多轮对话历史，作为 Redis 降级存储。"""

    __tablename__ = "session_memories"

    session_id = Column(String(100), primary_key=True, index=True)
    customer_id = Column(String(100), index=True, nullable=False)
    conversation_history = Column(
        JSON, nullable=False, default=list
    )  # List of message dicts: [{"role": "user", "content": "..."}]
    updated_at = Column(
        DateTime, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )


class KnowledgeDoc(Base):
    """保存可版本化、可分类检索的知识库文档。"""

    __tablename__ = "knowledge_docs"

    id = Column(String(100), primary_key=True, index=True)
    title = Column(String(255), nullable=False)
    content = Column(Text, nullable=False)
    version = Column(String(50), nullable=False, default="v1")
    category = Column(String(100), nullable=False)
    metadata_json = Column(JSON, nullable=True)  # Extra fields
    created_at = Column(DateTime, default=datetime.datetime.utcnow)


class ResponseApproval(Base):
    """保存 AI 回复草稿、人工审批结果及处理耗时。"""

    __tablename__ = "response_approvals"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=False)
    drafted_response = Column(Text, nullable=False)
    modified_response = Column(Text, nullable=True)
    status = Column(
        String(50), nullable=False, default="pending"
    )  # pending, approved, modified, rejected
    agent_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    latency_seconds = Column(Float, nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

    ticket = relationship("Ticket", back_populates="approvals")
    agent = relationship("User", back_populates="approvals")


class AgentRun(Base):
    """持久化一次 Agent Workflow 的输入、输出版本及质量快照。

    该记录是 Trace、反馈事件和训练数据候选之间的统一关联主键。
    """

    __tablename__ = "agent_runs"

    id = Column(String(36), primary_key=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=True, index=True)
    session_id_hash = Column(String(64), nullable=True, index=True)
    request_id = Column(String(128), nullable=False, index=True)
    trace_id = Column(String(32), nullable=True, index=True)
    feedback_token_hash = Column(String(64), nullable=False)
    endpoint = Column(String(100), nullable=False)
    workflow_version = Column(String(100), nullable=False)
    prompt_version = Column(String(100), nullable=False)
    model_provider = Column(String(50), nullable=False)
    model_name = Column(String(100), nullable=False)
    kb_version = Column(String(50), nullable=False)
    input_text = Column(Text, nullable=False)
    output_text = Column(Text, nullable=False)
    workflow_path = Column(JSON, nullable=False, default=list)
    tool_calls = Column(JSON, nullable=False, default=list)
    citations = Column(JSON, nullable=False, default=list)
    qa_score = Column(Float, nullable=True)
    hallucination_detected = Column(Boolean, nullable=False, default=False)
    escalation_recommended = Column(Boolean, nullable=False, default=False)
    approval_required = Column(Boolean, nullable=False, default=False)
    workflow_errors = Column(JSON, nullable=False, default=list)
    tokens_input = Column(Integer, nullable=False, default=0)
    tokens_output = Column(Integer, nullable=False, default=0)
    latency_seconds = Column(Float, nullable=False, default=0.0)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    ticket = relationship("Ticket", back_populates="agent_runs")
    feedback_events = relationship(
        "FeedbackEvent", back_populates="agent_run", cascade="all, delete-orphan"
    )
    links = relationship(
        "AgentRunLink", back_populates="agent_run", cascade="all, delete-orphan"
    )


class AgentRunLink(Base):
    """关联 Agent Run 与审批等业务实体，避免修改既有业务表结构。"""

    __tablename__ = "agent_run_links"
    __table_args__ = (
        UniqueConstraint("entity_type", "entity_id", name="uq_agent_run_entity"),
    )

    id = Column(Integer, primary_key=True, index=True)
    agent_run_id = Column(
        String(36), ForeignKey("agent_runs.id"), nullable=False, index=True
    )
    entity_type = Column(String(50), nullable=False)
    entity_id = Column(String(100), nullable=False)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    agent_run = relationship("AgentRun", back_populates="links")


class FeedbackEvent(Base):
    """保存用户评价、人工修正和质量评测等统一反馈事件。

    原始内容在进入该表前完成 PII 脱敏，Trace ID 仅用于链路定位。
    """

    __tablename__ = "feedback_events"
    __table_args__ = (
        UniqueConstraint("source", "external_ref", name="uq_feedback_external_ref"),
        UniqueConstraint("source", "agent_run_id", name="uq_feedback_source_run"),
    )

    id = Column(String(36), primary_key=True)
    agent_run_id = Column(
        String(36), ForeignKey("agent_runs.id"), nullable=False, index=True
    )
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=True, index=True)
    trace_id = Column(String(32), nullable=True, index=True)
    sequence = Column(Integer, nullable=True)
    source = Column(String(50), nullable=False, index=True)
    feedback_type = Column(String(50), nullable=False, index=True)
    external_ref = Column(String(160), nullable=False)
    rating = Column(Integer, nullable=True)
    comment = Column(Text, nullable=True)
    original_response = Column(Text, nullable=True)
    corrected_response = Column(Text, nullable=True)
    evaluation_metrics = Column(JSON, nullable=True)
    evaluation_passed = Column(Boolean, nullable=True)
    training_eligible = Column(Boolean, nullable=False, default=False, index=True)
    exclusion_reason = Column(String(255), nullable=True)
    created_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    agent_run = relationship("AgentRun", back_populates="feedback_events")
