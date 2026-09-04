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


class AgentExecution(Base):
    """记录可暂停、可恢复的 LangGraph 执行元数据。

    Checkpoint 正文由 LangGraph Saver 管理，本表只保存业务关联与恢复租约。
    """

    __tablename__ = "agent_executions"
    __table_args__ = (
        UniqueConstraint("approval_id", name="uq_agent_execution_approval"),
    )

    id = Column(String(36), primary_key=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=False, index=True)
    approval_id = Column(
        Integer, ForeignKey("response_approvals.id"), nullable=True, index=True
    )
    agent_run_id = Column(
        String(36), ForeignKey("agent_runs.id"), nullable=True, index=True
    )
    request_id = Column(String(128), nullable=False, index=True)
    checkpoint_namespace = Column(String(100), nullable=False)
    checkpoint_id = Column(String(100), nullable=True)
    checkpoint_backend = Column(String(30), nullable=False)
    workflow_version = Column(String(100), nullable=False)
    status = Column(String(40), nullable=False, index=True)
    interrupt_type = Column(String(80), nullable=True)
    interrupt_payload = Column(JSON, nullable=True)
    lock_version = Column(Integer, nullable=False, default=1)
    resume_attempts = Column(Integer, nullable=False, default=0)
    lease_owner = Column(String(36), nullable=True)
    lease_expires_at = Column(DateTime, nullable=True)
    initial_trace_id = Column(String(32), nullable=True, index=True)
    resume_trace_id = Column(String(32), nullable=True, index=True)
    last_error_type = Column(String(100), nullable=True)
    last_error_message = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)
    updated_at = Column(
        DateTime,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
        nullable=False,
    )
    interrupted_at = Column(DateTime, nullable=True)
    resumed_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)


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


class ToolAction(Base):
    """持久化高风险 Tool 的提议、审批和执行状态。"""

    __tablename__ = "tool_actions"

    id = Column(String(36), primary_key=True)
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=False, index=True)
    tool_name = Column(String(160), nullable=False, index=True)
    tool_version = Column(String(50), nullable=False)
    intent = Column(String(80), nullable=False)
    risk_level = Column(String(30), nullable=False)
    operation_type = Column(String(20), nullable=False)
    status = Column(String(40), nullable=False, index=True)
    version = Column(Integer, nullable=False, default=1)
    policy_version = Column(String(100), nullable=False)
    payload_encrypted = Column(Text, nullable=False)
    payload_hash = Column(String(64), nullable=False)
    payload_summary = Column(JSON, nullable=False, default=dict)
    result_summary = Column(JSON, nullable=True)
    error_type = Column(String(80), nullable=True)
    failure_reason = Column(String(255), nullable=True)
    request_id = Column(String(128), nullable=False, index=True)
    trace_id = Column(String(32), nullable=True, index=True)
    proposed_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    proposed_by_role = Column(String(50), nullable=False)
    reviewed_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    reviewed_by_role = Column(String(50), nullable=True)
    executed_by_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    review_comment = Column(Text, nullable=True)
    created_at = Column(
        DateTime, default=datetime.datetime.utcnow, nullable=False, index=True
    )
    updated_at = Column(
        DateTime,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
        nullable=False,
    )
    reviewed_at = Column(DateTime, nullable=True)
    execution_started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    events = relationship(
        "ToolActionEvent",
        back_populates="tool_action",
        cascade="all, delete-orphan",
        order_by="ToolActionEvent.sequence",
    )


class ToolActionEvent(Base):
    """以 Append-only 方式保存 Tool Action 的每次合法迁移。"""

    __tablename__ = "tool_action_events"
    __table_args__ = (
        UniqueConstraint("tool_action_id", "sequence", name="uq_tool_action_event"),
    )

    id = Column(String(36), primary_key=True)
    tool_action_id = Column(
        String(36), ForeignKey("tool_actions.id"), nullable=False, index=True
    )
    sequence = Column(Integer, nullable=False)
    action = Column(String(60), nullable=False)
    from_status = Column(String(40), nullable=True)
    to_status = Column(String(40), nullable=False)
    actor_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    actor_role = Column(String(50), nullable=True)
    request_id = Column(String(128), nullable=False, index=True)
    trace_id = Column(String(32), nullable=True, index=True)
    details = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.datetime.utcnow, nullable=False)

    tool_action = relationship("ToolAction", back_populates="events")


class ToolInvocationAudit(Base):
    """持久化 ToolRegistry 每次允许、拒绝或执行的脱敏审计摘要。"""

    __tablename__ = "tool_invocation_audits"

    id = Column(String(36), primary_key=True)
    tool_action_id = Column(
        String(36), ForeignKey("tool_actions.id"), nullable=True, index=True
    )
    ticket_id = Column(Integer, ForeignKey("tickets.id"), nullable=True, index=True)
    request_id = Column(String(128), nullable=False, index=True)
    trace_id = Column(String(32), nullable=True, index=True)
    tool_name = Column(String(160), nullable=False, index=True)
    tool_version = Column(String(50), nullable=False)
    operation_type = Column(String(20), nullable=False)
    risk_level = Column(String(30), nullable=False)
    actor_user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    actor_role = Column(String(50), nullable=False)
    allowed = Column(Boolean, nullable=False)
    status = Column(String(60), nullable=False, index=True)
    attempts = Column(Integer, nullable=False, default=0)
    latency_ms = Column(Float, nullable=False, default=0.0)
    mocked = Column(Boolean, nullable=False, default=False)
    error_type = Column(String(80), nullable=True)
    payload_hash = Column(String(64), nullable=False)
    payload_keys = Column(JSON, nullable=False, default=list)
    result_summary = Column(JSON, nullable=True)
    policy_version = Column(String(100), nullable=False)
    created_at = Column(
        DateTime, default=datetime.datetime.utcnow, nullable=False, index=True
    )
