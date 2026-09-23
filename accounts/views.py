from django.contrib import messages
from django.contrib.auth import get_user_model, login, logout
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.http import HttpRequest, HttpResponse, HttpResponseRedirect
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.http import require_http_methods
from oauth2_provider.models import AccessToken, Grant, RefreshToken

from accounts.forms import LoginForm, SignupForm
from oauth_server.models import OAuthAuthorizationContext
from organizations.models import Organization, OrganizationMembership, UserProfile

User = get_user_model()


def _revoke_user_oauth(user) -> int:
    """Revoke all OAuth credentials for a user. Returns count of deleted access tokens."""
    token_count = AccessToken.objects.filter(user=user).count()
    AccessToken.objects.filter(user=user).delete()
    RefreshToken.objects.filter(user=user).delete()
    Grant.objects.filter(user=user).delete()
    OAuthAuthorizationContext.objects.filter(user=user).delete()
    return token_count


@require_http_methods(["GET", "POST"])
def login_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect(request.GET.get("next") or reverse("dashboard"))

    form = LoginForm(request, data=request.POST or None)
    if request.method == "POST" and form.is_valid():
        login(request, form.get_user())
        next_url = request.POST.get("next") or request.GET.get("next") or reverse("dashboard")
        return HttpResponseRedirect(next_url)

    return render(
        request,
        "accounts/login.html",
        {
            "form": form,
            "next": request.GET.get("next", ""),
            "page": "login",
        },
    )


@require_http_methods(["GET", "POST"])
def signup_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        return redirect(request.GET.get("next") or reverse("dashboard"))

    form = SignupForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            user = User.objects.create_user(
                username=form.cleaned_data["username"],
                email=form.cleaned_data.get("email") or "",
                password=form.cleaned_data["password1"],
            )
            org = Organization.objects.create(
                name=form.cleaned_data["organization_name"]
            )
            OrganizationMembership.objects.create(
                user=user,
                organization=org,
                role=OrganizationMembership.Role.OWNER,
            )
            profile, _ = UserProfile.objects.get_or_create(user=user)
            profile.active_organization = org
            profile.save(update_fields=["active_organization"])

        login(request, user)
        next_url = request.POST.get("next") or request.GET.get("next") or reverse("dashboard")
        return HttpResponseRedirect(next_url)

    return render(
        request,
        "accounts/signup.html",
        {
            "form": form,
            "next": request.GET.get("next", ""),
            "page": "signup",
        },
    )


@require_http_methods(["POST", "GET"])
def logout_view(request: HttpRequest) -> HttpResponse:
    if request.user.is_authenticated:
        revoked = _revoke_user_oauth(request.user)
        logout(request)
        if revoked:
            messages.info(
                request,
                "You signed out and all connected apps were disconnected. "
                "Reconnect Claude after signing in again.",
            )
        else:
            messages.info(request, "You have signed out.")
    else:
        logout(request)
    return redirect("login")


@login_required
def dashboard_view(request: HttpRequest) -> HttpResponse:
    return render(request, "accounts/dashboard.html", {"page": "dashboard"})
