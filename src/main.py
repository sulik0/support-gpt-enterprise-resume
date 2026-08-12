import time
import datetime
import uuid
import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException, status, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.future import select

from src.config import settings
from src.database import engine, init_db, get_db
from src.models.db_models import (
    AgentRun,
    ResponseApproval,
    SessionMemory,
    Ticket,
    User,
)
from src.models.schemas import (
    UserCreate,
    UserResponse,
    LoginRequest,
    Token,
    ChatRequest,
    ChatResponse,
    Citation,
    CostMetadata,
    TicketCreate,
    TicketResponse,
    TicketSummaryResponse,
    TicketSentimentResponse,
    TicketEscalationResponse,
    SuggestResponseRequest,
    SuggestResponseResponse,
    CustomerContextRequest,
    CustomerContextResponse,
    OrderInfo,
    EvaluateResponseRequest,
    EvaluateResponseResponse,
    ResponseApprovalRequest,
    ResponseApprovalResponse,
    UserFeedbackRequest,
    FeedbackEventResponse,
    AgentRunResponse,
)
from src.auth.jwt import verify_password, get_password_hash, create_access_token
from src.auth.rbac import (
    get_current_user,
    get_optional_current_user,
    require_admin,
    require_agent,
    require_manager,
)
from src.agents.graph import run_agent_workflow
from src.approval.workflows import human_it_loop_service
from src.tools.crm import crm_tool
from src.tools.ticketing import ticketing_tool
from src.tools.order_mgmt import order_mgmt_tool
from src.memory.redis_memory import redis_memory
from src.tickets.state_machine import TicketAction, ticket_state_machine
from src.observability.instrumentation import instrument_dependencies
from src.observability.tracing import (
    bind_request_id,
    get_current_trace_id,
    get_tracer,
    init_tracing,
    observed_span,
    reset_request_id,
    set_span_attributes,
)
from src.observability.metrics import HTTP_REQUESTS_TOTAL, HTTP_REQUEST_DURATION_SECONDS
from src.evaluation.framework import run_deeval_evaluation
from src.feedback.service import feedback_service

tracer = get_tracer(__name__)
logger = logging.getLogger("supportgpt.main")


