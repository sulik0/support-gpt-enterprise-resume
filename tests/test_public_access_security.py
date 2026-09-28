import datetime

import pytest
from cryptography.fernet import Fernet
from fastapi import HTTPException

from src.config import Settings, settings
from src.models.db_models import ConversationMessage, ConversationSession
from src.security import public_access_service, public_rate_limiter


@pytest.mark.asyncio
async def test_staff_self_registration_can_be_disabled(client, monkeypatch):
    monkeypatch.setattr(settings, "STAFF_SELF_REGISTRATION_ENABLED", False)

    response = await client.post(
        "/auth/register",
        json={"username": "public_admin", "password": "password", "role": "admin"},
    )

    assert response.status_code == 404


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("path", "payload"),
    [
        (
            "/chat",
            {
                "session_id": "unauthorized-session",
                "customer_id": "cust_101",
                "message": "Run the internal workflow",
            },
        ),
        (
            "/evaluate-response",
            {"query": "q", "context": ["c"], "response": "a"},
        ),
    ],
)
async def test_internal_llm_endpoints_require_staff_authentication(
    client, path, payload
):
    response = await client.post(path, json=payload)

    assert response.status_code in {401, 403}


@pytest.mark.asyncio
async def test_cors_only_allows_configured_frontend(client):
    allowed = await client.options(
        "/support/requests",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    denied = await client.options(
        "/support/requests",
        headers={
            "Origin": "https://attacker.example",
            "Access-Control-Request-Method": "POST",
        },
    )

    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert denied.status_code == 400
    assert "access-control-allow-origin" not in denied.headers


@pytest.mark.asyncio
async def test_sensitive_responses_disable_caching(client):
    response = await client.post(
        "/auth/token",
        json={"username": "unknown", "password": "not-the-password"},
    )

    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["x-frame-options"] == "DENY"


@pytest.mark.asyncio
async def test_public_history_is_isolated_by_signed_visitor(
    client, db_session, monkeypatch
):
    monkeypatch.setattr(settings, "PUBLIC_DEMO_ISOLATION_ENABLED", True)
    monkeypatch.setattr(settings, "PUBLIC_VISITOR_SECRET", "v" * 48)
    visitor_id = "visitor_identity_1234567890"
    session_id = "shared-browser-session"
    internal_session_id = public_access_service.scoped_session_id(
        visitor_id, session_id
    )
    db_session.add(
        ConversationSession(
            session_id=internal_session_id,
            customer_id="cust_101",
        )
    )
    db_session.add(
        ConversationMessage(
            id="isolated-message",
            session_id=internal_session_id,
            role="user",
            content="只属于访客 A 的对话",
            status="final",
            created_at=datetime.datetime.utcnow(),
        )
    )
    await db_session.commit()
    client.cookies.set(
        settings.PUBLIC_VISITOR_COOKIE_NAME,
        public_access_service._signed(visitor_id),
    )

    owner = await client.get(
        "/support/history",
        params={"customer_id": "cust_101", "session_id": session_id},
    )
    assert owner.status_code == 200
    assert [item["id"] for item in owner.json()["messages"]] == [
        "isolated-message"
    ]

    client.cookies.clear()
    other_visitor = await client.get(
        "/support/history",
        params={"customer_id": "cust_101", "session_id": session_id},
    )
    assert other_visitor.status_code == 200
    assert other_visitor.json()["messages"] == []
    assert settings.PUBLIC_VISITOR_COOKIE_NAME in other_visitor.cookies


@pytest.mark.asyncio
async def test_public_demo_rejects_unknown_customer_profile(client, monkeypatch):
    monkeypatch.setattr(settings, "PUBLIC_DEMO_ISOLATION_ENABLED", True)

    response = await client.get(
        "/support/history",
        params={"customer_id": "real_customer_42", "session_id": "session-a"},
    )

    assert response.status_code == 422


@pytest.mark.asyncio
async def test_rate_limiter_blocks_after_configured_limit(monkeypatch):
    monkeypatch.setattr(settings, "PUBLIC_RATE_LIMIT_ENABLED", True)
    monkeypatch.setattr(settings, "REDIS_URL", None)
    await public_rate_limiter.reset_for_tests()

    await public_rate_limiter.enforce(
        scope="security-test",
        identities=("visitor-a",),
        limit=1,
        window_seconds=60,
    )
    with pytest.raises(HTTPException) as error:
        await public_rate_limiter.enforce(
            scope="security-test",
            identities=("visitor-a",),
            limit=1,
            window_seconds=60,
        )

    assert error.value.status_code == 429
    assert error.value.headers["Retry-After"]


def test_production_rejects_default_jwt_secret():
    with pytest.raises(ValueError, match="JWT_SECRET"):
        Settings(
            APP_ENV="production",
            DEBUG=False,
            JWT_SECRET="super-secret-jwt-key-change-in-production-123456",
            TOOL_ACTION_ENCRYPTION_KEY=Fernet.generate_key().decode("ascii"),
            PUBLIC_VISITOR_SECRET="p" * 48,
            CORS_ALLOWED_ORIGINS="https://support.example.com",
            STAFF_SELF_REGISTRATION_ENABLED=False,
            PUBLIC_DEMO_ISOLATION_ENABLED=True,
            PUBLIC_RATE_LIMIT_ENABLED=True,
        )


def test_production_accepts_explicit_security_configuration():
    configured = Settings(
        APP_ENV="production",
        DEBUG=False,
        JWT_SECRET="j" * 48,
        TOOL_ACTION_ENCRYPTION_KEY=Fernet.generate_key().decode("ascii"),
        PUBLIC_VISITOR_SECRET="p" * 48,
        CORS_ALLOWED_ORIGINS="https://support.example.com",
        STAFF_SELF_REGISTRATION_ENABLED=False,
        PUBLIC_DEMO_ISOLATION_ENABLED=True,
        PUBLIC_RATE_LIMIT_ENABLED=True,
    )

    assert configured.cors_allowed_origins == ["https://support.example.com"]
