"""文件型不可变 Prompt Registry 与原子环境版本指针。"""

from __future__ import annotations

import fcntl
import hashlib
import json
import os
import re
import tempfile
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from string import Template
from typing import Any, Iterator

from src.promptops.defaults import default_payload


INPUTS = {
    "analyzer": {"text"},
    "resolver": {"subject", "description", "context"},
    "qa": {"query", "context", "response"},
}


def canonical_hash(value: Any) -> str:
    """用稳定 JSON 编码生成内容标识，不依赖文件缩进。"""
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def atomic_json(path: Path, value: Any) -> None:
    """同目录写入后原子替换，读者不会读到半份指针。"""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temporary = tempfile.mkstemp(dir=path.parent, prefix=".pending-")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as stream:
            json.dump(value, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


class PromptBundle:
    """验证三个节点的模板契约，以内容 Hash 标识整个 Bundle。

    对外只返回副本，避免并发请求修改已绑定的版本。
    """

    def __init__(self, payload: dict[str, Any]) -> None:
        if set(payload) != {"schema_version", "version", "templates"}:
            raise ValueError("Prompt Bundle requires schema_version, version and templates.")
        if payload["schema_version"] != "1.0":
            raise ValueError("Unsupported Prompt Bundle schema.")
        if not re.fullmatch(r"[a-zA-Z0-9][a-zA-Z0-9._-]{0,79}", str(payload["version"])):
            raise ValueError("Invalid Prompt version label.")
        templates = payload["templates"]
        if not isinstance(templates, dict) or set(templates) != set(INPUTS):
            raise ValueError("Bundle must contain analyzer, resolver and qa.")
        for node, expected in INPUTS.items():
            item = templates[node]
            if not isinstance(item, dict) or set(item) != {"system", "user"}:
                raise ValueError(f"{node}: system and user templates are required.")
            for role, content in item.items():
                if not isinstance(content, str) or not content.strip() or len(content) > 30000:
                    raise ValueError(f"{node}.{role}: invalid template content.")
                template = Template(content)
                if not template.is_valid():
                    raise ValueError(f"{node}.{role}: invalid placeholder; escape literal $ as $$.")
                required = expected if role == "user" else set()
                if set(template.get_identifiers()) != required:
                    raise ValueError(f"{node}.{role}: placeholders must be {sorted(required)}.")
        self._payload = json.loads(json.dumps(payload))
        self.bundle_id = canonical_hash(self._payload)
        self.version = self._payload["version"]

    def payload(self) -> dict[str, Any]:
        return json.loads(json.dumps(self._payload))

    def metadata(self) -> dict[str, Any]:
        return {
            "bundle_id": self.bundle_id,
            "version": self.version,
            "node_hashes": {
                node: canonical_hash(value)
                for node, value in self._payload["templates"].items()
            },
        }

    def messages(self, node: str, **values: str) -> list[dict[str, str]]:
        """仅替换白名单变量，用户文本中的占位符不会再次展开。"""
        if set(values) != INPUTS[node]:
            raise ValueError(f"Unexpected inputs for {node}.")
        return [
            {"role": role, "content": Template(self._payload["templates"][node][role]).substitute(values)}
            for role in ("system", "user")
        ]


class PromptRegistry:
    """管理内容寻址快照和带审计记录的环境指针。

    V1 使用本机文件锁，适用于单机或统一发布目录。
    """

    def __init__(self, root: Path) -> None:
        self.root = Path(root)

    @contextmanager
    def _lock(self) -> Iterator[None]:
        self.root.mkdir(parents=True, exist_ok=True)
        with (self.root / ".registry.lock").open("a") as stream:
            fcntl.flock(stream, fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(stream, fcntl.LOCK_UN)

    def register(self, payload: dict[str, Any]) -> PromptBundle:
        bundle = PromptBundle(payload)
        with self._lock():
            path = self.root / "bundles" / f"{bundle.bundle_id}.json"
            if path.exists():
                self.load(bundle.bundle_id)
            else:
                atomic_json(path, bundle.payload())
        return bundle

    def load(self, bundle_id: str) -> PromptBundle:
        if not re.fullmatch(r"[0-9a-f]{64}", bundle_id):
            raise ValueError("Bundle ID must be a SHA256 hash.")
        path = self.root / "bundles" / f"{bundle_id}.json"
        if not path.exists() and bundle_id == PromptBundle(default_payload()).bundle_id:
            return PromptBundle(default_payload())
        bundle = PromptBundle(json.loads(path.read_text(encoding="utf-8")))
        if bundle.bundle_id != bundle_id:
            raise ValueError("Prompt snapshot hash mismatch.")
        return bundle

    def state(self) -> dict[str, Any]:
        path = self.root / "releases.json"
        return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {
            "environments": {}, "history": []
        }

    def resolve(self, environment: str) -> PromptBundle:
        self._environment(environment)
        bundle_id = self.state()["environments"].get(environment)
        return self.load(bundle_id) if bundle_id else PromptBundle(default_payload())

    def _release(
        self, *, environment: str, bundle_id: str, expected_current: str,
        actor: str, reason: str, evidence: dict[str, Any], operation: str = "promote",
    ) -> dict[str, Any]:
        """证据由 EvalOps 验证后写入；CAS 拒绝过时实验覆盖新版本。"""
        self._environment(environment)
        if not actor.strip() or not reason.strip():
            raise ValueError("Release actor and reason are required.")
        self.load(bundle_id)
        with self._lock():
            state = self.state()
            current = state["environments"].get(environment) or PromptBundle(default_payload()).bundle_id
            if current != expected_current:
                raise ValueError("Active Prompt changed; re-evaluate against the current version.")
            if current == bundle_id:
                raise ValueError("Candidate is already active.")
            event = {
                "sequence": len(state["history"]) + 1,
                "at": datetime.now(timezone.utc).isoformat(),
                "environment": environment, "operation": operation,
                "previous": current, "bundle_id": bundle_id,
                "actor": actor, "reason": reason, "evidence": evidence,
            }
            state["environments"][environment] = bundle_id
            state["history"].append(event)
            atomic_json(self.root / "releases.json", state)
        return event

    def rollback(self, *, environment: str, actor: str, reason: str) -> dict[str, Any]:
        """回到该环境最近一次切换之前的版本，不允许指定未发布版本。"""
        self._environment(environment)
        history = [e for e in self.state()["history"] if e["environment"] == environment]
        if not history:
            raise ValueError("No release to roll back.")
        previous = history[-1]
        return self._release(
            environment=environment, bundle_id=previous["previous"],
            expected_current=previous["bundle_id"], actor=actor, reason=reason,
            evidence={"rollback_of": previous["sequence"]}, operation="rollback",
        )

    @staticmethod
    def _environment(value: str) -> None:
        if value not in {"staging", "production"}:
            raise ValueError("Environment must be staging or production.")
