"""在一次 Workflow 内固定 Prompt Bundle，隔离并发候选实验。"""

from contextlib import contextmanager
from contextvars import ContextVar
from pathlib import Path
from typing import Iterator

from src.config import settings
from src.promptops.registry import PromptBundle, PromptRegistry


_bundle: ContextVar[PromptBundle | None] = ContextVar("prompt_bundle", default=None)


def active_bundle() -> PromptBundle:
    """显式实验版本优先，其次部署固定 Hash，最后读取环境指针。"""
    pinned = _bundle.get()
    if pinned is not None:
        return pinned
    registry = PromptRegistry(Path(settings.PROMPT_REGISTRY_DIR))
    if settings.PROMPT_BUNDLE_ID:
        return registry.load(settings.PROMPT_BUNDLE_ID)
    selected = registry.resolve(settings.PROMPT_ENVIRONMENT)
    # 默认模板也落盘，后续升级内置模板后仍能按旧 Hash 查回内容。
    if not (registry.root / "bundles" / f"{selected.bundle_id}.json").exists():
        registry.register(selected.payload())
    return selected


@contextmanager
def prompt_scope(bundle: PromptBundle | None = None) -> Iterator[PromptBundle]:
    """请求开始时绑定快照，发布切换不影响正在执行的请求。"""
    selected = bundle or active_bundle()
    token = _bundle.set(selected)
    try:
        yield selected
    finally:
        _bundle.reset(token)
