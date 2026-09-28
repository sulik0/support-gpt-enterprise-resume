#!/usr/bin/env python3
"""在不开放公开注册的前提下初始化首个员工账号。"""

from __future__ import annotations

import argparse
import asyncio
import getpass
import os

from sqlalchemy import select

from src.auth.jwt import get_password_hash
from src.database import AsyncSessionLocal, init_db
from src.models.db_models import User


async def create_user(username: str, password: str, role: str) -> None:
    """直接通过受控数据库连接创建账号。"""
    await init_db()
    async with AsyncSessionLocal() as session:
        existing = await session.scalar(select(User).where(User.username == username))
        if existing:
            raise SystemExit(f"Staff user '{username}' already exists.")
        session.add(
            User(
                username=username,
                hashed_password=get_password_hash(password),
                role=role,
            )
        )
        await session.commit()
    print(f"Created staff user '{username}' with role '{role}'.")


def main() -> None:
    parser = argparse.ArgumentParser(description="Create a SupportGPT staff user.")
    parser.add_argument("username")
    parser.add_argument("--role", choices=("agent", "manager", "admin"), default="agent")
    parser.add_argument(
        "--password-env",
        default="STAFF_BOOTSTRAP_PASSWORD",
        help="Read the password from this environment variable; otherwise prompt securely.",
    )
    args = parser.parse_args()
    password = os.getenv(args.password_env) or getpass.getpass("Staff password: ")
    if len(password) < 12:
        parser.error("staff passwords must contain at least 12 characters")
    asyncio.run(create_user(args.username, password, args.role))


if __name__ == "__main__":
    main()
