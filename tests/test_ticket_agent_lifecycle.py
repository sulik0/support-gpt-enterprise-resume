import pytest
from httpx import AsyncClient
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.db_models import AgentRun, Ticket


@pytest.mark.asyncio
async def test_create_ticket_runs_agent_once_and_detail_only_reads_saved_result(
    client: AsyncClient,
    db_session: AsyncSession,
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
    )

    assert create_response.status_code == 201
    ticket_id = create_response.json()["id"]
    assert create_response.json()["status"] == "pending_approval"
    assert len(workflow_calls) == 1
    assert workflow_calls[0]["ticket_id"] == ticket_id
    assert workflow_calls[0]["kb_version"] == "v2"

    first_detail = await client.get(f"/tickets/{ticket_id}/agent-result")
    second_detail = await client.get(f"/tickets/{ticket_id}/agent-result")

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

    response = await client.get(f"/tickets/{ticket.id}/agent-result")

    assert response.status_code == 404
    assert "No persisted Agent result" in response.json()["detail"]
