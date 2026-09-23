from __future__ import annotations

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse, JsonResponse
from django.shortcuts import redirect, render
from django.views.decorators.csrf import csrf_exempt
from django.views.decorators.http import require_GET, require_http_methods
from django.utils.decorators import method_decorator
from oauth2_provider.models import AccessToken, Application, Grant, RefreshToken
from oauth2_provider.views import AuthorizationView as DOTAuthorizationView

from oauth_server.models import OAuthAuthorizationContext
from organizations.models import UserProfile


SCOPE_DESCRIPTIONS = getattr(settings, "RETRIEVER_SCOPES", {})


def _public_base(request: HttpRequest) -> str:
    configured = getattr(settings, "PUBLIC_BASE_URL", "").rstrip("/")
    if configured and not settings.DEBUG:
        return configured
    return request.build_absolute_uri("/").rstrip("/")


def _mcp_resource_url(request: HttpRequest) -> str:
    configured = getattr(settings, "MCP_RESOURCE_URL", "").rstrip("/")
    if configured:
        return configured
    return f"{_public_base(request)}/mcp"


@require_GET
def oauth_authorization_server_metadata(request: HttpRequest) -> JsonResponse:
    base = _public_base(request)
    scopes = list(settings.OAUTH2_PROVIDER.get("SCOPES", {}).keys())
    return JsonResponse(
        {
            "issuer": base,
            "authorization_endpoint": f"{base}/o/authorize/",
            "token_endpoint": f"{base}/o/token/",
            "revocation_endpoint": f"{base}/o/revoke_token/",
            "introspection_endpoint": f"{base}/o/introspect/",
            "registration_endpoint": f"{base}/o/register/",
            "response_types_supported": ["code"],
            "grant_types_supported": [
                "authorization_code",
                "refresh_token",
            ],
            "code_challenge_methods_supported": ["S256"],
            "token_endpoint_auth_methods_supported": [
                "client_secret_basic",
                "client_secret_post",
                "none",
            ],
            "scopes_supported": scopes,
            "revocation_endpoint_auth_methods_supported": [
                "client_secret_basic",
                "client_secret_post",
            ],
            "introspection_endpoint_auth_methods_supported": [
                "client_secret_basic",
                "client_secret_post",
            ],
        }
    )


@require_GET
def oauth_protected_resource_metadata(request: HttpRequest, resource_path: str = "") -> JsonResponse:
    base = _public_base(request)
    mcp_url = _mcp_resource_url(request)
    scopes = list(getattr(settings, "RETRIEVER_SCOPES", {}).keys())
    return JsonResponse(
        {
            "resource": mcp_url,
            "authorization_servers": [base],
            "scopes_supported": scopes,
            "bearer_methods_supported": ["header"],
            "resource_name": "Retriever MCP",
            "resource_documentation": f"{base}/dashboard/",
        }
    )


@method_decorator(login_required(login_url="/login/"), name="dispatch")
class RetrieverAuthorizationView(DOTAuthorizationView):
    """
    Consent screen hosted by Retriever.

    Requires an existing Django session. If the user is not logged in,
    Django's login_required redirects to /login/?next=<full authorize URL>,
    preserving client_id, redirect_uri, state, scope, PKCE, and resource.
    """

    template_name = "oauth2_provider/authorize.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        profile, _ = UserProfile.objects.get_or_create(user=self.request.user)
        org = profile.ensure_active_organization()
        scopes = context.get("scopes") or []
        context.update(
            {
                "page": "consent",
                "signed_in_user": self.request.user,
                "consent_organization": org,
                "scope_rows": [
                    {
                        "scope": s,
                        "description": SCOPE_DESCRIPTIONS.get(
                            s, settings.OAUTH2_PROVIDER["SCOPES"].get(s, s)
                        ),
                    }
                    for s in scopes
                    if s != "offline_access"
                ],
                "mcp_client_name": getattr(context.get("application"), "name", "MCP Client"),
            }
        )
        return context

    def form_valid(self, form):
        allow = form.cleaned_data.get("allow")
        response = super().form_valid(form)
        if not allow:
            return response

        profile, _ = UserProfile.objects.get_or_create(user=self.request.user)
        org = profile.ensure_active_organization()
        if org is None:
            return response

        client_id = form.cleaned_data.get("client_id")
        try:
            app = Application.objects.get(client_id=client_id)
        except Application.DoesNotExist:
            return response

        scopes = form.cleaned_data.get("scope") or ""
        if isinstance(scopes, list):
            scopes = " ".join(scopes)

        grant = (
            Grant.objects.filter(user=self.request.user, application=app)
            .order_by("-created")
            .first()
        )
        if grant is not None:
            OAuthAuthorizationContext.objects.update_or_create(
                grant=grant,
                defaults={
                    "application": app,
                    "user": self.request.user,
                    "organization": org,
                    "scopes": scopes,
                    "access_token": None,
                },
            )
        else:
            OAuthAuthorizationContext.objects.create(
                application=app,
                user=self.request.user,
                organization=org,
                scopes=scopes,
            )
        return response


