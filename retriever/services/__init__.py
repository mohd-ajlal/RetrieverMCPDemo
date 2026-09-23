from __future__ import annotations

from dataclasses import dataclass

from django.db import transaction

from retriever.models import AuditLog, DeploymentOrder, Device, ReturnOrder


@dataclass(frozen=True)
class AuthContext:
    user_id: int
    organization_id: int
    scopes: frozenset[str]
    oauth_client: str
    username: str = ""


def _require_scope(ctx: AuthContext, scope: str) -> None:
    if scope not in ctx.scopes:
        raise PermissionError(f"insufficient_scope:{scope}")


def write_audit(
    ctx: AuthContext,
    tool: str,
    status: str,
    detail: str = "",
) -> None:
    AuditLog.objects.create(
        user_id=ctx.user_id,
        organization_id=ctx.organization_id,
        oauth_client=ctx.oauth_client,
        tool=tool,
        status=status,
        detail=detail[:512],
    )


class DeviceService:
    @staticmethod
    def get_devices(organization_id: int) -> list[dict]:
        qs = Device.objects.filter(organization_id=organization_id)
        return [
            {
                "id": d.id,
                "name": d.name,
                "serial_number": d.serial_number,
                "device_type": d.device_type,
                "status": d.status,
            }
            for d in qs
        ]


class OrderService:
    @staticmethod
    def get_deployment_orders(organization_id: int) -> list[dict]:
        qs = DeploymentOrder.objects.filter(organization_id=organization_id)
        return [
            {
                "id": o.id,
                "reference": o.reference,
                "status": o.status,
                "device_id": o.device_id,
                "notes": o.notes,
            }
            for o in qs
        ]

    @staticmethod
    def get_return_orders(organization_id: int) -> list[dict]:
        qs = ReturnOrder.objects.filter(organization_id=organization_id)
        return [
            {
                "id": o.id,
                "reference": o.reference,
                "status": o.status,
                "device_id": o.device_id,
                "notes": o.notes,
            }
            for o in qs
        ]

    @staticmethod
    @transaction.atomic
    def create_test_deployment_order(
        organization_id: int,
        notes: str = "Created via MCP demo tool",
    ) -> dict:
        count = DeploymentOrder.objects.filter(organization_id=organization_id).count()
        device = Device.objects.filter(organization_id=organization_id).first()
        order = DeploymentOrder.objects.create(
            organization_id=organization_id,
            reference=f"DEP-MCP-{count + 1:04d}",
            device=device,
            status=DeploymentOrder.Status.PENDING,
            notes=notes,
        )
        return {
            "id": order.id,
            "reference": order.reference,
            "status": order.status,
            "device_id": order.device_id,
            "notes": order.notes,
        }
