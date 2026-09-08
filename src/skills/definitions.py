"""SupportGPT Skill Framework V1 的唯一能力清单。"""

from src.models.intents import IntentType
from src.skills.models import SkillDefinition
from src.skills.registry import SkillRegistry


SKILL_REGISTRY_VERSION = "v1"
COMMON_READ_TOOLS = frozenset(
    {"crm.get_customer_profile", "tickets.get_past_tickets"}
)
ORDER_READ_TOOL = "orders.get_order_history"
REFUND_ELIGIBILITY_TOOL = "orders.check_refund_eligibility"
REFUND_WRITE_TOOL = "orders.create_refund_request"
ALL_TOOL_NAMES = COMMON_READ_TOOLS | {
    ORDER_READ_TOOL,
    REFUND_ELIGIBILITY_TOOL,
    REFUND_WRITE_TOOL,
}


def _definition(
    *,
    name: str,
    description: str,
    intents: frozenset[IntentType],
    tools: frozenset[str],
    rag_categories: tuple[str, ...],
) -> SkillDefinition:
    """生成带明确 Tool Allowlist/Forbidden List 的 Skill。"""
    return SkillDefinition(
        name=name,
        version="v1",
        description=description,
        supported_intents=intents,
        allowed_tools=tools,
        forbidden_tools=ALL_TOOL_NAMES - tools,
        rag_categories=rag_categories,
        required_slots=("customer_id",),
    )


skill_registry = SkillRegistry(SKILL_REGISTRY_VERSION)
skill_registry.register(
    _definition(
        name="refund_support",
        description="处理退款、支付、发票与账务争议，写操作仍由 Tool Governance 审批。",
        intents=frozenset({IntentType.BILLING_DISPUTE}),
        tools=COMMON_READ_TOOLS
        | {ORDER_READ_TOOL, REFUND_ELIGIBILITY_TOOL, REFUND_WRITE_TOOL},
        rag_categories=("billing", "returns"),
    )
)
skill_registry.register(
    _definition(
        name="order_support",
        description="处理订单状态查询和取消请求。",
        intents=frozenset({IntentType.ORDER_STATUS, IntentType.ORDER_CANCELLATION}),
        tools=COMMON_READ_TOOLS | {ORDER_READ_TOOL},
        rag_categories=("shipping",),
    )
)
skill_registry.register(
    _definition(
        name="account_support",
        description="处理登录、锁定和凭据等已发生的账户异常。",
        intents=frozenset({IntentType.ACCOUNT_SUPPORT}),
        tools=COMMON_READ_TOOLS,
        rag_categories=("support", "general"),
    )
)
skill_registry.register(
    _definition(
        name="api_incident_triage",
        description="处理 API 报错、超时、宕机和服务降级问题。",
        intents=frozenset({IntentType.OUTAGE_REPORT}),
        tools=COMMON_READ_TOOLS,
        rag_categories=("technical",),
    )
)
skill_registry.register(
    _definition(
        name="warranty_support",
        description="处理设备保修、维修和换货申请。",
        intents=frozenset({IntentType.WARRANTY_CLAIM}),
        tools=COMMON_READ_TOOLS,
        rag_categories=("returns", "general"),
    )
)
skill_registry.register(
    _definition(
        name="general_support",
        description="处理一般信息咨询、使用说明和用户反馈。",
        intents=frozenset({IntentType.INFORMATION_REQUEST, IntentType.FEEDBACK}),
        tools=COMMON_READ_TOOLS,
        rag_categories=("general",),
    )
)
