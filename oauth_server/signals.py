"""Signal handlers to bind organization context onto issued access tokens."""

from django.db.models.signals import post_save
from django.dispatch import receiver
from oauth2_provider.models import AccessToken

from oauth_server.models import OAuthAuthorizationContext


@receiver(post_save, sender=AccessToken)
def bind_org_context_to_token(sender, instance: AccessToken, created: bool, **kwargs):
    if not created:
        return
    existing = OAuthAuthorizationContext.objects.filter(access_token=instance).first()
    if existing:
        return
    pending = (
        OAuthAuthorizationContext.objects.filter(
            user=instance.user,
            application=instance.application,
            access_token__isnull=True,
        )
        .order_by("-created_at")
        .first()
    )
    if pending is None:
        return
    # Prefer linking the grant's context; clone if grant already linked elsewhere
    if pending.grant_id and not pending.access_token_id:
        pending.access_token = instance
        pending.scopes = instance.scope or pending.scopes
        pending.save(update_fields=["access_token", "scopes"])
    else:
        OAuthAuthorizationContext.objects.create(
            application=instance.application,
            user=instance.user,
            organization=pending.organization,
            scopes=instance.scope or pending.scopes,
            access_token=instance,
        )
