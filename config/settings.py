"""Django settings for Retriever MCP OAuth demo."""

from __future__ import annotations

import os
import urllib.parse
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()
load_dotenv(".env.local")

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = os.environ.get(
    "SECRET_KEY",
    "dev-only-insecure-secret-key-change-me-in-production",
)

DEBUG = os.environ.get("DEBUG", "true").lower() in ("1", "true", "yes")

ALLOWED_HOSTS = [
    h.strip()
    for h in os.environ.get(
        "ALLOWED_HOSTS", "localhost,127.0.0.1,testserver,.vercel.app"
    ).split(",")
    if h.strip()
]

PUBLIC_BASE_URL = os.environ.get("PUBLIC_BASE_URL", "http://127.0.0.1:8000").rstrip("/")
MCP_RESOURCE_URL = os.environ.get("MCP_RESOURCE_URL", f"{PUBLIC_BASE_URL}/mcp").rstrip("/")

CSRF_TRUSTED_ORIGINS = [
    o.strip()
    for o in os.environ.get(
        "CSRF_TRUSTED_ORIGINS",
        "http://127.0.0.1:8000,http://localhost:8000",
    ).split(",")
    if o.strip()
]

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django_vite",
    "oauth2_provider",
    "accounts",
    "organizations",
    "oauth_server.apps.OauthServerConfig",
    "retriever",
    "mcp_server",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "organizations.context_processors.active_organization",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"


def _normalize_database_url(raw: str | None) -> str:
    """Strip whitespace and wrapping quotes (common when pasting into Vercel UI)."""
    if not raw:
        return ""
    value = raw.strip()
    if (value.startswith('"') and value.endswith('"')) or (
        value.startswith("'") and value.endswith("'")
    ):
        value = value[1:-1].strip()
    return value


_database_url = _normalize_database_url(os.environ.get("DATABASE_URL"))

if _database_url:
    url = urllib.parse.urlparse(_database_url)
    query = dict(urllib.parse.parse_qsl(url.query))
    db_name = url.path.lstrip("/")
    OPTIONS = {}
    if query.get("sslmode"):
        OPTIONS["sslmode"] = query["sslmode"].rstrip('"').rstrip("'")
    # Neon pooler may send channel_binding; psycopg accepts it via options when present
    if query.get("channel_binding"):
        OPTIONS["channel_binding"] = query["channel_binding"].rstrip('"').rstrip("'")
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": db_name,
            "USER": urllib.parse.unquote(url.username or ""),
            "PASSWORD": urllib.parse.unquote(url.password or ""),
            "HOST": url.hostname or "",
            "PORT": str(url.port or "5432"),
            "CONN_MAX_AGE": int(os.environ.get("DB_CONN_MAX_AGE", "0")),
            "OPTIONS": OPTIONS,
        }
    }
else:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": BASE_DIR / "db.sqlite3",
        }
    }

# region agent log
try:
    import json
    import time

    _log_path = BASE_DIR / ".cursor" / "debug-8cee01.log"
    _log_path.parent.mkdir(parents=True, exist_ok=True)
    _dbg = {
        "sessionId": "8cee01",
        "runId": "db-url-parse",
        "hypothesisId": "A",
        "location": "config/settings.py:DATABASES",
        "message": "DATABASE_URL parse result (redacted)",
        "data": {
            "raw_present": bool(os.environ.get("DATABASE_URL")),
            "raw_starts_with_quote": (os.environ.get("DATABASE_URL") or "").lstrip().startswith(
                ('"', "'")
            ),
            "normalized_scheme": urllib.parse.urlparse(_database_url).scheme if _database_url else "",
            "engine": DATABASES["default"]["ENGINE"],
            "name": str(DATABASES["default"].get("NAME", ""))[:63],
            "name_len": len(str(DATABASES["default"].get("NAME", ""))),
            "host_set": bool(DATABASES["default"].get("HOST")),
            "user_set": bool(DATABASES["default"].get("USER")),
            "sslmode": (DATABASES["default"].get("OPTIONS") or {}).get("sslmode"),
        },
        "timestamp": int(time.time() * 1000),
    }
    with open(_log_path, "a", encoding="utf-8") as _f:
        _f.write(json.dumps(_dbg) + "\n")
