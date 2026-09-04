from collections import Counter

import pytest
from httpx import AsyncClient
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.types import Command
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.agents.analyzer import ticket_analyzer_agent
from src.agents.escalation import escalation_agent
from src.agents.graph import build_ticket_state, create_agent_graph
from src.agents.quality_assurance import quality_assurance_agent
from src.agents.resolver import resolution_agent
from src.agents.retriever import knowledge_retriever_agent
from src.agents.tooling import tooling_agent
from src.models.db_models import AgentExecution, AgentRun


def _install_deterministic_nodes(monkeypatch, calls: Counter) -> None:
    """使用确定性节点验证恢复过程不重跑已完成工作。"""

    async def analyze(state):
        calls["analyzer"] += 1
        return {
            **state,
            "sentiment": "negative",
            "priority": "high",
            "intent": "billing_dispute",
            "department": "billing",
            "analyzer_confidence": 0.99,
        }

    async def tooling(state):
        calls["tooling"] += 1
        return {**state, "tool_context": {}, "tool_calls": []}

    async def retrieve(state):
        calls["retriever"] += 1
        return {**state, "context_citations": []}

    async def resolve(state):
        calls["resolver"] += 1
        return {**state, "suggested_response": "需要人工审批的回复草稿。"}

    async def qa(state):
        calls["qa"] += 1
        return {
            **state,
            "qa_score": 0.95,
            "hallucination_detected": False,
        }

    async def escalate(state):
        calls["escalation"] += 1
        return {
            **state,
            "escalation_recommended": True,
            "escalation_reason": "High-risk refund requires approval.",
            "risk_requires_human": True,
        }

    monkeypatch.setattr(ticket_analyzer_agent, "analyze", analyze)
    monkeypatch.setattr(tooling_agent, "enrich", tooling)
    monkeypatch.setattr(knowledge_retriever_agent, "retrieve", retrieve)
    monkeypatch.setattr(resolution_agent, "resolve", resolve)
    monkeypatch.setattr(quality_assurance_agent, "verify", qa)
    monkeypatch.setattr(escalation_agent, "evaluate", escalate)


@pytest.mark.asyncio
async def test_sqlite_checkpoint_survives_restart_and_resumes_at_approval_gate(
    tmp_path, monkeypatch
):
    calls = Counter()
    _install_deterministic_nodes(monkeypatch, calls)
    checkpoint_path = tmp_path / "durable-checkpoints.sqlite"
    thread_id = "6ff7a925-8204-4b22-ae0f-e61f2239b7f2"
    config = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}
    state = build_ticket_state(
        {
            "ticket_id": 8001,
            "customer_id": "cust_101",
            "subject": "退款审批",
            "description": "请退款。",
            "checkpoint_thread_id": thread_id,
            "durable_execution_enabled": True,
        }
    )

    async with AsyncSqliteSaver.from_conn_string(str(checkpoint_path)) as saver:
        await saver.setup()
        graph = create_agent_graph(saver)
        first_output = await graph.ainvoke(state, config=config)
        snapshot = await graph.aget_state(config)

    assert first_output["suggested_response"] == "需要人工审批的回复草稿。"
    assert snapshot.next == ("approval_gate",)
    assert snapshot.tasks[0].interrupts[0].value["type"] == "response_approval"
    assert calls == {
        "analyzer": 1,
        "tooling": 1,
        "retriever": 1,
        "resolver": 1,
        "qa": 1,
        "escalation": 1,
    }

    # 重新打开 Saver 模拟应用进程重启。
    async with AsyncSqliteSaver.from_conn_string(str(checkpoint_path)) as saver:
        await saver.setup()
        restarted_graph = create_agent_graph(saver)
        resumed = await restarted_graph.ainvoke(
            Command(
                resume={
                    "status": "modified",
                    "final_response": "人工确认后的最终回复。",
                }
            ),
            config=config,
        )
        completed_snapshot = await restarted_graph.aget_state(config)

    assert resumed["suggested_response"] == "人工确认后的最终回复。"
    assert resumed["human_decision"] == "modified"
    assert resumed["workflow_path"][-1] == "human_approval"
    assert completed_snapshot.next == ()
    assert calls == {
        "analyzer": 1,
        "tooling": 1,
        "retriever": 1,
        "resolver": 1,
        "qa": 1,
        "escalation": 1,
    }


@pytest.mark.asyncio
async def test_approval_api_completes_persisted_durable_execution(
    client: AsyncClient,
    db_session: AsyncSession,
    agent_headers: dict[str, str],
):
    chat = await client.post(
        "/chat",
        json={
            "session_id": "durable-approval-session",
            "customer_id": "cust_101",
            "message": "I need a billing refund.",
            "kb_version": "v1",
        },
    )
    assert chat.status_code == 200
    approval_id = chat.json()["approval_id"]
    original_draft = chat.json()["response"]

    execution_result = await db_session.execute(select(AgentExecution))
    execution = execution_result.scalars().one()
    assert execution.status == "interrupted"
    assert execution.approval_id == approval_id
    assert execution.checkpoint_id

    approved = await client.post(
        f"/approvals/{approval_id}",
        headers=agent_headers,
        json={
            "approval_id": approval_id,
            "status": "modified",
            "modified_response": "已由人工审核并修改。",
        },
    )
    assert approved.status_code == 200
    assert approved.json()["workflow_execution_status"] == "completed"

    execution_result = await db_session.execute(
        select(AgentExecution).where(AgentExecution.id == execution.id)
    )
    execution = execution_result.scalars().one()
    assert execution.status == "completed"
    assert execution.resume_attempts == 1
    assert execution.lease_owner is None
    run_result = await db_session.execute(
        select(AgentRun).where(AgentRun.id == execution.agent_run_id)
    )
    agent_run = run_result.scalars().one()
    assert agent_run.output_text == original_draft
    assert agent_run.workflow_path[-1] == "human_approval"

    status_response = await client.get(
        f"/agent-executions/{execution.id}", headers=agent_headers
    )
    assert status_response.status_code == 200
    assert status_response.json()["status"] == "completed"
    assert "interrupt_payload" not in status_response.json()

    await client.post(
        "/auth/register",
        json={
            "username": "durable_manager",
            "password": "manager-pass",
            "role": "manager",
        },
    )
    login = await client.post(
        "/auth/token",
        json={"username": "durable_manager", "password": "manager-pass"},
    )
    manager_headers = {
        "Authorization": f"Bearer {login.json()['access_token']}"
    }
    repeated = await client.post(
        f"/agent-executions/{execution.id}/resume", headers=manager_headers
    )
    assert repeated.status_code == 200
    assert repeated.json()["status"] == "completed"
    assert repeated.json()["resume_attempts"] == 1
