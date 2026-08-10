import asyncio
import time
from dataclasses import dataclass
from typing import Any, Callable, Dict, List, Optional

from pydantic import BaseModel, Field, ValidationError

from src.tools.crm import crm_tool
from src.tools.order_mgmt import order_mgmt_tool
from src.tools.ticketing import ticketing_tool
from src.observability.tracing import get_tracer, observed_span, set_span_attributes
from src.observability.metrics import TOOL_CALLS_TOTAL, TOOL_CALL_DURATION_SECONDS


ROLE_RANK = {
    "agent": 1,
    "manager": 2,
    "admin": 3,
}

tracer = get_tracer(__name__)


class CustomerToolInput(BaseModel):
    """定义只需要客户标识的 Tool 输入参数。"""

    customer_id: str = Field(..., min_length=1)


class RefundEligibilityInput(BaseModel):
    """定义退款资格查询所需的客户和订单标识。"""

    customer_id: str = Field(..., min_length=1)
    order_id: str = Field(..., min_length=1)


@dataclass(frozen=True)
class ToolDefinition:
    """描述 Tool 的协议、权限、超时和执行入口。"""

    name: str
    description: str
    input_schema: type[BaseModel]
    output_schema: Dict[str, Any]
    min_role: str
    timeout_seconds: float
    mocked: bool
    handler: Callable[..., Any]