async def _record_agent_run_fail_open(
    *,
    primary_db: AsyncSession,
    agent_output: dict,
    input_text: str,
    endpoint: str,
    session_id: str | None = None,
) -> AgentRun | None:
    """使用独立事务保存 Agent Run，失败时不影响客服主流程。"""
    try:
        feedback_sessions = async_sessionmaker(
            bind=primary_db.bind,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        async with feedback_sessions() as feedback_db:
            agent_run = await feedback_service.record_agent_run(
                feedback_db,
                agent_output=agent_output,
                input_text=input_text,
                endpoint=endpoint,
                session_id=session_id,
                trace_id=get_current_trace_id(),
            )
            await feedback_db.commit()
            return agent_run
    except Exception as exc:
        logger.warning("Unable to persist Agent Run for feedback: %s", exc)
        return None


async def _link_approval_fail_open(
    primary_db: AsyncSession, agent_run_id: str, approval_id: int
) -> None:
    """使用独立事务关联审批记录，关联失败只写日志。"""
    try:
        feedback_sessions = async_sessionmaker(
            bind=primary_db.bind,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        async with feedback_sessions() as feedback_db:
            await feedback_service.link_entity(
                feedback_db,
                agent_run_id=agent_run_id,
                entity_type="approval",
                entity_id=approval_id,
            )
            await feedback_db.commit()
    except Exception as exc:
        logger.warning("Unable to link approval to Agent Run: %s", exc)


async def _record_evaluation_fail_open(
    primary_db: AsyncSession,
    *,
    agent_run_id: str,
    metrics: dict,
    passed: bool,
    external_ref: str | None,
) -> None:
    """使用独立事务回写可信评测，写入失败不影响评测结果。"""
    try:
        feedback_sessions = async_sessionmaker(
            bind=primary_db.bind,
            class_=AsyncSession,
            expire_on_commit=False,
        )
        async with feedback_sessions() as feedback_db:
            await feedback_service.record_evaluation(
                feedback_db,
                agent_run_id=agent_run_id,
                metrics=metrics,
                passed=passed,
                external_ref=external_ref,
            )
            await feedback_db.commit()
    except HTTPException:
        raise
    except Exception as exc:
        logger.warning("Unable to persist evaluation feedback: %s", exc)


def _record_http_metrics(
    method: str, endpoint: str, status_code: str, duration: float
) -> None:
    try:
        HTTP_REQUESTS_TOTAL.add(
            1, {"method": method, "endpoint": endpoint, "status": status_code}
        )
        HTTP_REQUEST_DURATION_SECONDS.record(
            duration, {"method": method, "endpoint": endpoint}
        )
    except Exception:
        return


def _route_template(request: Request) -> str:
    """Return the matched route template without exporting raw path identifiers."""
    route = request.scope.get("route")
    return getattr(route, "path", "unmatched")


# --- FastAPI Lifespan Handler ---
@asynccontextmanager
async def lifespan(app: FastAPI):
    # 初始化统一 OpenTelemetry Trace 与 Metrics。
    init_tracing()
    # Create DB schemas (SQLite or PostgreSQL)
    await init_db()
    yield


app = FastAPI(
    title=settings.APP_NAME,
    version="1.0.0",
    description="Enterprise Customer Support AI Copilot Platform",
    lifespan=lifespan,
)

# Configure CORS for Frontend connectivity
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Observability Request Latency Middleware ---
@app.middleware("http")
async def track_http_telemetry(request: Request, call_next):
    start_time = time.time()
    endpoint = request.url.path
    method = request.method

    # Avoid polluting application metrics with health probes.
    if endpoint == "/health":
        return await call_next(request)

    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex
    request_token = bind_request_id(request_id)
    try:
        with observed_span(tracer, f"api.{method}") as span:
            set_span_attributes(
                span,
                {
                    "http.method": method,
                    "request.id": request_id,
                },
            )
            try:
                response = await call_next(request)
                status_code = str(response.status_code)

                duration = time.time() - start_time
                route_template = _route_template(request)
                span.update_name(f"api.{method} {route_template}")
                _record_http_metrics(method, route_template, status_code, duration)
                set_span_attributes(
                    span,
                    {
                        "http.route": route_template,
                        "http.status_code": response.status_code,
                        "http.duration_seconds": round(duration, 4),
                    },
                )
                response.headers["X-Request-ID"] = request_id
                trace_id = get_current_trace_id()
                if trace_id:
                    response.headers["X-Trace-ID"] = trace_id
                return response
            except Exception as e:
                route_template = _route_template(request)
                _record_http_metrics(
                    method, route_template, "500", time.time() - start_time
                )
                set_span_attributes(
                    span,
                    {"http.status_code": 500, "error.type": e.__class__.__name__},
                )
                raise
    finally:
        reset_request_id(request_token)


# Auto-instrument infrastructure once; each integration fails open when unavailable.
instrument_dependencies(app, engine)


# --- AUTH ENDPOINTS ---
@app.post(
    "/auth/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED
)
async def register_user(user_in: UserCreate, db: AsyncSession = Depends(get_db)):
    # Check if username exists
    existing = await db.execute(select(User).filter(User.username == user_in.username))
    if existing.scalars().first():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Username already registered",
        )

    new_user = User(
        username=user_in.username,
        hashed_password=get_password_hash(user_in.password),
        role=user_in.role,
    )
    db.add(new_user)
    await db.commit()
    await db.refresh(new_user)
    return new_user


@app.post("/auth/token", response_model=Token)
async def login_for_access_token(
    form_data: LoginRequest, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(User).filter(User.username == form_data.username))
    user = result.scalars().first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    access_token = create_access_token(data={"sub": user.username, "role": user.role})
    return {"access_token": access_token, "token_type": "bearer", "role": user.role}


@app.get("/auth/users/me", response_model=UserResponse)
async def read_users_me(current_user: User = Depends(get_current_user)):
    return current_user


# --- CORE COPILOT APIS ---
@app.get("/health")
async def health_check():
    return {"status": "healthy", "timestamp": datetime.datetime.utcnow().isoformat()}


@app.post("/chat", response_model=ChatResponse)
async def chat_session(req: ChatRequest, db: AsyncSession = Depends(get_db)):
    """
    Submit a conversational message. Runs the LangGraph multi-agent flow.
    Appends conversation exchanges to historical memory.
    """
    # 1. Retrieve or create ticket log record
    ticket = Ticket(
        customer_id=req.customer_id,
        subject="Active Chat Conversation",
        description=req.message,
        status="open",
    )
    db.add(ticket)
    await db.commit()
    await db.refresh(ticket)

    # 2. Retrieve history memory from db
    history_res = await db.execute(
        select(SessionMemory).filter(SessionMemory.session_id == req.session_id)
    )
    session_mem = history_res.scalars().first()
    if not session_mem:
        session_mem = SessionMemory(
            session_id=req.session_id,
            customer_id=req.customer_id,
            conversation_history=[],
        )
        db.add(session_mem)

    # Use Redis as short-term working memory when available; SQL remains durable history.
    redis_history = await redis_memory.load_messages(req.session_id)
    session_history = list(
        redis_history if redis_history is not None else session_mem.conversation_history
    )
    session_history.append({"role": "user", "content": req.message})

    # 3. Invoke multi-agent graph
    initial_agent_state = {
        "ticket_id": ticket.id,
        "customer_id": req.customer_id,
        "subject": ticket.subject,
        "description": req.message,
        "kb_version": req.kb_version,
    }

    agent_output = await run_agent_workflow(initial_agent_state)

    # Update ticket details in SQL DB
    ticket.sentiment = agent_output.get("sentiment")
    ticket.priority = agent_output.get("priority")
    ticket.department = agent_output.get("department")
    ticket.sla_hours = agent_output.get("sla_hours")

    # 4. Save to Response Approval if HITL is required
    approval_id = None
    if agent_output.get("approval_required"):
        appr_obj = await human_it_loop_service.create_pending_approval(
            db=db,
            ticket_id=ticket.id,
            drafted_response=agent_output.get("suggested_response", ""),
        )
        approval_id = appr_obj.id

    # Append assistant message
    session_history.append(
        {"role": "assistant", "content": agent_output.get("suggested_response", "")}
    )
    session_mem.conversation_history = session_history
    await redis_memory.save_messages(req.session_id, session_history)

    await db.commit()

    # Feedback Pipeline 使用独立事务，失败时不阻断客服主流程。
    agent_run = await _record_agent_run_fail_open(
        primary_db=db,
        agent_output=agent_output,
        input_text=req.message,
        endpoint="/chat",
        session_id=req.session_id,
    )
    if agent_run and approval_id:
        await _link_approval_fail_open(db, agent_run.id, approval_id)

    # Build schema output
    citations = [
        Citation(source=c.source, text=c.text, score=c.score, version=c.version)
        for c in agent_output.get("context_citations", [])
    ]

    cost_meta = CostMetadata(
        tokens_input=agent_output.get("tokens_input", 0),
        tokens_output=agent_output.get("tokens_output", 0),
        cost_usd=agent_output.get("cost_usd", 0.0),
        latency_seconds=agent_output.get("latency_seconds", 0.0),
    )

    return ChatResponse(
        session_id=req.session_id,
        response=agent_output.get("suggested_response", ""),
        sentiment=agent_output.get("sentiment", "neutral"),
        priority=agent_output.get("priority", "medium"),
        tool_context=agent_output.get("tool_context", {}),
        tool_calls=agent_output.get("tool_calls", []),
        citations=citations,
        escalation_recommended=agent_output.get("escalation_recommended", False),
        escalation_reason=agent_output.get("escalation_reason"),
        cost_metadata=cost_meta,
        approval_required=agent_output.get("approval_required", False),
        approval_id=approval_id,
        agent_run_id=agent_run.id if agent_run else None,
        feedback_token=(
            getattr(agent_run, "_feedback_token", None) if agent_run else None
        ),
    )


@app.post("/summarize-ticket", response_model=TicketSummaryResponse)
async def summarize_ticket(
    req: SuggestResponseRequest, db: AsyncSession = Depends(get_db)
):
    """Analyze a ticket description and summarize key issues."""
    ticket_res = await db.execute(select(Ticket).filter(Ticket.id == req.ticket_id))
    ticket = ticket_res.scalars().first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    initial_state = {
        "ticket_id": ticket.id,
        "customer_id": ticket.customer_id,
        "subject": ticket.subject,
        "description": ticket.description,
        "kb_version": req.kb_version,
    }
    agent_output = await run_agent_workflow(initial_state)

    summary = f"The customer is reporting an issue regarding '{ticket.subject}'. Category: {agent_output.get('department')}."
    key_issues = [ticket.subject, f"Detected Intent: {agent_output.get('intent')}"]

    return TicketSummaryResponse(
        ticket_id=ticket.id,
        summary=summary,
        key_issues=key_issues,
        sentiment=agent_output.get("sentiment", "neutral"),
        priority=agent_output.get("priority", "medium"),
        urgency_score=0.9 if agent_output.get("priority") == "urgent" else 0.5,
    )


@app.post("/suggest-response", response_model=SuggestResponseResponse)
async def suggest_response(
    req: SuggestResponseRequest, db: AsyncSession = Depends(get_db)
):
    """Provide a response suggestion with citations and QA verification details."""
    ticket_res = await db.execute(select(Ticket).filter(Ticket.id == req.ticket_id))
    ticket = ticket_res.scalars().first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    initial_state = {
        "ticket_id": ticket.id,
        "customer_id": ticket.customer_id,
        "subject": ticket.subject,
        "description": ticket.description,
        "kb_version": req.kb_version,
    }
    agent_output = await run_agent_workflow(initial_state)

    # 先结束读取事务，再使用隔离事务写入反馈域。
    await db.commit()
    agent_run = await _record_agent_run_fail_open(
        primary_db=db,
        agent_output=agent_output,
        input_text=ticket.description,
        endpoint="/suggest-response",
    )

    citations = [
        Citation(source=c.source, text=c.text, score=c.score, version=c.version)
        for c in agent_output.get("context_citations", [])
    ]

    cost_meta = CostMetadata(
        tokens_input=agent_output.get("tokens_input", 0),
        tokens_output=agent_output.get("tokens_output", 0),
        cost_usd=agent_output.get("cost_usd", 0.0),
        latency_seconds=agent_output.get("latency_seconds", 0.0),
    )

    return SuggestResponseResponse(
        ticket_id=ticket.id,
        suggested_response=agent_output.get("suggested_response", ""),
        tool_context=agent_output.get("tool_context", {}),
        tool_calls=agent_output.get("tool_calls", []),
        citations=citations,
        qa_score=agent_output.get("qa_score", 1.0),
        hallucination_detected=agent_output.get("hallucination_detected", False),
        cost_metadata=cost_meta,
        agent_run_id=agent_run.id if agent_run else None,
        feedback_token=(
            getattr(agent_run, "_feedback_token", None) if agent_run else None
        ),
    )


@app.post("/analyze-sentiment", response_model=TicketSentimentResponse)
async def analyze_sentiment(
    req: SuggestResponseRequest, db: AsyncSession = Depends(get_db)
):
    """Evaluate customer ticket tone and urgency levels."""
    ticket_res = await db.execute(select(Ticket).filter(Ticket.id == req.ticket_id))
    ticket = ticket_res.scalars().first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    initial_state = {
        "ticket_id": ticket.id,
        "customer_id": ticket.customer_id,
        "subject": ticket.subject,
        "description": ticket.description,
        "kb_version": req.kb_version,
    }
    agent_output = await run_agent_workflow(initial_state)

    return TicketSentimentResponse(
        ticket_id=ticket.id,
        sentiment=agent_output.get("sentiment", "neutral"),
        confidence_score=0.95,
        detected_emotions=[agent_output.get("sentiment", "neutral")],
        priority=agent_output.get("priority", "medium"),
    )


@app.post("/recommend-escalation", response_model=TicketEscalationResponse)
async def recommend_escalation(
    req: SuggestResponseRequest, db: AsyncSession = Depends(get_db)
):
    """SLA routing prediction."""
    ticket_res = await db.execute(select(Ticket).filter(Ticket.id == req.ticket_id))
    ticket = ticket_res.scalars().first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    initial_state = {
        "ticket_id": ticket.id,
        "customer_id": ticket.customer_id,
        "subject": ticket.subject,
        "description": ticket.description,
        "kb_version": req.kb_version,
    }
    agent_output = await run_agent_workflow(initial_state)

    return TicketEscalationResponse(
        ticket_id=ticket.id,
        escalation_recommended=agent_output.get("escalation_recommended", False),
        escalation_reason=agent_output.get("escalation_reason", "Standard flow"),
        suggested_department=agent_output.get("department", "general"),
        sla_hours=agent_output.get("sla_hours", 24.0),
    )


@app.post("/customer-context", response_model=CustomerContextResponse)
async def get_customer_context(req: CustomerContextRequest):
    """Retrieve full customer profile summary across CRM and Ticketing tools."""
    profile = crm_tool.get_customer_profile(req.customer_id)
    history = ticketing_tool.get_past_tickets(req.customer_id)
    orders = order_mgmt_tool.get_order_history(req.customer_id)

    order_schemas = [
        OrderInfo(
            order_id=o["order_id"],
            status=o["status"],
            items=o["items"],
            total_amount=o["total_amount"],
            order_date=o["order_date"],
        )
        for o in orders
    ]

    return CustomerContextResponse(
        customer_id=req.customer_id,
        name=profile["name"],
        tier=profile["tier"],
        open_tickets_count=profile["open_tickets_count"],
        recent_orders=order_schemas,
        last_interaction=datetime.datetime.utcnow() - datetime.timedelta(days=2),
    )


@app.post("/evaluate-response", response_model=EvaluateResponseResponse)
async def evaluate_response(
    req: EvaluateResponseRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_optional_current_user),
):
    """Run evaluation scores comparing drafted answers against context."""
    if req.agent_run_id and (
        current_user is None or current_user.role not in {"admin", "manager"}
    ):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Manager role is required to link evaluation feedback.",
        )
    results = await run_deeval_evaluation(
        query=req.query, context=req.context, response=req.response
    )
    if req.agent_run_id:
        await db.commit()
        await _record_evaluation_fail_open(
            db,
            agent_run_id=req.agent_run_id,
            metrics={
                "faithfulness": results.faithfulness_score,
                "context_precision": results.context_precision,
                "context_recall": results.context_recall,
                "hallucination_rate": results.hallucination_rate,
                "answer_relevance": results.answer_relevance,
                "overall_quality_score": results.overall_quality_score,
            },
            passed=results.passed_evaluation,
            external_ref=req.external_ref,
        )
    return results


