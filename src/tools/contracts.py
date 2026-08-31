"""Tool Governance 的内部授权和执行契约。"""

from dataclasses import dataclass


@dataclass(frozen=True)
class ApprovedToolExecution:
    """绑定 Action、Tool 和参数摘要，防止审批后替换参数。"""

    action_id: str
    tool_name: str
    payload_hash: str
    approved_by_user_id: int
