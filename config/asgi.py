"""
ASGI entrypoint: FastMCP at /mcp, Django for everything else.

Discovery endpoints (/.well-known/*) are owned by Django.
"""

from __future__ import annotations

import os

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

from django.conf import settings
from django.core.asgi import get_asgi_application

django_asgi_app = get_asgi_application()

from starlette.applications import Starlette
from starlette.middleware import Middleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.routing import Mount
from starlette.types import ASGIApp, Receive, Scope, Send

from mcp_server.server import create_mcp_asgi_app


class ResourceMetadataChallengeMiddleware(BaseHTTPMiddleware):
    """Advertise RFC 9728 protected resource metadata on 401 responses."""

    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        if response.status_code == 401 and request.url.path.startswith("/mcp"):
            base = getattr(settings, "PUBLIC_BASE_URL", "").rstrip("/")
            scopes = " ".join(getattr(settings, "RETRIEVER_SCOPES", {}).keys())
            metadata_url = f"{base}/.well-known/oauth-protected-resource"
            response.headers["WWW-Authenticate"] = (
                f'Bearer resource_metadata="{metadata_url}", scope="{scopes}"'
            )
        return response


class NormalizeMcpPath:
    """Ensure `/mcp` (no trailing slash) is treated like `/mcp/` for Mount."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope.get("path") == "/mcp":
            scope = dict(scope)
            scope["path"] = "/mcp/"
        await self.app(scope, receive, send)


mcp_asgi = create_mcp_asgi_app()

_starlette = Starlette(
    routes=[
        Mount("/mcp", app=mcp_asgi),
        Mount("/", app=django_asgi_app),
    ],
    lifespan=mcp_asgi.lifespan,
    middleware=[Middleware(ResourceMetadataChallengeMiddleware)],
)

application = NormalizeMcpPath(_starlette)
