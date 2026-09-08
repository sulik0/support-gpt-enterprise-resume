"""Skill Framework 的版本化协议。"""

import re
from dataclasses import dataclass
from typing import Any, Dict, FrozenSet, Tuple

from pydantic import BaseModel

from src.models.intents import IntentType


class SkillInput(BaseModel):
    """定义 Skill Selector 可信赖的最小输入。"""

    intent: IntentType
    operator_role: str = "agent"


class SkillOutput(BaseModel):
    """定义 Skill 选择结果的稳定输出协议。"""

    skill_name: str
    skill_version: str
    selection_strategy: str
    allowed_tools: list[str]
    forbidden_tools: list[str]
    missing_slots: list[str]


@dataclass(frozen=True)
class SkillDefinition:
    """将一类业务能力封装为可版本化的 Skill 定义。"""

    name: str
    version: str
    description: str
    supported_intents: FrozenSet[IntentType]
    allowed_tools: FrozenSet[str]
    forbidden_tools: FrozenSet[str]
    rag_categories: Tuple[str, ...]
    required_slots: Tuple[str, ...] = ()
    minimum_role: str = "agent"
    execution_mode: str = "shared_workflow"
    input_schema: type[BaseModel] = SkillInput
    output_schema: type[BaseModel] = SkillOutput

    def __post_init__(self) -> None:
        """在启动期阻止无效或相互冲突的 Skill 进入注册表。"""
        if not re.fullmatch(r"[a-z][a-z0-9_]*", self.name):
            raise ValueError(f"Invalid skill name: {self.name}")
        if not re.fullmatch(r"v\d+(?:\.\d+)*", self.version):
            raise ValueError(f"Invalid skill version: {self.version}")
        if not self.supported_intents:
            raise ValueError(f"Skill '{self.name}' must support at least one intent.")
        overlap = self.allowed_tools & self.forbidden_tools
        if overlap:
            raise ValueError(f"Skill '{self.name}' has conflicting tools: {sorted(overlap)}")

    def as_dict(self) -> Dict[str, Any]:
        """输出可用于 Trace、评测与审计的稳定快照。"""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "supported_intents": sorted(item.value for item in self.supported_intents),
            "allowed_tools": sorted(self.allowed_tools),
            "forbidden_tools": sorted(self.forbidden_tools),
            "rag_categories": list(self.rag_categories),
            "required_slots": list(self.required_slots),
            "minimum_role": self.minimum_role,
            "execution_mode": self.execution_mode,
            "input_schema": self.input_schema.model_json_schema(),
            "output_schema": self.output_schema.model_json_schema(),
        }


@dataclass(frozen=True)
class SkillSelection:
    """保存一次确定性 Skill 选择及其缺失槽位。"""

    definition: SkillDefinition
    strategy: str
    registry_id: str
    missing_slots: Tuple[str, ...] = ()

    def state_updates(self) -> Dict[str, Any]:
        """转换为可直接合并到 AgentState 的字段。"""
        output = SkillOutput(
            skill_name=self.definition.name,
            skill_version=self.definition.version,
            selection_strategy=self.strategy,
            allowed_tools=sorted(self.definition.allowed_tools),
            forbidden_tools=sorted(self.definition.forbidden_tools),
            missing_slots=list(self.missing_slots),
        )
        return {
            **output.model_dump(),
            "skill_registry_id": self.registry_id,
            "skill_required_slots": list(self.definition.required_slots),
            "skill_rag_categories": list(self.definition.rag_categories),
        }
