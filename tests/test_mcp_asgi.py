"""ASGI-level MCP endpoint tests using Starlette/httpx."""

from __future__ import annotations

from datetime import timedelta

import pytest
from asgi_lifespan import LifespanManager
from django.contrib.auth import get_user_model
from django.utils import timezone
from httpx import ASGITransport, AsyncClient
from oauth2_provider.generators import generate_client_id, generate_client_secret
from oauth2_provider.models import AccessToken, Application

from organizations.models import Organization, OrganizationMembership, UserProfile
from oauth_server.models import OAuthAuthorizationContext
from retriever.models import Device

User = get_user_model()


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_mcp_requires_auth_and_discovery_header(settings):
    settings.PUBLIC_BASE_URL = "http://testserver"
    settings.MCP_RESOURCE_URL = "http://testserver/mcp"

    from config.asgi import application

    async with LifespanManager(application):
        transport = ASGITransport(app=application)
        async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
            resp = await ac.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-11-25",
                        "capabilities": {},
                        "clientInfo": {"name": "test", "version": "0"},
                    },
                },
                headers={"Accept": "application/json, text/event-stream"},
            )
            assert resp.status_code == 401
            assert "resource_metadata" in resp.headers.get("www-authenticate", "")


@pytest.mark.django_db(transaction=True)
@pytest.mark.asyncio
async def test_mcp_tool_with_token(settings):
    settings.PUBLIC_BASE_URL = "http://testserver"
    settings.MCP_RESOURCE_URL = "http://testserver/mcp"
    settings.MCP_REQUIRE_AUDIENCE = True

    user = await User.objects.acreate(username="mcp_user")
    user.set_password("DemoPassword123!")
    await user.asave()
    org = await Organization.objects.acreate(name="MCP Org")
    await OrganizationMembership.objects.acreate(
        user=user, organization=org, role="owner"
    )
    profile, _ = await UserProfile.objects.aget_or_create(user=user)
    profile.active_organization = org
    await profile.asave()
    await Device.objects.acreate(
        organization=org, name="MacBook Pro", serial_number="MCP-1"
    )

    raw = generate_client_secret()
    app = Application(
        name="Claude Retriever Demo",
        client_id=generate_client_id(),
        client_secret=raw,
        client_type=Application.CLIENT_CONFIDENTIAL,
        authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
        redirect_uris="https://claude.ai/api/mcp/auth_callback",
        hash_client_secret=True,
    )
    await app.asave()
    token = await AccessToken.objects.acreate(
        user=user,
        application=app,
        token="mcp-async-token-0001",
        expires=timezone.now() + timedelta(hours=1),
        scope="retriever.devices.read retriever.orders.read retriever.orders.write",
        resource=["http://testserver/mcp"],
    )
    await OAuthAuthorizationContext.objects.acreate(
        application=app,
        user=user,
        organization=org,
        access_token=token,
        scopes=token.scope,
    )

    from config.asgi import application

    async with LifespanManager(application):
        transport = ASGITransport(app=application)
        async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
            init = await ac.post(
                "/mcp",
                json={
                    "jsonrpc": "2.0",
                    "id": 1,
                    "method": "initialize",
                    "params": {
                        "protocolVersion": "2025-11-25",
                        "capabilities": {},
                        "clientInfo": {"name": "test", "version": "0"},
                    },
                },
                headers={
                    "Accept": "application/json, text/event-stream",
                    "Authorization": f"Bearer {token.token}",
                },
            )
            assert init.status_code == 200, init.text
