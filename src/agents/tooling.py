import logging
import time
from typing import Any, Dict

from src.observability.metrics import AGENT_EXECUTION_DURATION_SECONDS
from src.tools.crm import crm_tool
from src.tools.order_mgmt import order_mgmt_tool
from src.tools.ticketing import ticketing_tool

logger = logging.getLogger("supportgpt.agents.tooling")


class ToolingAgent:
    """
    Collects structured business context from support tools.

    The current tool implementations are mock adapters. They intentionally mimic
    CRM, order-management, and ticketing systems so the Agent workflow can be
    demonstrated locally without private enterprise integrations.
    """

    async def enrich(self, state: Dict[str, Any]) -> Dict[str, Any]:
        start_time = time.time()
        customer_id = state.get("customer_id", "")
        department = state.get("department", "general")
        intent = state.get("intent", "general")

        if "Security threat" in "".join(state.get("errors", [])):
            return state

        logger.info(
            "Tooling node started for customer=%s department=%s intent=%s",
            customer_id,
            department,
            intent,
        )

        try:
            profile = crm_tool.get_customer_profile(customer_id)
            past_tickets = ticketing_tool.get_past_tickets(customer_id)

            should_fetch_orders = department in {"billing", "shipping"} or any(
                token in intent.lower()
                for token in ["billing", "refund", "order", "shipping", "payment", "invoice"]
            )
            orders = order_mgmt_tool.get_order_history(customer_id) if should_fetch_orders else []

            tool_context = {
                "customer_profile": {
                    "customer_id": profile.get("customer_id"),
                    "tier": profile.get("tier"),
                    "open_tickets_count": profile.get("open_tickets_count"),
                },
                "recent_orders": orders[:3],
                "past_tickets": past_tickets[:3],
                "mocked": True,
                "mock_note": "CRM, order, and ticketing tools are local mock adapters for resume/demo use.",
            }

            duration = time.time() - start_time
            AGENT_EXECUTION_DURATION_SECONDS.labels(agent_name="tooling_agent").observe(duration)

            return {
                **state,
                "tool_context": tool_context,
            }
        except Exception as exc:
            logger.error("Tooling agent failed: %s", exc)
            return {
                **state,
                "tool_context": {},
                "errors": state.get("errors", []) + [f"Tooling agent error: {str(exc)}"],
            }


tooling_agent = ToolingAgent()
