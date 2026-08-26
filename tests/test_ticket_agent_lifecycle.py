import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.db_models import AgentRun, Ticket


def _public_workflow_output(state, *, approval_required: bool):
    """构造用户咨询接口所需的最小 Agent 输出。"""
    return {
        **state,
        "suggested_response": "这是可直接展示给用户的回复。",
        "sentiment": "neutral",
        "priority": "medium",
        "department": "general",
        "sla_hours": 24.0,
        "approval_required": approval_required,
        "escalation_recommended": approval_required,
        "qa_score": 0.92,
        "hallucination_detected": False,
        "workflow_path": ["ticket_analyzer", "resolver", "qa"],
        "tool_calls": [],
        "context_citations": [],
        "tokens_input": 80,
        "tokens_output": 30,
        "latency_seconds": 0.15,
    }


@pytest.mark.asyncio
async def test_internal_ticket_endpoints_require_staff_login(client: AsyncClient):
    create_response = await client.post(
        "/tickets",
        json={"customer_id": "cust_101", "subject": "内部工单", "description": "测试"},
    )
    list_response = await client.get("/tickets")
    detail_response = await client.get("/tickets/1/agent-result")

    assert create_response.status_code == 401
    assert list_response.status_code == 401
    assert detail_response.status_code == 401


@pytest.mark.asyncio
async def test_create_ticket_runs_agent_once_and_detail_only_reads_saved_result(
    client: AsyncClient,
    db_session: AsyncSession,
    agent_headers: dict[str, str],
    monkeypatch,
):
    workflow_calls = []

    async def fake_workflow(state):
        workflow_calls.append(state.copy())
        return {
            **state,
            "suggested_response": "已保存的 Agent 回复",
            "sentiment": "negative",
            "priority": "high",
            "department": "billing",
            "sla_hours": 4.0,
            "approval_required": True,
            "escalation_recommended": True,
            "qa_score": 0.88,
            "hallucination_detected": False,
            "workflow_path": ["ticket_analyzer", "retriever", "llm_generation"],
            "tool_calls": [],
            "context_citations": [
                {
                    "source": "refund_policy.md",
                    "text": "退款申请应在购买后 30 天内提交。",
                    "score": 0.95,
                    "version": state["kb_version"],
                }
            ],
            "tokens_input": 120,
            "tokens_output": 60,
            "latency_seconds": 0.25,
        }

    monkeypatch.setattr("src.main.run_agent_workflow", fake_workflow)
    create_response = await client.post(
        "/tickets",
        json={
            "customer_id": "cust_101",
            "subject": "退款申请",
            "description": "这笔费用需要退款。",
            "kb_version": "v2",
        },
        headers=agent_headers,
    )

    assert create_response.status_code == 201
    ticket_id = create_response.json()["id"]
    assert create_response.json()["status"] == "pending_approval"
    assert len(workflow_calls) == 1
    assert workflow_calls[0]["ticket_id"] == ticket_id
    assert workflow_calls[0]["kb_version"] == "v2"

    first_detail = await client.get(
        f"/tickets/{ticket_id}/agent-result", headers=agent_headers
    )
    second_detail = await client.get(
        f"/tickets/{ticket_id}/agent-result", headers=agent_headers
    )

    assert first_detail.status_code == 200
    assert second_detail.status_code == 200
    assert first_detail.json()["response"] == "已保存的 Agent 回复"
    assert first_detail.json()["kb_version"] == "v2"
    assert first_detail.json()["approval_required"] is True
    assert first_detail.json()["approval_id"] is not None
    assert first_detail.json()["citations"][0]["source"] == "refund_policy.md"
    assert len(workflow_calls) == 1

    ticket_count = await db_session.scalar(select(func.count()).select_from(Ticket))
    run_count = await db_session.scalar(select(func.count()).select_from(AgentRun))
    assert ticket_count == 1
    assert run_count == 1


@pytest.mark.asyncio
async def test_ticket_without_agent_run_returns_not_found(
    client: AsyncClient,
    db_session: AsyncSession,
    agent_headers: dict[str, str],
):
    ticket = Ticket(
        customer_id="legacy_customer",
        subject="历史工单",
        description="这张工单创建于自动处理功能之前。",
        status="open",
    )
    db_session.add(ticket)
    await db_session.commit()
    await db_session.refresh(ticket)

    response = await client.get(
        f"/tickets/{ticket.id}/agent-result", headers=agent_headers
    )

    assert response.status_code == 404
    assert "No persisted Agent result" in response.json()["detail"]


@pytest.mark.asyncio
async def test_public_support_request_returns_only_safe_answer(
    client: AsyncClient, monkeypatch
):
    async def fake_workflow(state):
        return _public_workflow_output(state, approval_required=False)

    monkeypatch.setattr("src.main.run_agent_workflow", fake_workflow)
    response = await client.post(
        "/support/requests",
        json={"customer_id": "cust_101", "message": "如何查看订单状态？"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == "answered"
    assert payload["response"] == "这是可直接展示给用户的回复。"
    assert set(payload) == {"ticket_id", "status", "response", "message", "created_at"}


@pytest.mark.asyncio
async def test_public_support_request_hides_draft_and_enters_staff_queue(
    client: AsyncClient, monkeypatch
):
    async def fake_workflow(state):
        return _public_workflow_output(state, approval_required=True)

    monkeypatch.setattr("src.main.run_agent_workflow", fake_workflow)
    response = await client.post(
        "/support/requests",
        json={"customer_id": "cust_101", "message": "请处理高风险退款。"},
    )

    assert response.status_code == 201
    payload = response.json()
    assert payload["status"] == "pending_human"
    assert payload["response"] is None

    register = await client.post(
        "/auth/register",
        json={"username": "queue_agent", "password": "queue-pass", "role": "agent"},
    )
    assert register.status_code == 201
    login = await client.post(
        "/auth/token",
        json={"username": "queue_agent", "password": "queue-pass"},
    )
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    queue = await client.get("/staff/review-queue", headers=headers)

    assert queue.status_code == 200
    assert [ticket["id"] for ticket in queue.json()] == [payload["ticket_id"]]
