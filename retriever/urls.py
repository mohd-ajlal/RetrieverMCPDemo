from django.urls import path

from retriever import views

urlpatterns = [
    path("devices/", views.devices_view, name="devices"),
    path("devices/new/", views.device_create_view, name="device_create"),
    path("devices/<int:device_id>/edit/", views.device_edit_view, name="device_edit"),
    path(
        "devices/<int:device_id>/delete/",
        views.device_delete_view,
        name="device_delete",
    ),
    path("orders/", views.orders_view, name="orders"),
    path(
        "orders/deployments/new/",
        views.deployment_create_view,
        name="deployment_create",
    ),
    path(
        "orders/deployments/<int:order_id>/edit/",
        views.deployment_edit_view,
        name="deployment_edit",
    ),
    path(
        "orders/deployments/<int:order_id>/delete/",
        views.deployment_delete_view,
        name="deployment_delete",
    ),
    path("orders/returns/new/", views.return_create_view, name="return_create"),
    path(
        "orders/returns/<int:order_id>/edit/",
        views.return_edit_view,
        name="return_edit",
    ),
    path(
        "orders/returns/<int:order_id>/delete/",
        views.return_delete_view,
        name="return_delete",
    ),
]
