from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from organizations.models import Organization, UserProfile
from retriever.forms import DeploymentOrderForm, DeviceForm, ReturnOrderForm
from retriever.models import DeploymentOrder, Device, ReturnOrder
from retriever.services import DeviceService, OrderService


def _active_org(request: HttpRequest) -> Organization | None:
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    return profile.ensure_active_organization()


def _require_org(request: HttpRequest) -> Organization | HttpResponse:
    org = _active_org(request)
    if org is None:
        messages.error(request, "Select or create an organization before managing inventory.")
        return redirect("dashboard")
    return org


@login_required
def devices_view(request: HttpRequest) -> HttpResponse:
    org = _active_org(request)
    devices = Device.objects.filter(organization=org) if org else Device.objects.none()
    return render(
        request,
        "retriever/devices.html",
        {"page": "devices", "devices": devices},
    )


@login_required
@require_http_methods(["GET", "POST"])
def device_create_view(request: HttpRequest) -> HttpResponse:
    org = _require_org(request)
    if not isinstance(org, Organization):
        return org
    form = DeviceForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        DeviceService.create_device(
            org.id,
            name=form.cleaned_data["name"],
            serial_number=form.cleaned_data.get("serial_number") or "",
            device_type=form.cleaned_data.get("device_type") or "laptop",
            status=form.cleaned_data.get("status") or "available",
        )
        messages.success(request, "Device created.")
        return redirect("devices")
    return render(
        request,
        "retriever/device_form.html",
        {
            "page": "devices",
            "form": form,
            "title": "Add device",
            "submit_label": "Create device",
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def device_edit_view(request: HttpRequest, device_id: int) -> HttpResponse:
    org = _require_org(request)
    if not isinstance(org, Organization):
        return org
    device = get_object_or_404(Device, pk=device_id, organization=org)
    form = DeviceForm(request.POST or None, instance=device)
    if request.method == "POST" and form.is_valid():
        DeviceService.update_device(
            org.id,
            device.id,
            name=form.cleaned_data["name"],
            serial_number=form.cleaned_data.get("serial_number") or "",
            device_type=form.cleaned_data.get("device_type") or "laptop",
            status=form.cleaned_data.get("status") or "available",
        )
        messages.success(request, "Device updated.")
        return redirect("devices")
    return render(
        request,
        "retriever/device_form.html",
        {
            "page": "devices",
            "form": form,
            "title": "Edit device",
            "submit_label": "Save changes",
            "device": device,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def device_delete_view(request: HttpRequest, device_id: int) -> HttpResponse:
    org = _require_org(request)
    if not isinstance(org, Organization):
        return org
    device = get_object_or_404(Device, pk=device_id, organization=org)
    if request.method == "POST":
        DeviceService.delete_device(org.id, device.id)
        messages.success(request, f"Deleted device “{device.name}”.")
        return redirect("devices")
    return render(
        request,
        "retriever/confirm_delete.html",
        {
            "page": "devices",
            "object_label": f"device “{device.name}”",
            "cancel_url": "devices",
        },
    )


@login_required
def orders_view(request: HttpRequest) -> HttpResponse:
    org = _active_org(request)
    deployments = (
        DeploymentOrder.objects.filter(organization=org)
        if org
        else DeploymentOrder.objects.none()
    )
    returns = (
        ReturnOrder.objects.filter(organization=org)
        if org
        else ReturnOrder.objects.none()
    )
    return render(
        request,
        "retriever/orders.html",
        {
            "page": "orders",
            "deployment_orders": deployments,
            "return_orders": returns,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def deployment_create_view(request: HttpRequest) -> HttpResponse:
    org = _require_org(request)
    if not isinstance(org, Organization):
        return org
    form = DeploymentOrderForm(request.POST or None, organization=org)
    if request.method == "POST" and form.is_valid():
        OrderService.create_deployment_order(
            org.id,
            reference=form.cleaned_data["reference"],
            status=form.cleaned_data["status"],
            notes=form.cleaned_data.get("notes") or "",
            device_id=form.cleaned_data["device"].id
            if form.cleaned_data.get("device")
            else None,
        )
        messages.success(request, "Deployment order created.")
        return redirect("orders")
    return render(
        request,
        "retriever/order_form.html",
        {
            "page": "orders",
            "form": form,
            "title": "New deployment order",
            "submit_label": "Create order",
            "order_kind": "deployment",
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def deployment_edit_view(request: HttpRequest, order_id: int) -> HttpResponse:
    org = _require_org(request)
    if not isinstance(org, Organization):
        return org
    order = get_object_or_404(DeploymentOrder, pk=order_id, organization=org)
    form = DeploymentOrderForm(request.POST or None, instance=order, organization=org)
    if request.method == "POST" and form.is_valid():
        device = form.cleaned_data.get("device")
        OrderService.update_deployment_order(
            org.id,
            order.id,
            reference=form.cleaned_data["reference"],
            status=form.cleaned_data["status"],
            notes=form.cleaned_data.get("notes") or "",
            device_id=device.id if device else None,
            clear_device=device is None,
        )
        messages.success(request, "Deployment order updated.")
        return redirect("orders")
    return render(
        request,
        "retriever/order_form.html",
        {
            "page": "orders",
            "form": form,
            "title": "Edit deployment order",
            "submit_label": "Save changes",
            "order_kind": "deployment",
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def deployment_delete_view(request: HttpRequest, order_id: int) -> HttpResponse:
    org = _require_org(request)
    if not isinstance(org, Organization):
        return org
    order = get_object_or_404(DeploymentOrder, pk=order_id, organization=org)
    if request.method == "POST":
        OrderService.delete_deployment_order(org.id, order.id)
        messages.success(request, f"Deleted deployment order {order.reference}.")
        return redirect("orders")
    return render(
        request,
        "retriever/confirm_delete.html",
        {
            "page": "orders",
            "object_label": f"deployment order {order.reference}",
            "cancel_url": "orders",
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def return_create_view(request: HttpRequest) -> HttpResponse:
    org = _require_org(request)
    if not isinstance(org, Organization):
        return org
    form = ReturnOrderForm(request.POST or None, organization=org)
    if request.method == "POST" and form.is_valid():
        OrderService.create_return_order(
            org.id,
            reference=form.cleaned_data["reference"],
            status=form.cleaned_data["status"],
            notes=form.cleaned_data.get("notes") or "",
            device_id=form.cleaned_data["device"].id
            if form.cleaned_data.get("device")
            else None,
        )
        messages.success(request, "Return order created.")
        return redirect("orders")
    return render(
        request,
        "retriever/order_form.html",
        {
            "page": "orders",
            "form": form,
            "title": "New return order",
            "submit_label": "Create order",
            "order_kind": "return",
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def return_edit_view(request: HttpRequest, order_id: int) -> HttpResponse:
    org = _require_org(request)
    if not isinstance(org, Organization):
        return org
    order = get_object_or_404(ReturnOrder, pk=order_id, organization=org)
    form = ReturnOrderForm(request.POST or None, instance=order, organization=org)
    if request.method == "POST" and form.is_valid():
        device = form.cleaned_data.get("device")
        OrderService.update_return_order(
            org.id,
            order.id,
            reference=form.cleaned_data["reference"],
            status=form.cleaned_data["status"],
            notes=form.cleaned_data.get("notes") or "",
            device_id=device.id if device else None,
            clear_device=device is None,
        )
        messages.success(request, "Return order updated.")
        return redirect("orders")
    return render(
        request,
        "retriever/order_form.html",
        {
            "page": "orders",
            "form": form,
            "title": "Edit return order",
            "submit_label": "Save changes",
            "order_kind": "return",
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def return_delete_view(request: HttpRequest, order_id: int) -> HttpResponse:
    org = _require_org(request)
    if not isinstance(org, Organization):
        return org
    order = get_object_or_404(ReturnOrder, pk=order_id, organization=org)
    if request.method == "POST":
        OrderService.delete_return_order(org.id, order.id)
        messages.success(request, f"Deleted return order {order.reference}.")
        return redirect("orders")
    return render(
        request,
        "retriever/confirm_delete.html",
        {
            "page": "orders",
            "object_label": f"return order {order.reference}",
            "cancel_url": "orders",
        },
    )
