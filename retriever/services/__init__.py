from __future__ import annotations

from dataclasses import dataclass

from django.core.exceptions import ObjectDoesNotExist, ValidationError
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


def _device_dict(d: Device) -> dict:
    return {
        "id": d.id,
        "name": d.name,
        "serial_number": d.serial_number,
        "device_type": d.device_type,
        "status": d.status,
    }


def _deployment_dict(o: DeploymentOrder) -> dict:
    return {
        "id": o.id,
        "reference": o.reference,
        "status": o.status,
        "device_id": o.device_id,
        "notes": o.notes,
    }


def _return_dict(o: ReturnOrder) -> dict:
    return {
        "id": o.id,
        "reference": o.reference,
        "status": o.status,
        "device_id": o.device_id,
        "notes": o.notes,
    }


def _resolve_org_device(organization_id: int, device_id: int | None) -> Device | None:
    if device_id is None:
        return None
    device = Device.objects.filter(id=device_id, organization_id=organization_id).first()
    if device is None:
        raise ValidationError("device_not_in_organization")
    return device


def _validate_status(value: str, choices) -> str:
    allowed = {c.value for c in choices}
    if value not in allowed:
        raise ValidationError(f"invalid_status:{value}")
    return value


class DeviceService:
    @staticmethod
    def get_devices(organization_id: int) -> list[dict]:
        qs = Device.objects.filter(organization_id=organization_id)
        return [_device_dict(d) for d in qs]

    @staticmethod
    def get_device(organization_id: int, device_id: int) -> dict:
        device = Device.objects.filter(
            id=device_id, organization_id=organization_id
        ).first()
        if device is None:
            raise ObjectDoesNotExist("device_not_found")
        return _device_dict(device)

    @staticmethod
    @transaction.atomic
    def create_device(
        organization_id: int,
        *,
        name: str,
        serial_number: str = "",
        device_type: str = "laptop",
        status: str = "available",
    ) -> dict:
        device = Device.objects.create(
            organization_id=organization_id,
            name=name.strip(),
            serial_number=(serial_number or "").strip(),
            device_type=(device_type or "laptop").strip(),
            status=(status or "available").strip(),
        )
        return _device_dict(device)

    @staticmethod
    @transaction.atomic
    def update_device(
        organization_id: int,
        device_id: int,
        *,
        name: str | None = None,
        serial_number: str | None = None,
        device_type: str | None = None,
        status: str | None = None,
    ) -> dict:
        device = Device.objects.filter(
            id=device_id, organization_id=organization_id
        ).first()
        if device is None:
            raise ObjectDoesNotExist("device_not_found")
        if name is not None:
            device.name = name.strip()
        if serial_number is not None:
            device.serial_number = serial_number.strip()
        if device_type is not None:
            device.device_type = device_type.strip()
        if status is not None:
            device.status = status.strip()
        device.save()
        return _device_dict(device)

    @staticmethod
    @transaction.atomic
    def delete_device(organization_id: int, device_id: int) -> None:
        deleted, _ = Device.objects.filter(
            id=device_id, organization_id=organization_id
        ).delete()
        if not deleted:
            raise ObjectDoesNotExist("device_not_found")


