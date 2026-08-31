"""为高风险 Tool Action 提供参数加密和防篡改摘要。"""

import base64
import hashlib
import hmac
import json
from typing import Any

from cryptography.fernet import Fernet, InvalidToken

from src.config import settings
from src.observability.sanitization import sanitize_value


class ToolPayloadSecurity:
    """加密 Action 参数，审计域只保留脱敏摘要与 HMAC。"""

    def __init__(self) -> None:
        configured = (settings.TOOL_ACTION_ENCRYPTION_KEY or "").strip()
        if configured:
            key = configured.encode("utf-8")
            try:
                Fernet(key)
            except (ValueError, TypeError) as exc:
                raise ValueError(
                    "TOOL_ACTION_ENCRYPTION_KEY must be a valid Fernet key."
                ) from exc
        else:
            key = base64.urlsafe_b64encode(
                hashlib.sha256(settings.JWT_SECRET.encode("utf-8")).digest()
            )
        self._key = key
        self._cipher = Fernet(key)

    def encrypt(self, payload: dict[str, Any]) -> str:
        return self._cipher.encrypt(self._canonical(payload)).decode("utf-8")

    def decrypt(self, encrypted: str) -> dict[str, Any]:
        """解密失败视为数据被篡改，不允许执行。"""
        try:
            raw = self._cipher.decrypt(encrypted.encode("utf-8"))
            value = json.loads(raw.decode("utf-8"))
        except (InvalidToken, ValueError, TypeError, json.JSONDecodeError) as exc:
            raise ValueError("Tool Action payload cannot be decrypted.") from exc
        if not isinstance(value, dict):
            raise ValueError("Tool Action payload must be an object.")
        return value

    def payload_hash(self, payload: dict[str, Any]) -> str:
        return hmac.new(self._key, self._canonical(payload), hashlib.sha256).hexdigest()

    @staticmethod
    def summary(payload: dict[str, Any]) -> dict[str, Any]:
        """业务标识和 PII 仅在摘要中保留过滤占位符。"""
        summary = sanitize_value(payload)
        for key in {"comment", "content", "description", "message", "notes", "reason"}:
            if key in summary:
                summary[key] = "[FILTERED]"
        return summary

    @staticmethod
    def result_summary(result: Any) -> Any:
        """结果摘要额外隔离可能携带客户文本的字段。"""
        if not isinstance(result, dict):
            return sanitize_value(result)
        return ToolPayloadSecurity.summary(result)

    @staticmethod
    def _canonical(payload: dict[str, Any]) -> bytes:
        return json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
            default=str,
        ).encode("utf-8")


tool_payload_security = ToolPayloadSecurity()