@login_required
def connected_apps_view(request: HttpRequest) -> HttpResponse:
    tokens = (
        AccessToken.objects.filter(user=request.user)
        .select_related("application")
        .order_by("-created")
    )
    apps = []
    seen = set()
    for token in tokens:
        if token.application_id in seen:
            continue
        if token.is_expired():
            continue
        seen.add(token.application_id)
        scopes = [s for s in (token.scope or "").split() if s]
        apps.append(
            {
                "application": token.application,
                "scopes": scopes,
                "scope_descriptions": [
                    SCOPE_DESCRIPTIONS.get(s, s) for s in scopes if s != "offline_access"
                ],
                "token_id": token.pk,
            }
        )
    return render(
        request,
        "oauth_server/connected_apps.html",
        {"page": "connected_apps", "connected_apps": apps},
    )


@login_required
@require_http_methods(["POST"])
def disconnect_app(request: HttpRequest, application_id: int) -> HttpResponse:
    app = Application.objects.filter(pk=application_id).first()
    if app is None:
        return redirect("connected_apps")
    AccessToken.objects.filter(user=request.user, application=app).delete()
    RefreshToken.objects.filter(user=request.user, application=app).delete()
    Grant.objects.filter(user=request.user, application=app).delete()
    OAuthAuthorizationContext.objects.filter(user=request.user, application=app).delete()
    return redirect("connected_apps")


@csrf_exempt
@require_http_methods(["POST"])
def dynamic_client_registration(request: HttpRequest) -> JsonResponse:
    """
    Minimal RFC 7591 Dynamic Client Registration for Claude fallback.

    Primary demo path uses a pre-registered Client ID + Client Secret.
    """
    import json

    try:
        payload = json.loads(request.body.decode("utf-8") or "{}")
    except json.JSONDecodeError:
        return JsonResponse(
            {"error": "invalid_client_metadata", "error_description": "Invalid JSON"},
            status=400,
        )

    redirect_uris = payload.get("redirect_uris") or []
    if not redirect_uris or not isinstance(redirect_uris, list):
        return JsonResponse(
            {
                "error": "invalid_redirect_uri",
                "error_description": "redirect_uris is required",
            },
            status=400,
        )

    client_name = payload.get("client_name") or "Dynamically Registered MCP Client"
    token_endpoint_auth_method = payload.get("token_endpoint_auth_method") or "none"
    client_type = (
        Application.CLIENT_PUBLIC
        if token_endpoint_auth_method == "none"
        else Application.CLIENT_CONFIDENTIAL
    )

    app = Application(
        name=client_name[:255],
        client_type=client_type,
        authorization_grant_type=Application.GRANT_AUTHORIZATION_CODE,
        redirect_uris="\n".join(redirect_uris),
        hash_client_secret=True,
    )
    # Generate credentials via model helpers
    from oauth2_provider.generators import generate_client_id, generate_client_secret

    app.client_id = generate_client_id()
    raw_secret = generate_client_secret()
    app.client_secret = raw_secret
    app.save()

    response = {
        "client_id": app.client_id,
        "client_name": app.name,
        "redirect_uris": redirect_uris,
        "grant_types": ["authorization_code", "refresh_token"],
        "response_types": ["code"],
        "token_endpoint_auth_method": token_endpoint_auth_method,
        "client_id_issued_at": int(app.created.timestamp()),
    }
    if client_type == Application.CLIENT_CONFIDENTIAL:
        response["client_secret"] = raw_secret
    return JsonResponse(response, status=201)
