from django.conf import settings
from django.db import models


class Device(models.Model):
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="devices",
    )
    name = models.CharField(max_length=255)
    serial_number = models.CharField(max_length=128, blank=True, default="")
    device_type = models.CharField(max_length=64, blank=True, default="laptop")
    status = models.CharField(max_length=64, default="available")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return f"{self.name} ({self.organization})"


class DeploymentOrder(models.Model):
    class Status(models.TextChoices):
        DRAFT = "draft", "Draft"
        PENDING = "pending", "Pending"
        COMPLETED = "completed", "Completed"

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="deployment_orders",
    )
    reference = models.CharField(max_length=64)
    device = models.ForeignKey(
        Device,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="deployment_orders",
    )
    status = models.CharField(
        max_length=32, choices=Status.choices, default=Status.PENDING
    )
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.reference


class ReturnOrder(models.Model):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        RECEIVED = "received", "Received"
        CLOSED = "closed", "Closed"

    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="return_orders",
    )
    reference = models.CharField(max_length=64)
    device = models.ForeignKey(
        Device,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="return_orders",
    )
    status = models.CharField(
        max_length=32, choices=Status.choices, default=Status.PENDING
    )
    notes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return self.reference


class AuditLog(models.Model):
    user_id = models.IntegerField(null=True, blank=True)
    organization_id = models.IntegerField(null=True, blank=True)
    oauth_client = models.CharField(max_length=255, blank=True, default="")
    tool = models.CharField(max_length=128)
    status = models.CharField(max_length=32)
    detail = models.CharField(max_length=512, blank=True, default="")
    timestamp = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-timestamp"]

    def __str__(self) -> str:
        return f"{self.tool}:{self.status}@{self.timestamp}"
