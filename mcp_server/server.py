"""FastMCP Resource Server for Retriever."""

from __future__ import annotations

from django.conf import settings
from fastmcp import FastMCP
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from mcp_server.auth import DjangoAccessTokenVerifier
from mcp_server.tools import register_tools


def build_mcp() -> FastMCP:
    verifier = DjangoAccessTokenVerifier()
    mcp = FastMCP(
        name="Retriever MCP",
        instructions=(
            "Retriever demo MCP server. Identity and organization come from "
            "the OAuth access token issued by Retriever after user consent."
        ),
        auth=verifier,
        mask_error_details=True,
    )
    register_tools(mcp)

    @mcp.custom_route("/health", methods=["GET"])
    async def health(_request: Request) -> Response:
        return JSONResponse({"status": "ok", "service": "retriever-mcp"})

    return mcp


_mcp: FastMCP | None = None


def get_mcp() -> FastMCP:
    global _mcp
    if _mcp is None:
        _mcp = build_mcp()
    return _mcp


def create_mcp_asgi_app():
    """
    Streamable HTTP ASGI app for serverless (Vercel).

    Mounted at /mcp by config.asgi — use path="/" here so the public
    resource URL is https://<host>/mcp.
    """
    mcp = get_mcp()
    return mcp.http_app(
        path="/",
        json_response=True,
        stateless_http=True,
    )
