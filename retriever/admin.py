from django.contrib import admin

from retriever.models import AuditLog, DeploymentOrder, Device, ReturnOrder


@admin.register(Device)
class DeviceAdmin(admin.ModelAdmin):
    list_display = ("id", "name", "organization", "status", "serial_number")
    list_filter = ("organization", "status")


@admin.register(DeploymentOrder)
class DeploymentOrderAdmin(admin.ModelAdmin):
    list_display = ("id", "reference", "organization", "status", "created_at")
    list_filter = ("organization", "status")


@admin.register(ReturnOrder)
class ReturnOrderAdmin(admin.ModelAdmin):
    list_display = ("id", "reference", "organization", "status", "created_at")
    list_filter = ("organization", "status")


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "tool",
        "status",
        "user_id",
        "organization_id",
        "oauth_client",
        "timestamp",
    )
    list_filter = ("tool", "status")
    readonly_fields = (
        "user_id",
        "organization_id",
        "oauth_client",
        "tool",
        "status",
        "detail",
        "timestamp",
    )
