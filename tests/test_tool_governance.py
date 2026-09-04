from dataclasses import replace

import pytest
from sqlalchemy import func, select

from src.config import settings
from src.models.db_models import (
    Ticket,
    ToolAction,
    ToolActionControl,
    ToolInvocationAudit,
)
from src.tools.outbox import OutboxStatus, ToolOutboxWorker, tool_outbox_worker
from src.tools.payload_security import tool_payload_security
from src.tools.refund_gateway import refund_gateway
from src.tools.registry import tool_registry


async def _register_and_login(client, username: str, role: str) -> dict[str, str]:
    register = await client.post(
        "/auth/register",
        json={"username": username, "password": "test-password", "role": role},
    )
    assert register.status_code == 201
    login = await client.post(
        "/auth/token",
        json={"username": username, "password": "test-password"},
    )
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def _ticket(db_session, customer_id: str = "cust_101") -> Ticket:
    ticket = Ticket(
        customer_id=customer_id,
        subject="Refund request",
        description="Please refund order ORD-7001.",
        status="open",
    )
    db_session.add(ticket)
    await db_session.commit()
    await db_session.refresh(ticket)
    return ticket


@pytest.mark.asyncio
async def test_high_risk_action_persists_approval_execution_and_audit(
    client, db_session, agent_headers, outbox_session_factory
):
    manager_headers = await _register_and_login(client, "governance_manager", "manager")
    ticket = await _ticket(db_session)
    payload = {
        "customer_id": "cust_101",
        "order_id": "ORD-7001",
        "reason": "Duplicate charge",
    }

    proposed = await client.post(
        "/tool-actions",
        headers=agent_headers,
        json={
            "ticket_id": ticket.id,
            "tool_name": "orders.create_refund_request",
            "payload": payload,
            "intent": "billing_dispute",
        },
    )
    assert proposed.status_code == 201, proposed.text
    proposed_body = proposed.json()
    assert proposed_body["status"] == "pending_approval"
    assert proposed_body["version"] == 2
    assert proposed_body["idempotency_key"].startswith("supportgpt:")
    assert len(proposed_body["policy_hash"]) == 64
    assert len(proposed_body["events"]) == 2
    assert proposed_body["payload_summary"]["customer_id"] == "[FILTERED]"
    assert proposed_body["payload_summary"]["order_id"] == "[FILTERED]"
    assert proposed_body["payload_summary"]["reason"] == "[FILTERED]"

    stored = await db_session.get(ToolAction, proposed_body["id"])
    assert stored is not None
    assert "cust_101" not in stored.payload_encrypted
    assert "ORD-7001" not in stored.payload_encrypted
    assert tool_payload_security.decrypt(stored.payload_encrypted) == payload

    approved = await client.post(
        f"/tool-actions/{stored.id}/decision",
        headers=manager_headers,
        json={
            "decision": "approved",
            "expected_version": 2,
            "comment": "Policy checked",
        },
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"
    assert approved.json()["version"] == 3

    executed = await client.post(
        f"/tool-actions/{stored.id}/execute",
        headers=manager_headers,
        json={"expected_version": 3},
    )
    assert executed.status_code == 200, executed.text
    assert executed.json()["status"] == "queued"
    assert executed.json()["version"] == 4
    assert await tool_outbox_worker.run_once(outbox_session_factory) == 1

    completed = await client.get(f"/tool-actions/{stored.id}", headers=manager_headers)
    executed_body = completed.json()
    assert executed_body["status"] == "succeeded"
    assert executed_body["version"] == 6
    assert len(executed_body["events"]) == 6
    assert all(event["request_id"] for event in executed_body["events"])
    assert executed_body["result_summary"]["status"] == "submitted"
    assert executed_body["result_summary"]["message"] == "[FILTERED]"

    audits = await client.get(
        "/tool-audits", headers=manager_headers, params={"action_id": stored.id}
    )
    assert audits.status_code == 200
    audit_body = audits.json()
    assert audit_body["total"] == 1
    assert audit_body["items"][0]["status"] == "success"
    assert audit_body["items"][0]["tool_action_id"] == stored.id
    assert audit_body["items"][0]["policy_version"] == "tool-policy-v2.2-test"
    assert "payload_hash" not in audit_body["items"][0]


@pytest.mark.asyncio
async def test_action_blocks_self_approval_stale_version_and_cross_customer(
    client, db_session
):
    manager_headers = await _register_and_login(client, "self_manager", "manager")
    ticket = await _ticket(db_session)
    request = {
        "ticket_id": ticket.id,
        "tool_name": "orders.create_refund_request",
        "payload": {
            "customer_id": "cust_101",
            "order_id": "ORD-7001",
            "reason": "Duplicate charge",
        },
        "intent": "billing_dispute",
    }
    proposed = await client.post("/tool-actions", headers=manager_headers, json=request)
    assert proposed.status_code == 201
    action_id = proposed.json()["id"]

    self_approval = await client.post(
        f"/tool-actions/{action_id}/decision",
        headers=manager_headers,
        json={"decision": "approved", "expected_version": 2},
    )
    assert self_approval.status_code == 409

    stale = await client.post(
        f"/tool-actions/{action_id}/decision",
        headers=manager_headers,
        json={"decision": "rejected", "expected_version": 1},
    )
    assert stale.status_code == 409

    request["payload"]["customer_id"] = "cust_999"
    cross_customer = await client.post(
        "/tool-actions", headers=manager_headers, json=request
    )
    assert cross_customer.status_code == 403


@pytest.mark.asyncio
async def test_pending_action_and_direct_registry_call_cannot_execute(
    client, db_session, agent_headers
):
    manager_headers = await _register_and_login(client, "execution_manager", "manager")
    ticket = await _ticket(db_session)
    proposed = await client.post(
        "/tool-actions",
        headers=agent_headers,
        json={
            "ticket_id": ticket.id,
            "tool_name": "orders.create_refund_request",
            "payload": {
                "customer_id": "cust_101",
                "order_id": "ORD-7001",
                "reason": "Duplicate charge",
            },
            "intent": "billing_dispute",
        },
    )
    action_id = proposed.json()["id"]
    premature = await client.post(
        f"/tool-actions/{action_id}/execute",
        headers=manager_headers,
        json={"expected_version": 2},
    )
    assert premature.status_code == 409

    direct = await tool_registry.call_tool(
        "orders.create_refund_request",
        {
            "customer_id": "cust_101",
            "order_id": "ORD-7001",
            "reason": "Duplicate charge",
        },
        role="manager",
        ticket_id=ticket.id,
        intent="billing_dispute",
        request_risk_level="high",
    )
    assert direct["allowed"] is False
    assert direct["status"] == "approval_required"


@pytest.mark.asyncio
async def test_agent_cannot_list_governance_records(client, db_session, agent_headers):
    assert (await client.get("/tool-actions", headers=agent_headers)).status_code == 403
    assert (await client.get("/tool-audits", headers=agent_headers)).status_code == 403
    assert (await client.get("/tool-outbox", headers=agent_headers)).status_code == 403

    count = await db_session.execute(select(func.count(ToolInvocationAudit.id)))
    assert count.scalar_one() == 0


@pytest.mark.asyncio
async def test_ticket_workflow_batch_persists_parallel_tool_audits(
    client, db_session, agent_headers
):
    response = await client.post(
        "/tickets",
        headers=agent_headers,
        json={
            "customer_id": "cust_101",
            "subject": "Order status",
            "description": "Where is order ORD-7001?",
            "kb_version": "v1",
        },
    )
    assert response.status_code == 201, response.text

    records = list(
        (
            await db_session.execute(
                select(ToolInvocationAudit).order_by(ToolInvocationAudit.tool_name)
            )
        )
        .scalars()
        .all()
    )
    assert {record.tool_name for record in records} == {
        "crm.get_customer_profile",
        "orders.get_order_history",
        "tickets.get_past_tickets",
    }
    assert all(record.request_id != "unbound" for record in records)
    assert all(record.payload_keys == ["customer_id"] for record in records)


@pytest.mark.asyncio
async def test_uncertain_write_failure_enters_unknown_without_retry(
    client, db_session, agent_headers, monkeypatch, outbox_session_factory
):
    manager_headers = await _register_and_login(client, "unknown_manager", "manager")
    ticket = await _ticket(db_session)
    proposed = await client.post(
        "/tool-actions",
        headers=agent_headers,
        json={
            "ticket_id": ticket.id,
            "tool_name": "orders.create_refund_request",
            "payload": {
                "customer_id": "cust_101",
                "order_id": "ORD-7001",
                "reason": "Duplicate charge",
            },
            "intent": "billing_dispute",
        },
    )
    action_id = proposed.json()["id"]
    approved = await client.post(
        f"/tool-actions/{action_id}/decision",
        headers=manager_headers,
        json={"decision": "approved", "expected_version": 2},
    )
    assert approved.status_code == 200

    calls = 0

    def uncertain_handler(**kwargs):
        nonlocal calls
        calls += 1
        # 模拟 OMS 已落账，但客户端在收到响应前超时。
        refund_gateway.create_refund_request(**kwargs)
        raise TimeoutError("mock downstream timeout")

    definition = tool_registry.get_definition("orders.create_refund_request")
    assert definition is not None
    monkeypatch.setitem(
        tool_registry._tools,
        definition.name,
        replace(definition, handler=uncertain_handler),
    )
    executed = await client.post(
        f"/tool-actions/{action_id}/execute",
        headers=manager_headers,
        json={"expected_version": 3},
    )

    assert executed.status_code == 200, executed.text
    assert executed.json()["status"] == "queued"
    assert await tool_outbox_worker.run_once(outbox_session_factory) == 1
    unknown = await client.get(f"/tool-actions/{action_id}", headers=manager_headers)
    assert unknown.json()["status"] == "unknown"
    assert unknown.json()["error_type"] == "timeout"
    assert calls == 1
    # 对账只查询相同幂等键的权威结果，不会再次调用退款写 Handler。
    assert await tool_outbox_worker.run_once(outbox_session_factory) == 1
    reconciled = await client.get(f"/tool-actions/{action_id}", headers=manager_headers)
    assert reconciled.json()["status"] == "succeeded"
    assert calls == 1
    audit = (
        await db_session.execute(
            select(ToolInvocationAudit).where(
                ToolInvocationAudit.tool_action_id == action_id
            )
        )
    ).scalar_one()
    assert audit.status == "timeout"
    assert audit.attempts == 1


@pytest.mark.asyncio
async def test_reconciliation_exhaustion_enters_dlq_and_requires_manual_review(
    client,
    db_session,
    agent_headers,
    monkeypatch,
    outbox_session_factory,
):
    manager_headers = await _register_and_login(client, "dlq_manager", "manager")
    ticket = await _ticket(db_session)
    proposed = await client.post(
        "/tool-actions",
        headers=agent_headers,
        json={
            "ticket_id": ticket.id,
            "tool_name": "orders.create_refund_request",
            "payload": {
                "customer_id": "cust_101",
                "order_id": "ORD-7001",
                "reason": "Duplicate charge",
            },
            "intent": "billing_dispute",
        },
    )
    action_id = proposed.json()["id"]
    await client.post(
        f"/tool-actions/{action_id}/decision",
        headers=manager_headers,
        json={"decision": "approved", "expected_version": 2},
    )
    calls = 0

    def timeout_without_side_effect(**_kwargs):
        nonlocal calls
        calls += 1
        raise TimeoutError("OMS did not persist this request")

    definition = tool_registry.get_definition("orders.create_refund_request")
    assert definition is not None
    monkeypatch.setitem(
        tool_registry._tools,
        definition.name,
        replace(definition, handler=timeout_without_side_effect),
    )
    monkeypatch.setattr(settings, "TOOL_OUTBOX_MAX_ATTEMPTS", 2)
    monkeypatch.setattr(settings, "TOOL_OUTBOX_RETRY_BASE_SECONDS", 0.0)
    monkeypatch.setattr(settings, "TOOL_OUTBOX_RETRY_MAX_SECONDS", 0.0)
    await client.post(
        f"/tool-actions/{action_id}/execute",
        headers=manager_headers,
        json={"expected_version": 3},
    )

    await tool_outbox_worker.run_once(outbox_session_factory)
    await tool_outbox_worker.run_once(outbox_session_factory)
    await tool_outbox_worker.run_once(outbox_session_factory)

    dlq = await client.get(
        "/tool-outbox",
        headers=manager_headers,
        params={"status": OutboxStatus.DEAD_LETTER, "action_id": action_id},
    )
    assert dlq.status_code == 200
    assert dlq.json()["total"] == 1
    assert dlq.json()["items"][0]["event_type"] == "reconcile"
    action = await client.get(f"/tool-actions/{action_id}", headers=manager_headers)
    assert action.json()["status"] == "unknown"
    assert action.json()["events"][-1]["action"] == "dead_letter"
    assert calls == 1
    replayed = await client.post(
        f"/tool-outbox/{dlq.json()['items'][0]['id']}/retry",
        headers=manager_headers,
    )
    assert replayed.status_code == 200
    assert replayed.json()["status"] == OutboxStatus.RETRY
    retried_action = await client.get(
        f"/tool-actions/{action_id}", headers=manager_headers
    )
    assert retried_action.json()["events"][-1]["action"] == "retry_dead_letter"


@pytest.mark.asyncio
async def test_successful_action_can_be_compensated_asynchronously(
    client, db_session, agent_headers, outbox_session_factory
):
    manager_headers = await _register_and_login(
        client, "compensation_manager", "manager"
    )
    ticket = await _ticket(db_session)
    proposed = await client.post(
        "/tool-actions",
        headers=agent_headers,
        json={
            "ticket_id": ticket.id,
            "tool_name": "orders.create_refund_request",
            "payload": {
                "customer_id": "cust_101",
                "order_id": "ORD-7001",
                "reason": "Duplicate charge",
            },
            "intent": "billing_dispute",
        },
    )
    action_id = proposed.json()["id"]
    await client.post(
        f"/tool-actions/{action_id}/decision",
        headers=manager_headers,
        json={"decision": "approved", "expected_version": 2},
    )
    await client.post(
        f"/tool-actions/{action_id}/execute",
        headers=manager_headers,
        json={"expected_version": 3},
    )
    await tool_outbox_worker.run_once(outbox_session_factory)

    requested = await client.post(
        f"/tool-actions/{action_id}/compensate",
        headers=manager_headers,
        json={"expected_version": 6, "reason": "Order dispute was withdrawn"},
    )
    assert requested.status_code == 200, requested.text
    assert requested.json()["status"] == "compensation_pending"
    await tool_outbox_worker.run_once(outbox_session_factory)
    compensated = await client.get(
        f"/tool-actions/{action_id}", headers=manager_headers
    )
    assert compensated.json()["status"] == "compensated"
    assert compensated.json()["version"] == 9


@pytest.mark.asyncio
async def test_policy_snapshot_replay_detects_tampering(
    client, db_session, agent_headers
):
    manager_headers = await _register_and_login(client, "replay_manager", "manager")
    ticket = await _ticket(db_session)
    proposed = await client.post(
        "/tool-actions",
        headers=agent_headers,
        json={
            "ticket_id": ticket.id,
            "tool_name": "orders.create_refund_request",
            "payload": {
                "customer_id": "cust_101",
                "order_id": "ORD-7001",
                "reason": "Duplicate charge",
            },
            "intent": "billing_dispute",
        },
    )
    action_id = proposed.json()["id"]
    replay = await client.get(
        f"/tool-actions/{action_id}/policy-replay", headers=manager_headers
    )
    assert replay.status_code == 200
    assert replay.json()["passed"] is True

    control = await db_session.get(ToolActionControl, action_id)
    control.policy_hash = "0" * 64
    await db_session.commit()
    tampered = await client.get(
        f"/tool-actions/{action_id}/policy-replay", headers=manager_headers
    )
    assert tampered.json()["passed"] is False
    assert "policy_hash_valid" in tampered.json()["violations"]


@pytest.mark.asyncio
async def test_outbox_lease_allows_only_one_worker_to_claim_event(
    client, db_session, agent_headers, outbox_session_factory
):
    manager_headers = await _register_and_login(client, "lease_manager", "manager")
    ticket = await _ticket(db_session)
    proposed = await client.post(
        "/tool-actions",
        headers=agent_headers,
        json={
            "ticket_id": ticket.id,
            "tool_name": "orders.create_refund_request",
            "payload": {
                "customer_id": "cust_101",
                "order_id": "ORD-7001",
                "reason": "Duplicate charge",
            },
            "intent": "billing_dispute",
        },
    )
    action_id = proposed.json()["id"]
    await client.post(
        f"/tool-actions/{action_id}/decision",
        headers=manager_headers,
        json={"decision": "approved", "expected_version": 2},
    )
    await client.post(
        f"/tool-actions/{action_id}/execute",
        headers=manager_headers,
        json={"expected_version": 3},
    )
    worker_a = ToolOutboxWorker()
    worker_b = ToolOutboxWorker()

    claimed_a = await worker_a._claim_batch(outbox_session_factory)
    claimed_b = await worker_b._claim_batch(outbox_session_factory)

    assert len(claimed_a) == 1
    assert claimed_b == []
    await worker_a._process_one(outbox_session_factory, claimed_a[0])
    completed = await client.get(f"/tool-actions/{action_id}", headers=manager_headers)
    assert completed.json()["status"] == "succeeded"


def test_tool_payload_integrity_rejects_ciphertext_tampering():
    encrypted = tool_payload_security.encrypt({"customer_id": "cust_101"})
    tampered = encrypted[:-2] + ("AA" if encrypted[-2:] != "AA" else "BB")

    with pytest.raises(ValueError):
        tool_payload_security.decrypt(tampered)


def test_mock_oms_returns_same_result_for_same_business_idempotency_key():
    payload = {
        "customer_id": "cust_101",
        "order_id": "ORD-7001",
        "reason": "Duplicate charge",
        "idempotency_key": "refund-action-idempotency-001",
    }

    first = refund_gateway.create_refund_request(**payload)
    second = refund_gateway.create_refund_request(**payload)

    assert second == first
    assert (
        refund_gateway.reconcile(idempotency_key=payload["idempotency_key"])["result"]
        == first
    )
