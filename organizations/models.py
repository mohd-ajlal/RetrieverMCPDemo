from django.conf import settings
from django.contrib.auth.models import User
from django.db import models
from django.db.models.signals import post_save
from django.dispatch import receiver


class Organization(models.Model):
    name = models.CharField(max_length=255, unique=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name


class OrganizationMembership(models.Model):
    class Role(models.TextChoices):
        OWNER = "owner", "Owner"
        ADMIN = "admin", "Admin"
        MEMBER = "member", "Member"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    organization = models.ForeignKey(
        Organization,
        on_delete=models.CASCADE,
        related_name="memberships",
    )
    role = models.CharField(max_length=32, choices=Role.choices, default=Role.MEMBER)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ("user", "organization")
        ordering = ["organization__name"]

    def __str__(self) -> str:
        return f"{self.user} @ {self.organization} ({self.role})"


class UserProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="profile",
    )
    active_organization = models.ForeignKey(
        Organization,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="active_users",
    )

    def __str__(self) -> str:
        return f"Profile({self.user})"

    def ensure_active_organization(self) -> Organization | None:
        if self.active_organization_id:
            membership = OrganizationMembership.objects.filter(
                user=self.user, organization_id=self.active_organization_id
            ).exists()
            if membership:
                return self.active_organization
        membership = (
            OrganizationMembership.objects.filter(user=self.user)
            .select_related("organization")
            .first()
        )
        if membership:
            self.active_organization = membership.organization
            self.save(update_fields=["active_organization"])
            return self.active_organization
        return None


@receiver(post_save, sender=User)
def create_user_profile(sender, instance: User, created: bool, **kwargs) -> None:
    if created:
        UserProfile.objects.get_or_create(user=instance)
