"""
Django settings for customer_support project.
"""

import os
from pathlib import Path

import dj_database_url
from dotenv import load_dotenv


# ============================================================
# BASE DIRECTORY / ENVIRONMENT
# ============================================================

BASE_DIR = Path(__file__).resolve().parent.parent

# Load .env from project root
load_dotenv(BASE_DIR / ".env")


# ============================================================
# SECURITY
# ============================================================

SECRET_KEY = os.getenv(
    "DJANGO_SECRET_KEY",
    "django-insecure-change-this-in-production",
)

DEBUG = os.getenv(
    "DJANGO_DEBUG",
    "True",
).lower() == "true"

ALLOWED_HOSTS = [
    host.strip()
    for host in os.getenv(
        "DJANGO_ALLOWED_HOSTS",
        "127.0.0.1,localhost",
    ).split(",")
    if host.strip()
]

# Session tokens must be stored in HttpOnly cookies, never localStorage.
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SECURE = not DEBUG  # True in production (HTTPS)
CSRF_COOKIE_HTTPONLY = True
CSRF_COOKIE_SECURE = not DEBUG


# ============================================================
# OIDC / OAUTH2 (mozilla-django-oidc)
# ============================================================

OIDC_RP_CLIENT_ID = os.getenv("OIDC_RP_CLIENT_ID")
OIDC_RP_CLIENT_SECRET = os.getenv("OIDC_RP_CLIENT_SECRET")

# Signing algorithm used by the identity provider (default RS256 for Entra ID / Okta)
OIDC_RP_SIGN_ALGO = os.getenv("OIDC_RP_SIGN_ALGO", "RS256")

# Identity provider endpoints — set these via environment variables
OIDC_OP_AUTHORIZATION_ENDPOINT = os.getenv("OIDC_OP_AUTHORIZATION_ENDPOINT")
OIDC_OP_TOKEN_ENDPOINT = os.getenv("OIDC_OP_TOKEN_ENDPOINT")
OIDC_OP_USER_ENDPOINT = os.getenv("OIDC_OP_USER_ENDPOINT")
OIDC_OP_JWKS_ENDPOINT = os.getenv("OIDC_OP_JWKS_ENDPOINT")

# Where to send users after a successful login / logout
LOGIN_REDIRECT_URL = os.getenv("LOGIN_REDIRECT_URL", "/")
LOGOUT_REDIRECT_URL = os.getenv("LOGOUT_REDIRECT_URL", "/")

# Unauthenticated requests are redirected here (Django login page → triggers OIDC)
LOGIN_URL = "/oidc/authenticate/"


# ============================================================
# APPLICATIONS
# ============================================================

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",

    # Third-party
    "rest_framework",
    "corsheaders",
    "mozilla_django_oidc",

    # Local
    "api",
]


# ============================================================
# MIDDLEWARE
# ============================================================

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",

    "django.middleware.security.SecurityMiddleware",

    "django.contrib.sessions.middleware.SessionMiddleware",

    "django.middleware.common.CommonMiddleware",

    "django.middleware.csrf.CsrfViewMiddleware",

    "django.contrib.auth.middleware.AuthenticationMiddleware",

    "django.contrib.messages.middleware.MessageMiddleware",

    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]


# ============================================================
# URL / WSGI / ASGI
# ============================================================

ROOT_URLCONF = "customer_support.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",

        "DIRS": [],

        "APP_DIRS": True,

        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",

                "django.contrib.auth.context_processors.auth",

                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

WSGI_APPLICATION = "customer_support.wsgi.application"

ASGI_APPLICATION = "customer_support.asgi.application"


# ============================================================
# DATABASE
# ============================================================

DATABASES = {
    "default": dj_database_url.config(
        env="DATABASE_URL",
        default=f"sqlite:///{BASE_DIR / 'db.sqlite3'}",
        conn_max_age=int(os.getenv("DB_CONN_MAX_AGE", "0")),
    )
}


# ============================================================
# PASSWORD VALIDATION
# ============================================================

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "UserAttributeSimilarityValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "MinimumLengthValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "CommonPasswordValidator"
        ),
    },
    {
        "NAME": (
            "django.contrib.auth.password_validation."
            "NumericPasswordValidator"
        ),
    },
]


# ============================================================
# INTERNATIONALIZATION
# ============================================================

LANGUAGE_CODE = "en-us"

TIME_ZONE = "UTC"

USE_I18N = True

USE_TZ = True


# ============================================================
# STATIC FILES
# ============================================================

STATIC_URL = "static/"


# ============================================================
# EMAIL
# ============================================================

EMAIL_BACKEND = (
    "django.core.mail.backends.console.EmailBackend"
)


# ============================================================
# CORS
# ============================================================

CORS_ALLOW_ALL_ORIGINS = True


# ============================================================
# RAG CONFIGURATION
# ============================================================

DATA_DIR = Path(
    os.getenv(
        "DATA_DIR",
        str(BASE_DIR / "data"),
    )
)

