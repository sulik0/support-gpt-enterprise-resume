from copy import deepcopy

import pytest

from src.config import settings
from src.promptops.defaults import default_payload
from src.tools.registry import tool_registry


async def _headers(client, username: str, role: str) -> dict[str, str]:
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


@pytest.mark.asyncio
async def test_resource_management_requires_admin(client):
    manager_headers = await _headers(client, "resource_manager", "manager")

    for path in (
        "/admin/resources/tools",
        "/admin/resources/prompts",
        "/admin/resources/rag-documents",
    ):
        unauthenticated = await client.get(path)
        forbidden = await client.get(path, headers=manager_headers)
        assert unauthenticated.status_code == 401
        assert forbidden.status_code == 403


@pytest.mark.asyncio
async def test_admin_can_persistently_disable_and_enable_tool(client):
    admin_headers = await _headers(client, "resource_admin", "admin")
    tool_name = "crm.get_customer_profile"

    listing = await client.get("/admin/resources/tools", headers=admin_headers)
    assert listing.status_code == 200
    assert any(item["name"] == tool_name for item in listing.json())

    disabled = await client.put(
        f"/admin/resources/tools/{tool_name}",
        headers=admin_headers,
        json={"enabled": False, "reason": "dependency maintenance"},
    )
    assert disabled.status_code == 200
    assert disabled.json()["enabled"] is False
    assert disabled.json()["disabled_reason"] == "dependency maintenance"
    assert tool_registry.is_enabled(tool_name) is False

    blocked = await tool_registry.call_tool(
        tool_name,
        {"customer_id": "cust_001"},
    )
    assert blocked["status"] == "disabled"
    assert blocked["allowed"] is False

    enabled = await client.put(
        f"/admin/resources/tools/{tool_name}",
        headers=admin_headers,
        json={"enabled": True, "reason": "maintenance complete"},
    )
    assert enabled.status_code == 200
    assert enabled.json()["enabled"] is True
    assert tool_registry.is_enabled(tool_name) is True


@pytest.mark.asyncio
async def test_admin_can_create_prompt_candidate_without_promoting(client, tmp_path, monkeypatch):
    monkeypatch.setattr(settings, "PROMPT_REGISTRY_DIR", str(tmp_path))
    admin_headers = await _headers(client, "prompt_admin", "admin")
    payload = deepcopy(default_payload())
    payload["version"] = "candidate-admin-v1"

    created = await client.post(
        "/admin/resources/prompts",
        headers=admin_headers,
        json=payload,
    )
    assert created.status_code == 201
    assert created.json()["version"] == "candidate-admin-v1"

    listing = await client.get("/admin/resources/prompts", headers=admin_headers)
    assert listing.status_code == 200
    body = listing.json()
    assert any(item["version"] == "candidate-admin-v1" for item in body["bundles"])
    assert body["state"]["environments"] == {}
    assert body["effective"]["production"]["version"] != "candidate-admin-v1"


@pytest.mark.asyncio
async def test_admin_manages_rag_document_and_vector_index(client):
    admin_headers = await _headers(client, "rag_admin", "admin")
    document = {
        "id": "admin-refund-policy",
        "title": "Admin Refund Policy",
        "content": "Refund eligibility requires a delivered order and manual review.",
        "version": "v-admin",
        "category": "refund",
        "metadata": {"owner": "support"},
    }

    created = await client.post(
        "/admin/resources/rag-documents",
        headers=admin_headers,
        json=document,
    )
    assert created.status_code == 201
    assert created.json()["id"] == document["id"]

    document["content"] = "Updated refund guidance with approval requirements."
    updated = await client.put(
        f"/admin/resources/rag-documents/{document['id']}",
        headers=admin_headers,
        json=document,
    )
    assert updated.status_code == 200
    assert updated.json()["content"].startswith("Updated")

    listing = await client.get(
        "/admin/resources/rag-documents", headers=admin_headers
    )
    assert listing.status_code == 200
    assert listing.json()[0]["metadata"] == {"owner": "support"}

    reindexed = await client.post(
        "/admin/resources/rag-documents/reindex", headers=admin_headers
    )
    assert reindexed.status_code == 200
    assert reindexed.json() == {"indexed_documents": 1}

    deleted = await client.delete(
        f"/admin/resources/rag-documents/{document['id']}",
        headers=admin_headers,
    )
    assert deleted.status_code == 204
    empty = await client.get("/admin/resources/rag-documents", headers=admin_headers)
    assert empty.json() == []
