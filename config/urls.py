"""URL configuration for Retriever MCP demo."""

from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("accounts.urls")),
    path("", include("organizations.urls")),
    path("", include("oauth_server.urls")),
    path("", include("retriever.urls")),
    path("o/", include("oauth2_provider.urls", namespace="oauth2_provider")),
]
