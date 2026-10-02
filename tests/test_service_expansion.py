"""验证新增业务工具真实进入上下文，同时遵守原有权限边界。"""

import pytest

from src.agents.tooling import tooling_agent
from src.agents.resolver import ResolutionAgent
from src.rag.demo_documents import DEMO_DOCUMENTS
from src.rag.vector_store import vector_store
from src.tools.registry import tool_registry
from src.tools.service_queries import service_query_adapter
from src.rag.kb_versioning import kb_versioning_service


@pytest.mark.parametrize("intent,tool", [
    ("order_status", "shipping.get_shipments"),
    ("order_cancellation", "shipping.get_shipments"),
    ("billing_dispute", "billing.get_payment_invoices"),
    ("warranty_claim", "warranty.get_entitlements"),
    ("outage_report", "services.get_status"),
])
@pytest.mark.asyncio
async def test_service_tool_routing_and_resolver_context(intent, tool):
    result = await tooling_agent.enrich({
        "customer_id": "cust_103", "intent": intent, "operator_role": "agent",
        "risk_level": "low", "errors": [],
    })
    call = next(item for item in result["tool_calls"] if item["tool_name"] == tool)
    assert call["status"] == "success"
    assert result["tool_context"]["service_query"]["data"]["mocked"] is True
    assert tool in ResolutionAgent._compact_tool_context(result["tool_context"])
    assert "orders.create_refund_request" not in {item["tool_name"] for item in result["tool_calls"]}
    if intent in {"warranty_claim", "outage_report"}:
        assert result["tool_context"]["recent_orders"] == []


@pytest.mark.asyncio
async def test_queries_respect_skill_policy_and_runtime_switch():
    wrong = await tool_registry.call_tool(
        "billing.get_payment_invoices", {"customer_id": "cust_101"},
        intent="information_request", skill_name="general_support", skill_version="v1.1",
    )
    assert wrong["allowed"] is False
    tool_registry.set_enabled("shipping.get_shipments", False)
    result = await tooling_agent.enrich({"customer_id": "cust_101", "intent": "order_status"})
    assert result["tool_context"]["service_query"]["data"] is None
    assert result["tool_context"]["service_query"]["status"] != "success"


def test_customer_isolation_and_defensive_copy():
    for query in (service_query_adapter.get_shipments, service_query_adapter.get_warranties, service_query_adapter.get_billing, service_query_adapter.get_service_status):
        unknown = query("unknown_customer")
        assert unknown["status"] == "not_found"
        assert unknown["records"] == []
    result = service_query_adapter.get_shipments("cust_102")
    result["records"][0]["status"] = "tampered"
    assert service_query_adapter.get_shipments("cust_102")["records"][0]["status"] == "in_transit"


@pytest.mark.asyncio
async def test_explicit_order_cannot_use_another_customers_record():
    result = await tooling_agent.enrich({
        "customer_id": "cust_101", "intent": "order_status",
        "memory_active_entities": {"order_id": "ORD-8002"},
    })
    data = result["tool_context"]["service_query"]["data"]
    assert data["records"] == []
    assert data["status"] == "not_found"


@pytest.mark.asyncio
async def test_chinese_policy_lexical_recall_and_version_filter():
    for doc in DEMO_DOCUMENTS:
        await vector_store.add_document_chunks(doc["doc_id"], [doc["content"]], {"title": doc["title"], "category": doc["category"]}, doc["version"])
    candidates = vector_store._lexical_candidates("显示签收但没有收到", {"$and": [{"version": "v1"}, {"category": "shipping"}]}, 3)
    assert candidates
    assert "签收" in candidates[0]["document"]
    results = await vector_store.query_kb("显示签收但没有收到", version="v1", category_filter="shipping", top_k=3)
    assert any("签收" in item.text for item in results)
    assert await vector_store.query_kb("签收", version="v2", top_k=3) == []


@pytest.mark.asyncio
async def test_incremental_seed_preserves_admin_content(db_session, monkeypatch):
    from scripts import seed_kb

    async def no_init():
        pass

    monkeypatch.setattr(seed_kb, "init_db", no_init)
    monkeypatch.setattr(seed_kb, "AsyncSessionLocal", lambda: db_session)
    doc = DEMO_DOCUMENTS[0]
    await kb_versioning_service.register_document(
        db_session, doc["doc_id"], doc["title"], "管理员维护的退款说明", doc["category"], "v1",
    )
    await seed_kb.seed(only_missing=True)
    documents = await kb_versioning_service.list_documents(db_session)
    assert len(documents) == 16
    saved = await kb_versioning_service.get_document(db_session, doc["doc_id"])
    assert saved.content == "管理员维护的退款说明"
    await seed_kb.seed(only_missing=True)
    assert len(await kb_versioning_service.list_documents(db_session)) == 16