# --- FEEDBACK PIPELINE APIS ---
@app.post(
    "/feedback/user",
    response_model=FeedbackEventResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_user_feedback(
    req: UserFeedbackRequest, db: AsyncSession = Depends(get_db)
):
    """采集用户评分，并关联对应 Agent Run 与 OpenTelemetry Trace。"""
    event = await feedback_service.record_user_feedback(
        db,
        agent_run_id=req.agent_run_id,
        feedback_token=req.feedback_token,
        rating=req.rating,
        comment=req.comment,
        idempotency_key=req.idempotency_key,
    )
    await db.commit()
    await db.refresh(event)
    return event


@app.get("/feedback/runs/{agent_run_id}", response_model=AgentRunResponse)
async def get_feedback_run(
    agent_run_id: str,
    current_user: User = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    """供主管按 Agent Run 查看 Trace、版本快照和全部反馈。"""
    return await feedback_service.get_agent_run(db, agent_run_id)


# --- HUMAN IN THE LOOP APPROVAL APIS ---
@app.get("/approvals/pending", response_model=list[ResponseApprovalResponse])
async def list_pending_approvals(
    current_user: User = Depends(require_agent), db: AsyncSession = Depends(get_db)
):
    """Secure endpoint: list all response drafts needing validation."""
    records = await human_it_loop_service.get_pending_approvals(db)

    # Map to schema
    output = []
    for r in records:
        output.append(
            ResponseApprovalResponse(
                id=r.id,
                ticket_id=r.ticket_id,
                status=r.status,
                final_response=r.drafted_response,
                latency_seconds=r.latency_seconds or 0.0,
                approved_at=r.created_at,
            )
        )
    return output


@app.post("/approvals/{approval_id}", response_model=ResponseApprovalResponse)
async def process_approval(
    approval_id: int,
    req: ResponseApprovalRequest,
    current_user: User = Depends(require_agent),
    db: AsyncSession = Depends(get_db),
):
    """Secure endpoint: approve, reject, or edit a response draft."""
    record = await human_it_loop_service.process_agent_approval(
        db=db, approval_id=approval_id, agent_id=current_user.id, req=req
    )

    return ResponseApprovalResponse(
        id=record.id,
        ticket_id=record.ticket_id,
        status=record.status,
        final_response=record.modified_response or record.drafted_response,
        latency_seconds=record.latency_seconds or 0.0,
        approved_at=datetime.datetime.utcnow(),
    )


# --- GENERAL TICKETING APIS ---
@app.post(
    "/tickets", response_model=TicketResponse, status_code=status.HTTP_201_CREATED
)
async def create_ticket(req: TicketCreate, db: AsyncSession = Depends(get_db)):
    ticket = Ticket(
        customer_id=req.customer_id,
        subject=req.subject,
        description=req.description,
        status="open",
        priority="medium",
    )
    db.add(ticket)
    await db.commit()
    await db.refresh(ticket)
    return ticket


@app.post("/tickets/{ticket_id}/close", response_model=TicketResponse)
async def close_ticket(ticket_id: int, db: AsyncSession = Depends(get_db)):
    ticket_res = await db.execute(select(Ticket).filter(Ticket.id == ticket_id))
    ticket = ticket_res.scalars().first()
    if not ticket:
        raise HTTPException(status_code=404, detail="Ticket not found")

    ticket_state_machine.transition(ticket, TicketAction.CLOSE)
    await db.commit()
    await db.refresh(ticket)
    return ticket


@app.get("/tickets", response_model=list[TicketResponse])
async def list_tickets(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Ticket))
    return result.scalars().all()