DEFAULT_CHUNK_SIZE = int(
    os.getenv(
        "DEFAULT_CHUNK_SIZE",
        "500",
    )
)

DEFAULT_CHUNK_OVERLAP = int(
    os.getenv(
        "DEFAULT_CHUNK_OVERLAP",
        "50",
    )
)

DEFAULT_TOP_K = int(
    os.getenv(
        "DEFAULT_TOP_K",
        "3",
    )
)

RAG_MIN_RELEVANCE_SCORE = float(
    os.getenv(
        "RAG_MIN_RELEVANCE_SCORE",
        "0.55",
    )
)

RAG_MIN_QDRANT_SCORE = float(
    os.getenv(
        "RAG_MIN_QDRANT_SCORE",
        "0.55",
    )
)




# ============================================================
# AZURE OPENAI
# ============================================================

AZURE_OPENAI_ENDPOINT = os.getenv(
    "AZURE_OPENAI_ENDPOINT"
)

AZURE_OPENAI_API_KEY = os.getenv(
    "AZURE_OPENAI_API_KEY"
)

AZURE_OPENAI_API_VERSION = os.getenv(
    "AZURE_OPENAI_API_VERSION"
)

AZURE_OPENAI_CHAT_DEPLOYMENT = os.getenv(
    "AZURE_OPENAI_CHAT_DEPLOYMENT"
)

AZURE_OPENAI_EMBEDDING_DEPLOYMENT = os.getenv(
    "AZURE_OPENAI_EMBEDDING_DEPLOYMENT"
)


# ============================================================
# AZURE AI SEARCH
# ============================================================

AZURE_SEARCH_ENDPOINT = os.getenv(
    "AZURE_SEARCH_ENDPOINT"
)

AZURE_SEARCH_API_KEY = os.getenv(
    "AZURE_SEARCH_API_KEY"
)

AZURE_SEARCH_INDEX_NAME = os.getenv(
    "AZURE_SEARCH_INDEX_NAME"
)


# ============================================================
# AZURE BLOB STORAGE
# ============================================================

AZURE_STORAGE_CONNECTION_STRING = os.getenv(
    "AZURE_STORAGE_CONNECTION_STRING"
)

AZURE_STORAGE_CONTAINER_NAME = os.getenv(
    "AZURE_STORAGE_CONTAINER_NAME"
)


# ============================================================
# DATABASE BACKUP
# Backups are uploaded to a SEPARATE storage account / region
# from the primary document container to satisfy the cross-
# region isolation requirement.  Set AZURE_BACKUP_STORAGE_-
# CONNECTION_STRING to a storage account in a different region;
# fall back to the primary connection string only for local dev.
# ============================================================

# Connection string for the backup storage account (different
# region from the primary AZURE_STORAGE_CONNECTION_STRING).
AZURE_BACKUP_STORAGE_CONNECTION_STRING = os.getenv(
    "AZURE_BACKUP_STORAGE_CONNECTION_STRING",
    os.getenv("AZURE_STORAGE_CONNECTION_STRING"),   # dev fallback
)

# Container inside the backup storage account that holds SQLite
# backup blobs.
AZURE_BACKUP_CONTAINER_NAME = os.getenv(
    "AZURE_BACKUP_CONTAINER_NAME",
    "db-backups",
)

# How many days of backups to keep (minimum required: 30).
DB_BACKUP_RETENTION_DAYS = int(
    os.getenv(
        "DB_BACKUP_RETENTION_DAYS",
        "30",
    )
)


# ============================================================
# QDRANT
# ============================================================

QDRANT_URL = os.getenv(
    "QDRANT_URL"
)

QDRANT_API_KEY = os.getenv(
    "QDRANT_API_KEY"
)

QDRANT_COLLECTION_NAME = os.getenv(
    "QDRANT_COLLECTION_NAME",
    "customer_support",
)


# ============================================================
# AUTHENTICATION BACKENDS
# ============================================================

AUTHENTICATION_BACKENDS = [
    "mozilla_django_oidc.auth.OIDCAuthenticationBackend",
    "django.contrib.auth.backends.ModelBackend",
]


# ============================================================
# DJANGO REST FRAMEWORK
# ============================================================

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": [
        "rest_framework.renderers.JSONRenderer",
    ],
    "DEFAULT_PARSER_CLASSES": [
        "rest_framework.parsers.JSONParser",
    ],
    # Require authentication on all API endpoints by default.
    # Individual views can override this with AllowAny (e.g. health check).
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "mozilla_django_oidc.contrib.drf.OIDCAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}


# ============================================================
# LOGGING
# ============================================================

LOGGING = {
    "version": 1,

    "disable_existing_loggers": False,

    "formatters": {
        "verbose": {
            "format": (
                "[{asctime}] "
                "[{levelname}] "
                "[{name}:{lineno}] "
                "{message}"
            ),
            "style": "{",
        },
    },

    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },

    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
        },

        "api": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },

        "rag": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },

        "azure_services": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}