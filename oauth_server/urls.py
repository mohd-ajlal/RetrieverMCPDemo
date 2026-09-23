from django.urls import path, re_path

from oauth_server import views

urlpatterns = [
    path(
        ".well-known/oauth-authorization-server",
        views.oauth_authorization_server_metadata,
        name="oauth_authorization_server_metadata",
    ),
    path(
        ".well-known/oauth-protected-resource",
        views.oauth_protected_resource_metadata,
        name="oauth_protected_resource_metadata",
    ),
    re_path(
        r"^\.well-known/oauth-protected-resource/(?P<resource_path>.+)$",
        views.oauth_protected_resource_metadata,
        name="oauth_protected_resource_metadata_path",
    ),
    # Override DOT authorize with Retriever consent
    path(
        "o/authorize/",
        views.RetrieverAuthorizationView.as_view(),
        name="retriever_authorize",
    ),
    path("o/register/", views.dynamic_client_registration, name="oauth_dcr"),
    path("settings/connected-apps/", views.connected_apps_view, name="connected_apps"),
    path(
        "settings/connected-apps/<int:application_id>/permissions/",
        views.update_app_permissions,
        name="update_app_permissions",
    ),
    path(
        "settings/connected-apps/<int:application_id>/disconnect/",
        views.disconnect_app,
        name="disconnect_app",
    ),
]
