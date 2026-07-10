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
    )

    assert result["allowed"] is True
    assert result["status"] == "success"
    assert result["result"]["eligible"] is True
