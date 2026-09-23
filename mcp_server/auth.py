"""In-process OAuth access token verification against django-oauth-toolkit."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from django.conf import settings
from django.utils import timezone as django_timezone
from fastmcp.server.auth import AccessToken, TokenVerifier
from oauth2_provider.models import AccessToken as DOTAccessToken

from oauth_server.models import OAuthAuthorizationContext

logger = logging.getLogger(__name__)


class DjangoAccessTokenVerifier(TokenVerifier):
    """
    Validate opaque DOT access tokens via ORM (no HTTP introspection loop).

    Suitable for same-deployment AS + RS on serverless platforms.
    """

    def __init__(self, **kwargs):
        super().__init__(
            required_scopes=None,
            resource_base_url=getattr(settings, "MCP_RESOURCE_URL", None),
            **{k: v for k, v in kwargs.items() if k in ("base_url",)},
        )

    async def verify_token(self, token: str) -> AccessToken | None:
        if not token:
            return None
        try:
            return await self._verify(token)
        except Exception:
            logger.exception("token verification failed")
            return None

    async def _verify(self, token: str) -> AccessToken | None:
        # ORM calls are sync; run in thread if needed — Django sync_to_async
        from asgiref.sync import sync_to_async

        return await sync_to_async(self._verify_sync, thread_sensitive=True)(token)

    def _verify_sync(self, token: str) -> AccessToken | None:
        try:
            dot_token = (
                DOTAccessToken.objects.select_related("application", "user")
                .filter(token=token)
                .first()
            )
        except Exception:
            logger.exception("token lookup error")
            return None

        if dot_token is None:
            return None
        if dot_token.is_expired():
            return None

        # Audience / resource validation (RFC 8707)
        expected = getattr(settings, "MCP_RESOURCE_URL", "").rstrip("/")
        audiences: list[str] = []
        resource_attr = getattr(dot_token, "resource", None)
        if resource_attr:
            if isinstance(resource_attr, str):
                audiences = [a.strip() for a in resource_attr.split() if a.strip()]
            elif isinstance(resource_attr, (list, tuple)):
                audiences = [str(a).strip() for a in resource_attr if a]

        if expected:
            if audiences:
                normalized = {a.rstrip("/") for a in audiences}
                if expected not in normalized:
                    logger.info("token audience mismatch")
                    return None
            elif getattr(settings, "MCP_REQUIRE_AUDIENCE", False):
                logger.info("token missing audience")
                return None

        scopes = [s for s in (dot_token.scope or "").split() if s]

        ctx = (
            OAuthAuthorizationContext.objects.filter(access_token=dot_token)
            .select_related("organization")
            .first()
        )
        if ctx is None:
            # Try grant linkage then attach
            grant_ctx = (
                OAuthAuthorizationContext.objects.filter(
                    user=dot_token.user,
                    application=dot_token.application,
                    access_token__isnull=True,
                )
                .order_by("-created_at")
                .first()
            )
            if grant_ctx is not None:
                grant_ctx.access_token = dot_token
                grant_ctx.save(update_fields=["access_token"])
                ctx = grant_ctx

        org_id = ctx.organization_id if ctx else None
        if org_id is None:
            # Fallback to user's active organization for resilience
            from organizations.models import UserProfile

            profile = UserProfile.objects.filter(user=dot_token.user).first()
            if profile:
                org = profile.ensure_active_organization()
                org_id = org.id if org else None

        if org_id is None:
            logger.info("token has no organization context")
            return None

        expires_at = None
        if dot_token.expires:
            exp = dot_token.expires
            if django_timezone.is_naive(exp):
                exp = django_timezone.make_aware(exp, timezone.utc)
            expires_at = int(exp.timestamp())

        client_id = dot_token.application.client_id if dot_token.application else ""
        client_name = (
            dot_token.application.name if dot_token.application else "unknown"
        )

        return AccessToken(
            token=token,
            client_id=client_id,
            scopes=scopes,
            expires_at=expires_at,
            resource=expected or None,
            subject=str(dot_token.user_id),
            claims={
                "user_id": dot_token.user_id,
                "username": dot_token.user.get_username(),
                "organization_id": org_id,
                "oauth_client": client_name,
                "scope": scopes,
            },
        )
