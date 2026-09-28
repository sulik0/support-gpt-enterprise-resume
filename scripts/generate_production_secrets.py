#!/usr/bin/env python3
"""生成并安全写入 SupportGPT 生产密钥，不在终端回显密钥。"""

from __future__ import annotations

import argparse
import os
import secrets
import tempfile
from pathlib import Path

from cryptography.fernet import Fernet


def _replace_values(content: str, replacements: dict[str, str]) -> str:
    """保留其他环境配置，仅旋转指定密钥。"""
    remaining = dict(replacements)
    lines: list[str] = []
    for line in content.splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            key = line.split("=", 1)[0].strip()
            if key in remaining:
                lines.append(f"{key}={remaining.pop(key)}")
                continue
        lines.append(line)
    if remaining:
        if lines and lines[-1]:
            lines.append("")
        lines.append("# Generated production security secrets")
        lines.extend(f"{key}={value}" for key, value in remaining.items())
    return "\n".join(lines) + "\n"


def rotate(path: Path) -> None:
    """使用原子替换写入密钥文件，并限制为当前用户读写。"""
    original = path.read_text(encoding="utf-8") if path.exists() else ""
    updated = _replace_values(
        original,
        {
            "JWT_SECRET": secrets.token_urlsafe(48),
            "TOOL_ACTION_ENCRYPTION_KEY": Fernet.generate_key().decode("ascii"),
            "PUBLIC_VISITOR_SECRET": secrets.token_urlsafe(48),
        },
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary = tempfile.mkstemp(prefix=".env-secrets-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            stream.write(updated)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temporary, 0o600)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Rotate JWT, Tool encryption and public visitor secrets."
    )
    parser.add_argument("--env-file", default=".env.production")
    parser.add_argument(
        "--confirm",
        action="store_true",
        help="Required because rotating keys invalidates existing tokens and pending payloads.",
    )
    args = parser.parse_args()
    if not args.confirm:
        parser.error("pass --confirm to rotate secrets")
    path = Path(args.env_file).expanduser().resolve()
    rotate(path)
    print(f"Rotated production secrets in {path} (values intentionally hidden).")


if __name__ == "__main__":
    main()
