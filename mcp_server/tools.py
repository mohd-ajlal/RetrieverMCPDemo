"""MCP tools backed by Retriever service layer."""

from __future__ import annotations

from django.core.exceptions import ObjectDoesNotExist, ValidationError
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


def _map_service_error(exc: Exception) -> ToolError:
    if isinstance(exc, ObjectDoesNotExist):
        return ToolError("Not found")
    if isinstance(exc, ValidationError):
        return ToolError(str(exc))
    if isinstance(exc, PermissionError):
        return ToolError(str(exc))
    return ToolError("Request failed")


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
        _ = organization_id
        try:
            result = DeviceService.get_devices(organization_id=ctx.organization_id)
            write_audit(ctx, "get_devices", "success")
            return result
        except Exception as exc:
            write_audit(ctx, "get_devices", "failure", str(exc))
            raise ToolError("Failed to list devices") from exc

    @mcp.tool()
    def create_device(
        name: str,
        serial_number: str = "",
        device_type: str = "laptop",
        status: str = "available",
        organization_id: int | None = None,
    ) -> dict:
        """Create a device in the authenticated organization."""
        ctx = _auth_context()
        _require(ctx, "retriever.devices.write")
        _ = organization_id
        try:
            result = DeviceService.create_device(
                ctx.organization_id,
                name=name,
                serial_number=serial_number,
                device_type=device_type,
                status=status,
            )
            write_audit(ctx, "create_device", "success", result["name"])
            return result
        except Exception as exc:
            write_audit(ctx, "create_device", "failure", str(exc))
            raise _map_service_error(exc) from exc

    @mcp.tool()
    def update_device(
        device_id: int,
        name: str | None = None,
        serial_number: str | None = None,
        device_type: str | None = None,
        status: str | None = None,
        organization_id: int | None = None,
    ) -> dict:
        """Update a device in the authenticated organization."""
        ctx = _auth_context()
        _require(ctx, "retriever.devices.write")
        _ = organization_id
        try:
            result = DeviceService.update_device(
                ctx.organization_id,
                device_id,
                name=name,
                serial_number=serial_number,
                device_type=device_type,
                status=status,
            )
            write_audit(ctx, "update_device", "success", str(device_id))
            return result
        except Exception as exc:
            write_audit(ctx, "update_device", "failure", str(exc))
            raise _map_service_error(exc) from exc

    @mcp.tool()
    def delete_device(
        device_id: int,
        organization_id: int | None = None,
    ) -> dict:
        """Delete a device in the authenticated organization."""
        ctx = _auth_context()
        _require(ctx, "retriever.devices.write")
        _ = organization_id
        try:
            DeviceService.delete_device(ctx.organization_id, device_id)
            write_audit(ctx, "delete_device", "success", str(device_id))
            return {"deleted": True, "device_id": device_id}
        except Exception as exc:
            write_audit(ctx, "delete_device", "failure", str(exc))
            raise _map_service_error(exc) from exc

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
    def create_deployment_order(
        reference: str,
        status: str = "pending",
        notes: str = "",
        device_id: int | None = None,
        organization_id: int | None = None,
    ) -> dict:
        """Create a deployment order in the authenticated organization."""
        ctx = _auth_context()
        _require(ctx, "retriever.orders.write")
        _ = organization_id
        try:
            result = OrderService.create_deployment_order(
                ctx.organization_id,
                reference=reference,
                status=status,
                notes=notes,
                device_id=device_id,
            )
            write_audit(ctx, "create_deployment_order", "success", result["reference"])
            return result
        except Exception as exc:
            write_audit(ctx, "create_deployment_order", "failure", str(exc))
            raise _map_service_error(exc) from exc

    @mcp.tool()
    def update_deployment_order(
        order_id: int,
        reference: str | None = None,
        status: str | None = None,
        notes: str | None = None,
        device_id: int | None = None,
        clear_device: bool = False,
        organization_id: int | None = None,
    ) -> dict:
        """Update a deployment order in the authenticated organization."""
        ctx = _auth_context()
        _require(ctx, "retriever.orders.write")
        _ = organization_id
        try:
            result = OrderService.update_deployment_order(
                ctx.organization_id,
                order_id,
                reference=reference,
                status=status,
                notes=notes,
                device_id=device_id,
                clear_device=clear_device,
            )
            write_audit(ctx, "update_deployment_order", "success", str(order_id))
            return result
        except Exception as exc:
            write_audit(ctx, "update_deployment_order", "failure", str(exc))
            raise _map_service_error(exc) from exc

    @mcp.tool()
    def delete_deployment_order(
        order_id: int,
        organization_id: int | None = None,
    ) -> dict:
        """Delete a deployment order in the authenticated organization."""
        ctx = _auth_context()
        _require(ctx, "retriever.orders.write")
        _ = organization_id
        try:
            OrderService.delete_deployment_order(ctx.organization_id, order_id)
            write_audit(ctx, "delete_deployment_order", "success", str(order_id))
            return {"deleted": True, "order_id": order_id}
        except Exception as exc:
            write_audit(ctx, "delete_deployment_order", "failure", str(exc))
            raise _map_service_error(exc) from exc

    @mcp.tool()
    def create_return_order(
        reference: str,
        status: str = "pending",
        notes: str = "",
        device_id: int | None = None,
        organization_id: int | None = None,
    ) -> dict:
        """Create a return order in the authenticated organization."""
        ctx = _auth_context()
        _require(ctx, "retriever.orders.write")
        _ = organization_id
        try:
            result = OrderService.create_return_order(
                ctx.organization_id,
                reference=reference,
                status=status,
                notes=notes,
                device_id=device_id,
            )
            write_audit(ctx, "create_return_order", "success", result["reference"])
            return result
        except Exception as exc:
            write_audit(ctx, "create_return_order", "failure", str(exc))
            raise _map_service_error(exc) from exc

    @mcp.tool()
    def update_return_order(
        order_id: int,
        reference: str | None = None,
        status: str | None = None,
        notes: str | None = None,
        device_id: int | None = None,
        clear_device: bool = False,
        organization_id: int | None = None,
    ) -> dict:
        """Update a return order in the authenticated organization."""
        ctx = _auth_context()
        _require(ctx, "retriever.orders.write")
        _ = organization_id
        try:
            result = OrderService.update_return_order(
                ctx.organization_id,
                order_id,
                reference=reference,
                status=status,
                notes=notes,
                device_id=device_id,
                clear_device=clear_device,
            )
            write_audit(ctx, "update_return_order", "success", str(order_id))
            return result
        except Exception as exc:
            write_audit(ctx, "update_return_order", "failure", str(exc))
            raise _map_service_error(exc) from exc

    @mcp.tool()
    def delete_return_order(
        order_id: int,
        organization_id: int | None = None,
    ) -> dict:
        """Delete a return order in the authenticated organization."""
        ctx = _auth_context()
        _require(ctx, "retriever.orders.write")
        _ = organization_id
        try:
            OrderService.delete_return_order(ctx.organization_id, order_id)
            write_audit(ctx, "delete_return_order", "success", str(order_id))
            return {"deleted": True, "order_id": order_id}
        except Exception as exc:
            write_audit(ctx, "delete_return_order", "failure", str(exc))
            raise _map_service_error(exc) from exc

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
            write_audit(
                ctx, "create_test_deployment_order", "success", result["reference"]
            )
            return result
        except Exception as exc:
            write_audit(ctx, "create_test_deployment_order", "failure", str(exc))
            raise _map_service_error(exc) from exc
