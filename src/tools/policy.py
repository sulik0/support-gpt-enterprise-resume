"""Tool Policy 快照、版本校验和确定性审计回放。"""

from typing import Any

from src.config import settings
from src.tools.payload_security import tool_payload_security


class ToolPolicyService:
    """将执行时策略冻结到 Action，避免历史审计受配置漂移影响。"""

    @staticmethod
    def snapshot(definition: Any) -> dict[str, Any]:
        return {
            "policy_version": settings.TOOL_POLICY_VERSION,
            "tool_name": definition.name,
            "tool_version": definition.version,
            "minimum_role": definition.min_role,
            "risk_level": definition.risk_level,
            "operation_type": definition.operation_type.value,
            "allowed_intents": (
                sorted(str(value) for value in definition.allowed_intents)
                if definition.allowed_intents is not None
                else None
            ),
            "requires_approval": True,
            "separation_of_duties": True,
            "business_idempotency": True,
            "transactional_outbox": True,
            "unknown_requires_reconciliation": True,
        }

    @staticmethod
    def digest(snapshot: dict[str, Any]) -> str:
        """复用治理密钥生成 HMAC，防止 Policy 快照与摘要同时被替换。"""
        return tool_payload_security.payload_hash(snapshot)

    def replay(self, action: Any) -> dict[str, Any]:
        """只读取历史快照重放策略检查，不调用 Tool 或外部系统。"""
        control = action.control
        if control is None:
            return {
                "passed": False,
                "policy_version": action.policy_version,
                "checks": {},
                "violations": ["missing_policy_snapshot"],
            }
        snapshot = dict(control.policy_snapshot or {})
        allowed_intents = snapshot.get("allowed_intents")
        approval_recorded = (
            action.status in {"proposed", "pending_approval"}
            or action.reviewed_by_user_id is not None
        )
        checks = {
            "policy_hash_valid": self.digest(snapshot) == control.policy_hash,
            "policy_version_matches": (
                snapshot.get("policy_version") == action.policy_version
            ),
            "tool_name_matches": snapshot.get("tool_name") == action.tool_name,
            "tool_version_matches": snapshot.get("tool_version") == action.tool_version,
            "intent_allowed": (
                allowed_intents is None or action.intent in allowed_intents
            ),
            "risk_level_matches": snapshot.get("risk_level") == action.risk_level,
            "operation_type_matches": (
                snapshot.get("operation_type") == action.operation_type
            ),
            "payload_hmac_valid": self._payload_hmac_valid(action),
            "approval_required": bool(snapshot.get("requires_approval")),
            "approval_recorded_when_required": (
                not snapshot.get("requires_approval") or approval_recorded
            ),
            "reviewer_role_authorized": (
                action.reviewed_by_user_id is None
                or action.reviewed_by_role in {"manager", "admin"}
            ),
            "separation_of_duties": (
                not snapshot.get("separation_of_duties")
                or action.reviewed_by_user_id is None
                or action.proposed_by_user_id != action.reviewed_by_user_id
            ),
            "idempotency_key_present": bool(control.idempotency_key),
        }
        violations = [name for name, passed in checks.items() if not passed]
        return {
            "passed": not violations,
            "policy_version": snapshot.get("policy_version"),
            "policy_hash": control.policy_hash,
            "checks": checks,
            "violations": violations,
        }

    @staticmethod
    def _payload_hmac_valid(action: Any) -> bool:
        try:
            payload = tool_payload_security.decrypt(action.payload_encrypted)
        except ValueError:
            return False
        return tool_payload_security.payload_hash(payload) == action.payload_hash


tool_policy_service = ToolPolicyService()
