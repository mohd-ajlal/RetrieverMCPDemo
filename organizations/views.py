from django.contrib.auth.decorators import login_required
from django.http import HttpRequest, HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from organizations.models import OrganizationMembership, UserProfile


def active_organization(request: HttpRequest) -> dict:
    org = None
    memberships = []
    if request.user.is_authenticated:
        profile, _ = UserProfile.objects.get_or_create(user=request.user)
        org = profile.ensure_active_organization()
        memberships = list(
            OrganizationMembership.objects.filter(user=request.user).select_related(
                "organization"
            )
        )
    return {
        "active_organization": org,
        "organization_memberships": memberships,
    }


@login_required
@require_http_methods(["POST"])
def switch_organization(request: HttpRequest) -> HttpResponse:
    org_id = request.POST.get("organization_id")
    membership = get_object_or_404(
        OrganizationMembership, user=request.user, organization_id=org_id
    )
    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    profile.active_organization = membership.organization
    profile.save(update_fields=["active_organization"])
    next_url = request.POST.get("next") or "/dashboard/"
    return redirect(next_url)


@login_required
def organization_view(request: HttpRequest) -> HttpResponse:
    return render(request, "organizations/detail.html", {"page": "organization"})
