"""MCP tools backed by Retriever service layer."""

from __future__ import annotations

from fastmcp import FastMCP
from fastmcp.exceptions import ToolError
from fastmcp.server.dependencies import get_access_token

from organizations.models import Organization
from retriever.services import (
    AuthContext,
    DeviceService,
    OrderService,
    write_audit,
)


def _auth_context() -> AuthContext:
    token = get_access_token()
    if token is None:
        raise ToolError("Unauthorized: missing or invalid access token")
    claims = token.claims or {}
    org_id = claims.get("organization_id")
    user_id = claims.get("user_id")
    if not org_id or not user_id:
        raise ToolError("Unauthorized: incomplete token claims")
    return AuthContext(
        user_id=int(user_id),
        organization_id=int(org_id),
        scopes=frozenset(token.scopes or []),
        oauth_client=str(claims.get("oauth_client") or token.client_id),
        username=str(claims.get("username") or ""),
    )


def _require(ctx: AuthContext, scope: str) -> None:
    if scope not in ctx.scopes:
        raise ToolError(f"Forbidden: missing scope {scope}")


def register_tools(mcp: FastMCP) -> None:
    @mcp.tool()
    def get_current_user() -> dict:
        """Return the authenticated Retriever user from the OAuth token."""
        ctx = _auth_context()
        try:
            write_audit(ctx, "get_current_user", "success")
            return {
                "user_id": ctx.user_id,
                "username": ctx.username,
            }
        except Exception as exc:
            write_audit(ctx, "get_current_user", "failure", str(exc))
            raise

    @mcp.tool()
    def get_current_organization() -> dict:
        """Return the organization bound at OAuth consent time."""
        ctx = _auth_context()
        try:
            org = Organization.objects.filter(id=ctx.organization_id).first()
            if org is None:
                raise ToolError("Organization not found")
            write_audit(ctx, "get_current_organization", "success")
            return {"organization_id": org.id, "name": org.name}
        except ToolError:
            write_audit(ctx, "get_current_organization", "failure")
            raise
        except Exception as exc:
            write_audit(ctx, "get_current_organization", "failure", str(exc))
            raise ToolError("Failed to resolve organization") from exc

    @mcp.tool()
    def get_devices(organization_id: int | None = None) -> list[dict]:
        """
        List devices for the authenticated organization.

        Any organization_id supplied by the model is ignored; tenant comes
        from the OAuth token context only.
        """
        ctx = _auth_context()
        _require(ctx, "retriever.devices.read")
        # Explicitly ignore client-supplied organization_id
        _ = organization_id
        try:
            result = DeviceService.get_devices(organization_id=ctx.organization_id)
            write_audit(ctx, "get_devices", "success")
            return result
        except Exception as exc:
            write_audit(ctx, "get_devices", "failure", str(exc))
            raise ToolError("Failed to list devices") from exc

    @mcp.tool()
    def get_deployment_orders(organization_id: int | None = None) -> list[dict]:
        """List deployment orders for the authenticated organization."""
        ctx = _auth_context()
        _require(ctx, "retriever.orders.read")
        _ = organization_id
        try:
            result = OrderService.get_deployment_orders(
                organization_id=ctx.organization_id
            )
            write_audit(ctx, "get_deployment_orders", "success")
            return result
        except Exception as exc:
            write_audit(ctx, "get_deployment_orders", "failure", str(exc))
            raise ToolError("Failed to list deployment orders") from exc

    @mcp.tool()
    def get_return_orders(organization_id: int | None = None) -> list[dict]:
        """List return orders for the authenticated organization."""
        ctx = _auth_context()
        _require(ctx, "retriever.orders.read")
        _ = organization_id
        try:
            result = OrderService.get_return_orders(organization_id=ctx.organization_id)
            write_audit(ctx, "get_return_orders", "success")
            return result
        except Exception as exc:
            write_audit(ctx, "get_return_orders", "failure", str(exc))
            raise ToolError("Failed to list return orders") from exc

    @mcp.tool()
    def create_test_deployment_order(
        notes: str = "Created via MCP demo tool",
        organization_id: int | None = None,
    ) -> dict:
        """Create a demo deployment order in the authenticated organization."""
        ctx = _auth_context()
        _require(ctx, "retriever.orders.write")
        _ = organization_id
        try:
            result = OrderService.create_test_deployment_order(
                organization_id=ctx.organization_id,
                notes=notes,
            )
            write_audit(ctx, "create_test_deployment_order", "success", result["reference"])
            return result
        except PermissionError as exc:
            write_audit(ctx, "create_test_deployment_order", "failure", str(exc))
            raise ToolError(str(exc)) from exc
        except Exception as exc:
            write_audit(ctx, "create_test_deployment_order", "failure", str(exc))
            raise ToolError("Failed to create deployment order") from exc
