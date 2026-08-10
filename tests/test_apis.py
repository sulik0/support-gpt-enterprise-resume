import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_general_endpoints(client: AsyncClient):
    # Health check
    h_res = await client.get("/health")
    assert h_res.status_code == 200
    assert h_res.json()["status"] == "healthy"


@pytest.mark.asyncio
async def test_copilot_service_routes(client: AsyncClient):
    # 1. Customer profile context lookup
    ctx_res = await client.post("/customer-context", json={"customer_id": "cust_101"})
    assert ctx_res.status_code == 200
    assert ctx_res.json()["name"] == "Jane Doe"
    assert ctx_res.json()["tier"] == "VIP"

    # 2. Chat workflow activation
    chat_payload = {
        "session_id": "sess_test",
        "customer_id": "cust_101",
        "message": "I want a refund for my charge.",
        "kb_version": "v1",
    }
    chat_res = await client.post("/chat", json=chat_payload)
    assert chat_res.status_code == 200
    data = chat_res.json()
    assert data["session_id"] == "sess_test"
    assert data["sentiment"] == "negative"
    assert data["priority"] == "high"
    assert "response" in data
    # High-priority / billing triggers Human-In-The-Loop approval requirement
    assert data["approval_required"] is True
    assert data["approval_id"] is not None

    # 3. Running offline metrics evaluations
    eval_payload = {
        "query": "policy refund",
        "context": [
            "Corporate policy states refunds must be requested within 30 days."
        ],
        "response": "Corporate policy states refunds must be requested within 30 days.",
    }
    eval_res = await client.post("/evaluate-response", json=eval_payload)
    assert eval_res.status_code == 200
    eval_data = eval_res.json()
    assert eval_data["passed_evaluation"] is True
    assert eval_data["faithfulness_score"] == 1.0


@pytest.mark.asyncio
async def test_human_in_loop_approvals(client: AsyncClient):
    # 1. Create agent credentials
    reg_res = await client.post(
        "/auth/register",
        json={"username": "agent_larry", "password": "larrypassword", "role": "agent"},
    )
    assert reg_res.status_code == 201

    login_res = await client.post(
        "/auth/token", json={"username": "agent_larry", "password": "larrypassword"}
    )
    token = login_res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # 2. Add an issue ticket which triggers a pending approval
    chat_payload = {
        "session_id": "sess_larry",
        "customer_id": "cust_101",
        "message": "I need a billing refund.",
        "kb_version": "v1",
    }
    chat_res = await client.post("/chat", json=chat_payload)
    approval_id = chat_res.json()["approval_id"]

    # 3. Retrieve pending approvals list
    list_res = await client.get("/approvals/pending", headers=headers)
    assert list_res.status_code == 200
    assert len(list_res.json()) > 0
    assert any(item["id"] == approval_id for item in list_res.json())

    # 4. Approve AI suggestion
    process_payload = {
        "approval_id": approval_id,
        "modified_response": "Fully approved billing refund.",
        "status": "approved",
    }
    appr_res = await client.post(
        f"/approvals/{approval_id}", json=process_payload, headers=headers
    )
    assert appr_res.status_code == 200
    assert appr_res.json()["status"] == "approved"
    assert appr_res.json()["final_response"] == "Fully approved billing refund."
