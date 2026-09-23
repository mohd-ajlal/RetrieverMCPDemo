from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import render

from organizations.models import UserProfile
from retriever.models import DeploymentOrder, Device, ReturnOrder


@login_required
def devices_view(request: HttpRequest) -> HttpResponse:
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    org = profile.ensure_active_organization()
    devices = Device.objects.filter(organization=org) if org else Device.objects.none()
    return render(
        request,
        "retriever/devices.html",
        {"page": "devices", "devices": devices},
    )


@login_required
def orders_view(request: HttpRequest) -> HttpResponse:
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    org = profile.ensure_active_organization()
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
