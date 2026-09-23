from django.apps import AppConfig


class OauthServerConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "oauth_server"
    verbose_name = "OAuth Server"

    def ready(self) -> None:
        from oauth_server import signals  # noqa: F401
