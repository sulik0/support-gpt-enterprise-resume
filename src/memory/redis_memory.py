import json
import logging
from typing import Any, Dict, List, Optional

from src.config import settings

logger = logging.getLogger("supportgpt.memory.redis")


class RedisConversationMemory:
    """
    Optional Redis-backed short-term conversation memory.

    SQL `SessionMemory` remains the durable store. Redis is used as a fast
    working-memory cache when `REDIS_URL` is configured.
    """

    def __init__(self, max_turns: int = 12):
        self.max_turns = max_turns
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

    def _key(self, session_id: str) -> str:
        return f"supportgpt:session:{session_id}:messages"

    async def load_messages(self, session_id: str) -> Optional[List[Dict[str, Any]]]:
        client = await self._get_client()
        if client is None:
            return None

        try:
            raw_messages = await client.lrange(self._key(session_id), 0, -1)
            return [json.loads(item) for item in raw_messages]
        except Exception as exc:
            logger.warning("Failed to load Redis conversation memory: %s", exc)
            return None

    async def save_messages(self, session_id: str, messages: List[Dict[str, Any]]) -> None:
        client = await self._get_client()
        if client is None:
            return

        try:
            key = self._key(session_id)
            trimmed = messages[-self.max_turns :]
            await client.delete(key)
            if trimmed:
                await client.rpush(key, *[json.dumps(msg, default=str) for msg in trimmed])
            await client.expire(key, 60 * 60 * 24)
        except Exception as exc:
            logger.warning("Failed to save Redis conversation memory: %s", exc)


redis_memory = RedisConversationMemory()
