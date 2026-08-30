import pytest

from src.tools.registry import tool_registry


@pytest.mark.asyncio
async def test_tool_registry_allows_schema_valid_read_tool():
    result = await tool_registry.call_tool(
        "crm.get_customer_profile",
        {"customer_id": "cust_101"},
        role="agent",
        ticket_id=100,
    )

    assert result["allowed"] is True
    assert result["status"] == "success"
    assert result["mocked"] is True
    assert result["result"]["customer_id"] == "cust_101"


@pytest.mark.asyncio
async def test_tool_registry_denies_manager_tool_for_agent():
    result = await tool_registry.call_tool(
        "orders.check_refund_eligibility",
        {"customer_id": "cust_101", "order_id": "ORD-7001"},
        role="agent",
        ticket_id=101,
    )

    assert result["allowed"] is False
    assert result["status"] == "permission_denied"
    assert "Required role: manager" in result["error"]


@pytest.mark.asyncio
async def test_tool_registry_allows_manager_tool_for_manager():
    result = await tool_registry.call_tool(
        "orders.check_refund_eligibility",
        {"customer_id": "cust_101", "order_id": "ORD-7001"},
        role="manager",
        ticket_id=102,
        intent="billing_dispute",
        request_risk_level="high",
    )

    assert result["allowed"] is True
    assert result["status"] == "success"
    assert result["result"]["eligible"] is True


@pytest.mark.asyncio
async def test_tool_registry_denies_forbidden_or_wrong_intent_before_handler():
    forbidden = await tool_registry.call_tool(
        "orders.get_order_history",
        {"customer_id": "cust_101"},
        role="agent",
        ticket_id=103,
        intent="information_request",
        request_risk_level="low",
        forbidden_tools={"orders.get_order_history"},
    )
    wrong_intent = await tool_registry.call_tool(
        "orders.get_order_history",
        {"customer_id": "cust_101"},
        role="agent",
        ticket_id=104,
        intent="account_support",
        request_risk_level="low",
    )

    assert forbidden["allowed"] is False
    assert forbidden["status"] == "policy_denied"
    assert wrong_intent["allowed"] is False
    assert wrong_intent["status"] == "policy_denied"


@pytest.mark.asyncio
async def test_high_risk_tool_requires_matching_risk_even_for_manager():
    result = await tool_registry.call_tool(
        "orders.check_refund_eligibility",
        {"customer_id": "cust_101", "order_id": "ORD-7001"},
        role="manager",
        ticket_id=105,
        intent="billing_dispute",
        request_risk_level="low",
    )

    assert result["allowed"] is False
    assert result["status"] == "policy_denied"
