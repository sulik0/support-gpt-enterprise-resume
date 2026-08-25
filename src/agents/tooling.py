import asyncio
import json
import logging
import time
from typing import Any, Dict

from src.guardrails.prompt_injection import analyze_prompt_injection
from src.guardrails.qwen3_guard import merge_qwen3_guard_result, qwen3_guard
from src.guardrails.security_policy import build_security_block
from src.observability.metrics import AGENT_EXECUTION_DURATION_SECONDS
from src.observability.sanitization import sanitize_value
from src.risk.engine import risk_engine
from src.tools.registry import tool_registry

logger = logging.getLogger("supportgpt.agents.tooling")


class ToolingAgent:
    """负责调用受 ToolRegistry 管理的工具补全业务上下文。

    当前 CRM、订单和工单工具均为本地 Mock Adapter。
    """

    async def enrich(self, state: Dict[str, Any]) -> Dict[str, Any]:
        start_time = time.time()
        customer_id = state.get("customer_id", "")
        ticket_id = state.get("ticket_id")
        operator_role = state.get("operator_role", "agent")
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
            should_fetch_orders = department in {"billing", "shipping"} or any(
                token in intent.lower()
                for token in [
                    "billing",
                    "refund",
                    "order",
                    "shipping",
                    "payment",
                    "invoice",
                ]
            )
            pending_calls = [
                tool_registry.call_tool(
                    "crm.get_customer_profile",
                    {"customer_id": customer_id},
                    role=operator_role,
                    ticket_id=ticket_id,
                ),
                tool_registry.call_tool(
                    "tickets.get_past_tickets",
                    {"customer_id": customer_id},
                    role=operator_role,
                    ticket_id=ticket_id,
                ),
            ]
            if should_fetch_orders:
                pending_calls.append(
                    tool_registry.call_tool(
                        "orders.get_order_history",
                        {"customer_id": customer_id},
                        role=operator_role,
                        ticket_id=ticket_id,
                    )
                )
            tool_calls = list(await asyncio.gather(*pending_calls))
            profile_call, ticket_call = tool_calls[:2]
            order_call = tool_calls[2] if len(tool_calls) > 2 else None

            profile = profile_call.get("result") or {}
            past_tickets = ticket_call.get("result") or []
            orders = order_call.get("result") if order_call else []

            public_tool_calls = [
                {key: value for key, value in call.items() if key != "result"}
                for call in tool_calls
            ]

            # 工具返回属于不可信外部数据，入上下文前扫描间接注入。
            tool_payload = json.dumps(
                [call.get("result") for call in tool_calls],
                ensure_ascii=False,
                default=str,
            )
            injection = analyze_prompt_injection(tool_payload, source="tool_result")
            if injection.detected:
                logger.warning(
                    "Indirect prompt injection detected in Tool result",
                    extra={
                        "ticket_id": ticket_id,
                        "risk_score": injection.risk_score,
                        "security_source": injection.source,
                    },
                )
                blocked = build_security_block(
                    state,
                    threat_type="Indirect prompt injection",
                    source=injection.source,
                    risk_score=injection.risk_score,
                    findings=[*injection.layers, *injection.signals],
                )
                return {**blocked, "tool_calls": public_tool_calls}

            semantic_payload = json.dumps(
                sanitize_value([call.get("result") for call in tool_calls]),
                ensure_ascii=False,
                default=str,
            )
            semantic_result = await qwen3_guard.classify(
                semantic_payload, source="tool_result"
            )
            guarded_state = merge_qwen3_guard_result(state, semantic_result)
            assessment = risk_engine.assess(guarded_state, stage="input")
            guarded_state = {**guarded_state, **assessment.state_updates()}
            if semantic_result.block_recommended:
                blocked = build_security_block(
                    guarded_state,
                    threat_type="Qwen3Guard semantic safety violation",
                    source=semantic_result.source,
                    risk_score=semantic_result.policy_score,
                    findings=[
                        f"semantic_severity:{semantic_result.severity}",
                        *(
                            f"semantic_category:{item}"
                            for item in semantic_result.categories
                        ),
                    ],
                )
                return {**blocked, "tool_calls": public_tool_calls}
            if semantic_result.degraded:
                return {
                    **guarded_state,
                    "tool_context": {},
                    "tool_calls": public_tool_calls,
                    "errors": list(guarded_state.get("errors", []))
                    + ["Semantic guard unavailable; Tool context isolated."],
                }

            tool_context = {
                "customer_profile": {
                    "customer_id": profile.get("customer_id"),
                    "tier": profile.get("tier"),
                    "open_tickets_count": profile.get("open_tickets_count"),
                },
                "recent_orders": orders[:3],
                "past_tickets": past_tickets[:3],
                "mocked": True,
                "tool_policy": {
                    "operator_role": operator_role,
                    "schema_validated": True,
                    "permission_checked": True,
                    "audit_enabled": True,
                },
                "mock_note": "CRM, order, and ticketing tools are local mock adapters behind the tool registry.",
            }

            duration = time.time() - start_time
            AGENT_EXECUTION_DURATION_SECONDS.record(
                duration, {"agent_name": "tooling_agent"}
            )

            return {
                **guarded_state,
                "tool_context": tool_context,
                "tool_calls": public_tool_calls,
            }
        except Exception as exc:
            logger.error("Tooling agent failed: %s", exc)
            return {
                **state,
                "tool_context": {},
                "tool_calls": [],
                "errors": state.get("errors", [])
                + [f"Tooling agent error: {str(exc)}"],
            }


tooling_agent = ToolingAgent()
