import json
import hashlib
import logging
from typing import Any, Dict, List, Optional

from src.config import settings

logger = logging.getLogger("supportgpt.memory.redis")


class RedisConversationMemory:
    """提供基于 Redis 的短期会话缓存。

    Cache 携带 SQL revision，过期或落后时由上层回退数据库。
    """

    def __init__(self):
        self._client = None

    async def _get_client(self):
        if not settings.REDIS_URL:
            return None
        if self._client is None:
            try:
                import redis.asyncio as redis

                self._client = redis.from_url(
                    settings.REDIS_URL,
                    encoding="utf-8",
                    decode_responses=True,
                )
            except Exception as exc:
                logger.warning("Redis memory unavailable: %s", exc)
                self._client = None
        return self._client

    def _key(self, session_id: str, customer_id: str) -> str:
        # 不把客户和会话原始标识写入 Redis Key。
        digest = hashlib.sha256(
            f"{customer_id}:{session_id}".encode("utf-8")
        ).hexdigest()
        return f"supportgpt:memory:v1:{digest}"

    async def load_messages(
        self, session_id: str, customer_id: str, *, revision: int
    ) -> Optional[List[Dict[str, Any]]]:
        client = await self._get_client()
        if client is None:
            return None

        try:
            raw_value = await client.get(self._key(session_id, customer_id))
            if not raw_value:
                return None
            cached = json.loads(raw_value)
            if int(cached.get("revision", -1)) != int(revision):
                return None
            messages = cached.get("messages")
            return messages if isinstance(messages, list) else None
        except Exception as exc:
            logger.warning("Failed to load Redis conversation memory: %s", exc)
            return None

    async def save_messages(
        self,
        session_id: str,
        customer_id: str,
        messages: List[Dict[str, Any]],
        *,
        revision: int,
    ) -> None:
        client = await self._get_client()
        if client is None:
            return

        try:
            payload = json.dumps(
                {"revision": revision, "messages": messages},
                ensure_ascii=False,
                default=str,
            )
            await client.set(
                self._key(session_id, customer_id),
                payload,
                ex=settings.MEMORY_TTL_SECONDS,
            )
        except Exception as exc:
            logger.warning("Failed to save Redis conversation memory: %s", exc)


redis_memory = RedisConversationMemory()
