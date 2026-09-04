import logging
import sys
from contextlib import AbstractAsyncContextManager
from pathlib import Path
from typing import Any

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import MemorySaver
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver

from src.config import settings

logger = logging.getLogger("supportgpt.agents.checkpointing")


class AgentCheckpointManager:
    """管理 LangGraph Checkpointer 的初始化与连接生命周期。

    本地使用 SQLite，PostgreSQL 部署使用官方 AsyncPostgresSaver。
    """

    def __init__(self) -> None:
        self._saver: BaseCheckpointSaver = MemorySaver()
        self._context: AbstractAsyncContextManager[Any] | None = None
        self._started = False
        self.backend = "memory"

    @property
    def saver(self) -> BaseCheckpointSaver:
        return self._saver

    async def start(self) -> BaseCheckpointSaver:
        """启动持久化 Saver，创建 LangGraph 官方 Checkpoint 表。"""
        if self._started:
            return self._saver
        if not settings.LANGGRAPH_CHECKPOINT_ENABLED:
            self._started = True
            logger.warning("LangGraph checkpointing is disabled; using memory only")
            return self._saver

        database_url = self._checkpoint_database_url()
        if self._is_postgres(database_url):
            self._context = AsyncPostgresSaver.from_conn_string(
                self._normalize_postgres_url(database_url)
            )
            self.backend = "postgresql"
        else:
            sqlite_path = self._sqlite_path(database_url)
            if sqlite_path != ":memory:":
                Path(sqlite_path).expanduser().resolve().parent.mkdir(
                    parents=True, exist_ok=True
                )
            self._context = AsyncSqliteSaver.from_conn_string(sqlite_path)
            self.backend = "sqlite"

        try:
            self._saver = await self._context.__aenter__()
            await self._saver.setup()
        except BaseException:
            if self._context is not None:
                await self._context.__aexit__(*sys.exc_info())
            self._context = None
            self.backend = "memory"
            raise

        self._started = True
        logger.info("LangGraph checkpointing initialized", extra={"backend": self.backend})
        return self._saver

    async def stop(self) -> None:
        """关闭 Saver 底层连接，不删除已保存的 Checkpoint。"""
        context = self._context
        self._context = None
        self._started = False
        self._saver = MemorySaver()
        self.backend = "memory"
        if context is not None:
            await context.__aexit__(None, None, None)

    @staticmethod
    def _is_postgres(database_url: str | None) -> bool:
        return bool(
            database_url
            and database_url.startswith(("postgres://", "postgresql"))
        )

    @staticmethod
    def _normalize_postgres_url(database_url: str) -> str:
        normalized = database_url.replace(
            "postgresql+asyncpg://", "postgresql://", 1
        )
        return normalized.replace("postgres://", "postgresql://", 1)

    @staticmethod
    def _sqlite_path(database_url: str | None) -> str:
        if not database_url:
            return settings.LANGGRAPH_CHECKPOINT_SQLITE_PATH
        for prefix in ("sqlite+aiosqlite:///", "sqlite:///"):
            if database_url.startswith(prefix):
                return database_url[len(prefix) :]
        if database_url in {"sqlite+aiosqlite:///:memory:", "sqlite:///:memory:"}:
            return ":memory:"
        raise ValueError("LangGraph checkpoint database must be PostgreSQL or SQLite.")

    @staticmethod
    def _checkpoint_database_url() -> str | None:
        explicit = settings.LANGGRAPH_CHECKPOINT_DATABASE_URL
        if explicit:
            return explicit
        if settings.DATABASE_URL.startswith(("postgres://", "postgresql")):
            return settings.DATABASE_URL
        if settings.APP_ENV == "testing" and ":memory:" in settings.DATABASE_URL:
            return "sqlite+aiosqlite:///:memory:"
        return None


checkpoint_manager = AgentCheckpointManager()