class OrderService:
    @staticmethod
    def get_deployment_orders(organization_id: int) -> list[dict]:
        qs = DeploymentOrder.objects.filter(organization_id=organization_id)
        return [_deployment_dict(o) for o in qs]

    @staticmethod
    def get_return_orders(organization_id: int) -> list[dict]:
        qs = ReturnOrder.objects.filter(organization_id=organization_id)
        return [_return_dict(o) for o in qs]

    @staticmethod
    def get_deployment_order(organization_id: int, order_id: int) -> dict:
        order = DeploymentOrder.objects.filter(
            id=order_id, organization_id=organization_id
        ).first()
        if order is None:
            raise ObjectDoesNotExist("deployment_order_not_found")
        return _deployment_dict(order)

    @staticmethod
    def get_return_order(organization_id: int, order_id: int) -> dict:
        order = ReturnOrder.objects.filter(
            id=order_id, organization_id=organization_id
        ).first()
        if order is None:
            raise ObjectDoesNotExist("return_order_not_found")
        return _return_dict(order)

    @staticmethod
    @transaction.atomic
    def create_deployment_order(
        organization_id: int,
        *,
        reference: str,
        status: str = DeploymentOrder.Status.PENDING,
        notes: str = "",
        device_id: int | None = None,
    ) -> dict:
        status = _validate_status(status, DeploymentOrder.Status)
        device = _resolve_org_device(organization_id, device_id)
        order = DeploymentOrder.objects.create(
            organization_id=organization_id,
            reference=reference.strip(),
            device=device,
            status=status,
            notes=notes or "",
        )
        return _deployment_dict(order)

    @staticmethod
    @transaction.atomic
    def update_deployment_order(
        organization_id: int,
        order_id: int,
        *,
        reference: str | None = None,
        status: str | None = None,
        notes: str | None = None,
        device_id: int | None = None,
        clear_device: bool = False,
    ) -> dict:
        order = DeploymentOrder.objects.filter(
            id=order_id, organization_id=organization_id
        ).first()
        if order is None:
            raise ObjectDoesNotExist("deployment_order_not_found")
        if reference is not None:
            order.reference = reference.strip()
        if status is not None:
            order.status = _validate_status(status, DeploymentOrder.Status)
        if notes is not None:
            order.notes = notes
        if clear_device:
            order.device = None
        elif device_id is not None:
            order.device = _resolve_org_device(organization_id, device_id)
        order.save()
        return _deployment_dict(order)

    @staticmethod
    @transaction.atomic
    def delete_deployment_order(organization_id: int, order_id: int) -> None:
        deleted, _ = DeploymentOrder.objects.filter(
            id=order_id, organization_id=organization_id
        ).delete()
        if not deleted:
            raise ObjectDoesNotExist("deployment_order_not_found")

    @staticmethod
    @transaction.atomic
    def create_return_order(
        organization_id: int,
        *,
        reference: str,
        status: str = ReturnOrder.Status.PENDING,
        notes: str = "",
        device_id: int | None = None,
    ) -> dict:
        status = _validate_status(status, ReturnOrder.Status)
        device = _resolve_org_device(organization_id, device_id)
        order = ReturnOrder.objects.create(
            organization_id=organization_id,
            reference=reference.strip(),
            device=device,
            status=status,
            notes=notes or "",
        )
        return _return_dict(order)

    @staticmethod
    @transaction.atomic
    def update_return_order(
        organization_id: int,
        order_id: int,
        *,
        reference: str | None = None,
        status: str | None = None,
        notes: str | None = None,
        device_id: int | None = None,
        clear_device: bool = False,
    ) -> dict:
        order = ReturnOrder.objects.filter(
            id=order_id, organization_id=organization_id
        ).first()
        if order is None:
            raise ObjectDoesNotExist("return_order_not_found")
        if reference is not None:
            order.reference = reference.strip()
        if status is not None:
            order.status = _validate_status(status, ReturnOrder.Status)
        if notes is not None:
            order.notes = notes
        if clear_device:
            order.device = None
        elif device_id is not None:
            order.device = _resolve_org_device(organization_id, device_id)
        order.save()
        return _return_dict(order)

    @staticmethod
    @transaction.atomic
    def delete_return_order(organization_id: int, order_id: int) -> None:
        deleted, _ = ReturnOrder.objects.filter(
            id=order_id, organization_id=organization_id
        ).delete()
        if not deleted:
            raise ObjectDoesNotExist("return_order_not_found")

    @staticmethod
    @transaction.atomic
    def create_test_deployment_order(
        organization_id: int,
        notes: str = "Created via MCP demo tool",
    ) -> dict:
        count = DeploymentOrder.objects.filter(organization_id=organization_id).count()
        device = Device.objects.filter(organization_id=organization_id).first()
        return OrderService.create_deployment_order(
            organization_id,
            reference=f"DEP-MCP-{count + 1:04d}",
            status=DeploymentOrder.Status.PENDING,
            notes=notes,
            device_id=device.id if device else None,
        )
