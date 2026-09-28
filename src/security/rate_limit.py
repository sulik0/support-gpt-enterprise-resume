"""Redis 优先、内存降级的公网接口限流器。"""

from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from dataclasses import dataclass

from fastapi import HTTPException, status

from src.config import settings


logger = logging.getLogger("supportgpt.security.rate_limit")


@dataclass
class _MemoryCounter:
    """保存单个固定时间窗口的计数和过期时间。"""

    count: int
    expires_at: float


class PublicRateLimiter:
    """对高成本公开请求执行多身份、多时间窗口限流。"""

    def __init__(self) -> None:
        self._redis = None
        self._redis_failed = False
        self._memory: dict[str, _MemoryCounter] = {}
        self._lock = asyncio.Lock()

    async def enforce(
        self,
        *,
        scope: str,
        identities: tuple[str, ...],
        limit: int,
        window_seconds: int,
    ) -> None:
        """任一身份超额即拒绝，并返回标准 Retry-After。"""
        if not settings.PUBLIC_RATE_LIMIT_ENABLED:
            return
        window = int(time.time()) // window_seconds
        retry_after = window_seconds - (int(time.time()) % window_seconds)
        for identity in identities:
            key = self._key(scope, identity, window_seconds, window)
            count = await self._increment(key, window_seconds)
            if count > limit:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail="Too many requests. Please retry later.",
                    headers={"Retry-After": str(max(retry_after, 1))},
                )

    async def close(self) -> None:
        """关闭 Redis 连接，用于应用优雅退出。"""
        client = self._redis
        self._redis = None
        if client is not None:
            await client.aclose()

    async def reset_for_tests(self) -> None:
        """清空进程内计数，避免测试用例相互影响。"""
        async with self._lock:
            self._memory.clear()

    async def _increment(self, key: str, ttl: int) -> int:
        client = await self._redis_client()
        if client is not None:
            try:
                value = await client.eval(
                    "local n=redis.call('INCR',KEYS[1]); "
                    "if n==1 then redis.call('EXPIRE',KEYS[1],ARGV[1]) end; return n",
                    1,
                    key,
                    ttl + 1,
                )
                return int(value)
            except Exception as exc:
                self._redis_failed = True
                failed_client = self._redis
                self._redis = None
                if failed_client is not None:
                    try:
                        await failed_client.aclose()
                    except Exception:
                        pass
                logger.warning(
                    "rate limiter redis unavailable; using in-memory fallback",
                    extra={"error_type": exc.__class__.__name__},
                )
        return await self._increment_memory(key, ttl)

    async def _redis_client(self):
        if self._redis is not None:
            return self._redis
        if self._redis_failed or not settings.REDIS_URL:
            return None
        try:
            import redis.asyncio as redis

            self._redis = redis.from_url(
                settings.REDIS_URL,
                encoding="utf-8",
                decode_responses=True,
                socket_connect_timeout=0.25,
                socket_timeout=0.5,
            )
            return self._redis
        except Exception as exc:
            self._redis_failed = True
            logger.warning(
                "rate limiter redis initialization failed",
                extra={"error_type": exc.__class__.__name__},
            )
            return None

    async def _increment_memory(self, key: str, ttl: int) -> int:
        now = time.monotonic()
        async with self._lock:
            counter = self._memory.get(key)
            if counter is None or counter.expires_at <= now:
                counter = _MemoryCounter(count=0, expires_at=now + ttl + 1)
            counter.count += 1
            self._memory[key] = counter
            if len(self._memory) > 10000:
                active = {
                    item_key: item
                    for item_key, item in self._memory.items()
                    if item.expires_at > now
                }
                self._memory = dict(list(active.items())[-10000:])
            return counter.count

    @staticmethod
    def _key(scope: str, identity: str, ttl: int, window: int) -> str:
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
        return f"{settings.RATE_LIMIT_REDIS_PREFIX}:{scope}:{ttl}:{window}:{digest}"


public_rate_limiter = PublicRateLimiter()
