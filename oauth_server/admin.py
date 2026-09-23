from django.contrib import admin

from oauth_server.models import OAuthAuthorizationContext


@admin.register(OAuthAuthorizationContext)
class OAuthAuthorizationContextAdmin(admin.ModelAdmin):
    list_display = ("id", "application", "user", "organization", "created_at")
    list_filter = ("organization", "application")
    raw_id_fields = ("grant", "access_token", "user", "organization", "application")
