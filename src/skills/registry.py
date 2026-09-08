"""Skill 注册、选择与 Tool Policy 校验。"""

import hashlib
import json
from typing import Any, Dict, Iterable, Optional

from src.models.intents import IntentType, normalize_intent
from src.skills.models import SkillDefinition, SkillInput, SkillSelection


ROLE_RANK = {"agent": 1, "manager": 2, "admin": 3}


class SkillRegistry:
    """集中管理 Skill 协议，并提供确定性 Intent 路由。

    V1 不让 LLM 自由选 Skill，避免路由漂移和权限扩散。
    """

    def __init__(self, version: str) -> None:
        self.version = version
        self._skills: Dict[str, SkillDefinition] = {}
        self._intent_index: Dict[IntentType, str] = {}
        self._registry_id: Optional[str] = None

    def register(self, definition: SkillDefinition) -> None:
        """注册 Skill，同一 Intent 在 V1 中只允许一个主 Skill。"""
        if definition.name in self._skills:
            raise ValueError(f"Skill '{definition.name}' is already registered.")
        duplicates = definition.supported_intents & self._intent_index.keys()
        if duplicates:
            raise ValueError(
                f"Intents already registered: {sorted(item.value for item in duplicates)}"
            )
        self._skills[definition.name] = definition
        for intent in definition.supported_intents:
            self._intent_index[intent] = definition.name
        self._registry_id = None

    @property
    def registry_id(self) -> str:
        """使用内容 Hash 标识当前注册表快照。"""
        if self._registry_id is None:
            canonical = json.dumps(
                self.snapshot(include_registry_id=False), sort_keys=True
            )
            self._registry_id = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
        return self._registry_id

    def get(self, name: str) -> Optional[SkillDefinition]:
        return self._skills.get(name)

    def list_skills(self) -> list[Dict[str, Any]]:
        return [self._skills[name].as_dict() for name in sorted(self._skills)]

    def snapshot(self, *, include_registry_id: bool = True) -> Dict[str, Any]:
        snapshot = {"version": self.version, "skills": self.list_skills()}
        if include_registry_id:
            snapshot["registry_id"] = self.registry_id
        return snapshot

    def select(self, state: Dict[str, Any]) -> SkillSelection:
        """依据归一化 Intent 选择 Skill，并校验最低角色。"""
        parsed = SkillInput.model_validate(
            {
                "intent": normalize_intent(state.get("intent")),
                "operator_role": state.get("operator_role", "agent"),
            }
        )
        name = self._intent_index.get(parsed.intent)
        if not name:
            raise LookupError(f"No Skill registered for intent '{parsed.intent}'.")
        definition = self._skills[name]
        if ROLE_RANK.get(parsed.operator_role, 0) < ROLE_RANK.get(
            definition.minimum_role, 999
        ):
            raise PermissionError(
                f"Role '{parsed.operator_role}' cannot select Skill '{name}'."
            )
        missing_slots = tuple(
            slot for slot in definition.required_slots if not state.get(slot)
        )
        return SkillSelection(
            definition=definition,
            strategy="intent_rule",
            registry_id=self.registry_id,
            missing_slots=missing_slots,
        )

    def tool_policy_error(
        self, skill_name: str, skill_version: Optional[str], tool_name: str
    ) -> Optional[str]:
        """在 Tool Handler 前校验 Skill 版本及 Tool Allowlist。"""
        definition = self.get(skill_name)
        if not definition:
            return f"Skill '{skill_name}' is not registered."
        if skill_version != definition.version:
            return (
                f"Skill '{skill_name}' version mismatch: expected "
                f"'{definition.version}', got '{skill_version}'."
            )
        if tool_name in definition.forbidden_tools:
            return f"Tool '{tool_name}' is forbidden by Skill '{skill_name}'."
        if tool_name not in definition.allowed_tools:
            return f"Tool '{tool_name}' is not allowed by Skill '{skill_name}'."
        return None

    def validate_tool_catalog(self, tool_names: Iterable[str]) -> None:
        """启动或测试时校验 Skill 引用的 Tool 已注册。"""
        available = set(tool_names)
        referenced = set().union(
            *(skill.allowed_tools | skill.forbidden_tools for skill in self._skills.values())
        )
        unknown = referenced - available
        if unknown:
            raise ValueError(f"Skills reference unknown tools: {sorted(unknown)}")
