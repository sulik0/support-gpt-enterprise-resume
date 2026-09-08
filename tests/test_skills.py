"""Skill Framework V1 的注册、选择和 Tool 边界测试。"""

import pytest

from src.agents.graph import build_ticket_state, run_agent_workflow
from src.models.intents import IntentType
from src.skills import skill_registry
from src.skills.models import SkillDefinition
from src.skills.registry import SkillRegistry
from src.tools.registry import tool_registry


def test_all_intents_have_one_versioned_skill():
    """所有统一 Intent 都必须有唯一 Skill 归属。"""
    selected = {
        skill_registry.select({"intent": intent, "operator_role": "agent"})
        .definition.name
        for intent in IntentType
    }
    assert selected == {
        "refund_support",
        "order_support",
        "account_support",
        "api_incident_triage",
        "warranty_support",
        "general_support",
    }
    assert all(item["version"] == "v1" for item in skill_registry.list_skills())
    assert len(skill_registry.registry_id) == 64


def test_skill_selection_reports_missing_required_slot():
    selection = skill_registry.select(
        {"intent": IntentType.ORDER_STATUS, "operator_role": "agent"}
    )
    assert selection.definition.name == "order_support"
    assert selection.missing_slots == ("customer_id",)


def test_registry_rejects_duplicate_intent_and_unknown_tools():
    registry = SkillRegistry("v1")
    definition = SkillDefinition(
        name="test_support",
        version="v1",
        description="test",
        supported_intents=frozenset({IntentType.FEEDBACK}),
        allowed_tools=frozenset({"known.tool"}),
        forbidden_tools=frozenset(),
        rag_categories=("general",),
    )
    registry.register(definition)
    with pytest.raises(ValueError, match="already registered"):
        registry.register(definition)
    with pytest.raises(ValueError, match="unknown tools"):
        registry.validate_tool_catalog(set())


@pytest.mark.asyncio
async def test_skill_allowlist_denies_cross_domain_tool():
    result = await tool_registry.call_tool(
        "orders.get_order_history",
        {"customer_id": "cust_101"},
        intent=IntentType.INFORMATION_REQUEST,
        skill_name="general_support",
        skill_version="v1",
    )
    assert result["allowed"] is False
    assert result["status"] == "skill_denied"


@pytest.mark.asyncio
async def test_skill_version_mismatch_is_denied():
    result = await tool_registry.call_tool(
        "crm.get_customer_profile",
        {"customer_id": "cust_101"},
        intent=IntentType.INFORMATION_REQUEST,
        skill_name="general_support",
        skill_version="v0",
    )
    assert result["allowed"] is False
    assert result["status"] == "skill_denied"


@pytest.mark.asyncio
async def test_workflow_persists_skill_in_state(monkeypatch):
    """正常 Workflow 在业务上下文节点前完成 Skill 选择。"""
    state = build_ticket_state(
        {
            "ticket_id": 310,
            "customer_id": "cust_101",
            "subject": "Order status",
            "description": "Please check my order status",
        }
    )
    assert state["skill_name"] == "unselected"

    result = await run_agent_workflow(state)
    assert result["skill_name"] == "order_support"
    assert result["skill_version"] == "v1"
    assert result["selection_strategy"] == "intent_rule"
    assert "skill_selector" in result["workflow_path"]
    assert result["tool_context"]["tool_policy"]["skill_checked"] is True
