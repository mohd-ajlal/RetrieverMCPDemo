from django.conf import settings
from django.db import models
from oauth2_provider.models import AccessToken, Application, Grant


class OAuthAuthorizationContext(models.Model):
    """
    Binds an OAuth grant/token to a Retriever organization at consent time.

    Organization is derived from the authenticated Retriever user — never from
    client-supplied organization_id.
    """

    grant = models.OneToOneField(
        Grant,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="retriever_context",
    )
    access_token = models.OneToOneField(
        AccessToken,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name="retriever_context",
    )
    application = models.ForeignKey(
        Application,
        on_delete=models.CASCADE,
        related_name="authorization_contexts",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="oauth_contexts",
    )
    organization = models.ForeignKey(
        "organizations.Organization",
        on_delete=models.CASCADE,
        related_name="oauth_contexts",
    )
    scopes = models.TextField(blank=True, default="")
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]

    def __str__(self) -> str:
        return f"{self.application.name} -> {self.organization} ({self.user})"
