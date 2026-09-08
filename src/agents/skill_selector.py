"""LangGraph Skill Selector 节点。"""

import logging
from typing import Any, Dict

from src.skills import skill_registry

logger = logging.getLogger("supportgpt.agents.skill_selector")


class SkillSelectorAgent:
    """将 Analyzer 输出确定性映射到版本化 Skill。

    V1 只负责能力选择与权限快照，不替代既有业务节点。
    """

    async def select(self, state: Dict[str, Any]) -> Dict[str, Any]:
        selection = skill_registry.select(state)
        updates = selection.state_updates()
        logger.info(
            "skill selected",
            extra={
                "ticket_id": state.get("ticket_id"),
                "skill": updates["skill_name"],
                "version": updates["skill_version"],
                "strategy": updates["selection_strategy"],
            },
        )
        return {**state, **updates}


skill_selector_agent = SkillSelectorAgent()