class ToolRegistry:
    """统一注册和治理 Agent 可调用的业务工具。

    每次调用执行 Schema、RBAC、超时控制并生成审计记录。
    """

    def __init__(self) -> None:
        self._tools: Dict[str, ToolDefinition] = {}
        self._audit_log: List[Dict[str, Any]] = []

    def register(self, definition: ToolDefinition) -> None:
        self._tools[definition.name] = definition

    def list_tools(self) -> List[Dict[str, Any]]:
        return [
            {
                "name": tool.name,
                "description": tool.description,
                "input_schema": tool.input_schema.model_json_schema(),
                "output_schema": tool.output_schema,
                "min_role": tool.min_role,
                "timeout_seconds": tool.timeout_seconds,
                "mocked": tool.mocked,
            }
            for tool in self._tools.values()
        ]

    def get_audit_log(self) -> List[Dict[str, Any]]:
        return list(self._audit_log)

    async def call_tool(
        self,
        name: str,
        payload: Dict[str, Any],
        role: str = "agent",
        ticket_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        with observed_span(
            tracer,
            "supportgpt.tool.call",
            {
                "tool.name": name,
                "tool.role": role,
                "ticket.id": ticket_id,
                "tool.payload_keys": sorted(payload.keys()),
            },
        ) as span:
            result = await self._call_tool_impl(name, payload, role, ticket_id)
            set_span_attributes(
                span,
                {
                    "tool.allowed": result.get("allowed"),
                    "tool.status": result.get("status"),
                    "tool.mocked": result.get("mocked"),
                    "tool.latency_ms": result.get("latency_ms"),
                    "tool.has_error": bool(result.get("error")),
                },
            )
            return result

    async def _call_tool_impl(
        self,
        name: str,
        payload: Dict[str, Any],
        role: str,
        ticket_id: Optional[int],
    ) -> Dict[str, Any]:
        started = time.time()
        definition = self._tools.get(name)
        if not definition:
            return self._record_call(
                name=name,
                role=role,
                ticket_id=ticket_id,
                allowed=False,
                status="not_found",
                started=started,
                mocked=False,
                error=f"Tool '{name}' is not registered.",
            )

        if not self._is_allowed(role, definition.min_role):
            return self._record_call(
                name=name,
                role=role,
                ticket_id=ticket_id,
                allowed=False,
                status="permission_denied",
                started=started,
                mocked=definition.mocked,
                error=f"Role '{role}' cannot call tool '{name}'. Required role: {definition.min_role}.",
            )

        try:
            args = definition.input_schema(**payload)
        except ValidationError as exc:
            return self._record_call(
                name=name,
                role=role,
                ticket_id=ticket_id,
                allowed=True,
                status="validation_error",
                started=started,
                mocked=definition.mocked,
                error=str(exc),
            )

        try:
            result = await asyncio.wait_for(
                asyncio.to_thread(definition.handler, **args.model_dump()),
                timeout=definition.timeout_seconds,
            )
            return self._record_call(
                name=name,
                role=role,
                ticket_id=ticket_id,
                allowed=True,
                status="success",
                started=started,
                mocked=definition.mocked,
                result=result,
            )
        except TimeoutError:
            return self._record_call(
                name=name,
                role=role,
                ticket_id=ticket_id,
                allowed=True,
                status="timeout",
                started=started,
                mocked=definition.mocked,
                error=f"Tool '{name}' timed out after {definition.timeout_seconds}s.",
            )
        except Exception as exc:
            return self._record_call(
                name=name,
                role=role,
                ticket_id=ticket_id,
                allowed=True,
                status="error",
                started=started,
                mocked=definition.mocked,
                error=str(exc),
            )

    def _is_allowed(self, role: str, min_role: str) -> bool:
        return ROLE_RANK.get(role, 0) >= ROLE_RANK.get(min_role, 999)

    def _record_call(
        self,
        name: str,
        role: str,
        ticket_id: Optional[int],
        allowed: bool,
        status: str,
        started: float,
        mocked: bool,
        result: Any = None,
        error: Optional[str] = None,
    ) -> Dict[str, Any]:
        record = {
            "tool_name": name,
            "role": role,
            "ticket_id": ticket_id,
            "allowed": allowed,
            "status": status,
            "latency_ms": round((time.time() - started) * 1000, 2),
            "mocked": mocked,
            "error": error,
        }
        self._audit_log.append(record)
        try:
            TOOL_CALLS_TOTAL.add(1, {"tool_name": name, "status": status})
            TOOL_CALL_DURATION_SECONDS.record(
                record["latency_ms"] / 1000.0, {"tool_name": name}
            )
        except Exception:
            pass
        return {**record, "result": result}


tool_registry = ToolRegistry()

tool_registry.register(
    ToolDefinition(
        name="crm.get_customer_profile",
        description="查询客户画像、客户等级和当前未关闭工单数量。",
        input_schema=CustomerToolInput,
        output_schema={
            "customer_id": "str",
            "name": "str",
            "tier": "str",
            "open_tickets_count": "int",
            "email": "str",
        },
        min_role="agent",
        timeout_seconds=1.0,
        mocked=True,
        handler=crm_tool.get_customer_profile,
    )
)

tool_registry.register(
    ToolDefinition(
        name="orders.get_order_history",
        description="查询客户近期订单、订单状态和付款金额。",
        input_schema=CustomerToolInput,
        output_schema={
            "orders": "list[dict]",
        },
        min_role="agent",
        timeout_seconds=1.0,
        mocked=True,
        handler=order_mgmt_tool.get_order_history,
    )
)

tool_registry.register(
    ToolDefinition(
        name="tickets.get_past_tickets",
        description="查询客户历史工单、处理状态和历史解决方案。",
        input_schema=CustomerToolInput,
        output_schema={
            "tickets": "list[dict]",
        },
        min_role="agent",
        timeout_seconds=1.0,
        mocked=True,
        handler=ticketing_tool.get_past_tickets,
    )
)


def mock_refund_eligibility_check(customer_id: str, order_id: str) -> Dict[str, Any]:
    orders = order_mgmt_tool.get_order_history(customer_id)
    matched_order = next(
        (order for order in orders if order.get("order_id") == order_id), None
    )
    if not matched_order:
        return {
            "customer_id": customer_id,
            "order_id": order_id,
            "eligible": False,
            "reason": "Order not found in mock OMS data.",
        }

    return {
        "customer_id": customer_id,
        "order_id": order_id,
        "eligible": matched_order.get("status") == "delivered",
        "reason": "Delivered orders are eligible for manager review in the mock policy.",
    }


tool_registry.register(
    ToolDefinition(
        name="orders.check_refund_eligibility",
        description="校验订单是否满足退款初筛条件；该工具代表高风险业务动作，要求 manager 及以上角色。",
        input_schema=RefundEligibilityInput,
        output_schema={
            "customer_id": "str",
            "order_id": "str",
            "eligible": "bool",
            "reason": "str",
        },
        min_role="manager",
        timeout_seconds=1.0,
        mocked=True,
        handler=mock_refund_eligibility_check,
    )
)