except Exception:
    pass
# endregion

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedStaticFilesStorage",
    },
}

DJANGO_VITE = {
    "default": {
        "dev_mode": DEBUG and os.environ.get("DJANGO_VITE_DEV", "false").lower() in (
            "1",
            "true",
            "yes",
        ),
        "manifest_path": BASE_DIR / "static" / "frontend" / "manifest.json",
        "static_url_prefix": "frontend/",
    }
}

# Avoid hard failure when frontend has not been built yet
import pathlib as _pathlib

if not (BASE_DIR / "static" / "frontend" / "manifest.json").exists():
    DJANGO_VITE["default"]["dev_mode"] = True


DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "/login/"
LOGIN_REDIRECT_URL = "/dashboard/"
LOGOUT_REDIRECT_URL = "/login/"

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_HTTPONLY = False
CSRF_COOKIE_SAMESITE = "Lax"

if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = os.environ.get("SECURE_SSL_REDIRECT", "true").lower() in (
        "1",
        "true",
        "yes",
    )

# --- OAuth Authorization Server (django-oauth-toolkit) ---
OAUTH2_PROVIDER_APPLICATION_MODEL = "oauth2_provider.Application"
OAUTH2_PROVIDER_ACCESS_TOKEN_MODEL = "oauth2_provider.AccessToken"
OAUTH2_PROVIDER_REFRESH_TOKEN_MODEL = "oauth2_provider.RefreshToken"
OAUTH2_PROVIDER_GRANT_MODEL = "oauth2_provider.Grant"
OAUTH2_PROVIDER_ID_TOKEN_MODEL = "oauth2_provider.IDToken"
OAUTH2_PROVIDER = {
    "PKCE_REQUIRED": True,
    "OIDC_ENABLED": False,
    "ACCESS_TOKEN_EXPIRE_SECONDS": int(os.environ.get("ACCESS_TOKEN_EXPIRE_SECONDS", "3600")),
    "AUTHORIZATION_CODE_EXPIRE_SECONDS": int(
        os.environ.get("AUTHORIZATION_CODE_EXPIRE_SECONDS", "60")
    ),
    "REFRESH_TOKEN_EXPIRE_SECONDS": int(
        os.environ.get("REFRESH_TOKEN_EXPIRE_SECONDS", "86400")
    ),
    "ROTATE_REFRESH_TOKEN": True,
    "SCOPES": {
        "retriever.devices.read": "View Retriever devices",
        "retriever.orders.read": "View deployment and return orders",
        "retriever.orders.write": "Create and modify demo orders",
        "offline_access": "Maintain access when you are not actively using the connector",
    },
    "DEFAULT_SCOPES": [
        "retriever.devices.read",
        "retriever.orders.read",
    ],
    "REQUEST_APPROVAL_PROMPT": "force",
    "ERROR_RESPONSE_WITH_SCOPES": True,
    "RESOURCE_SERVER_TOKEN_RESOURCE_VALIDATOR": (
        "oauth_server.validators.exact_resource_match"
    ),
}

# Scoped strings used by MCP tools
RETRIEVER_SCOPES = {
    "retriever.devices.read": "View Retriever devices",
    "retriever.orders.read": "View deployment and return orders",
    "retriever.orders.write": "Create and modify demo orders",
}

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "filters": {
        "redact_secrets": {
            "()": "oauth_server.logging.RedactSecretsFilter",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "filters": ["redact_secrets"],
        },
    },
    "root": {
        "handlers": ["console"],
        "level": os.environ.get("LOG_LEVEL", "INFO"),
    },
}
