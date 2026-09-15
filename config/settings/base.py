from pathlib import Path

import environ

from core.framing import parse_ancestors

BASE_DIR = Path(__file__).resolve().parent.parent.parent

env = environ.Env(DEBUG=(bool, False))
environ.Env.read_env(BASE_DIR / ".env")

SECRET_KEY = env("SECRET_KEY", default="insecure-dev-key")
DEBUG = env("DEBUG")
ALLOWED_HOSTS = env.list("ALLOWED_HOSTS", default=["localhost", "127.0.0.1"])

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "rest_framework",
    "drf_spectacular",
    "huey.contrib.djhuey",
    "core",
    "projects",
    "plans",
    "documents",
    "literature",
    "notes",
    "writing",
    "research",
    "prompts",
    "bots",
    "api",
]

X_FRAME_OPTIONS = "DENY"
# Origins allowed to put Atlas in a frame (#539: Atlas as a tab in OpenManus). Empty = nobody.
ATLAS_FRAME_ANCESTORS = parse_ancestors(env("ATLAS_FRAME_ANCESTORS", default=""))

REST_FRAMEWORK = {
    # API key for MCP/scripts; session+CSRF for the same-origin SPA (Owner idea #20)
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "api.authentication.APIKeyAuthentication",
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": ["rest_framework.permissions.IsAuthenticated"],
    "DEFAULT_PAGINATION_CLASS": "rest_framework.pagination.PageNumberPagination",
    "PAGE_SIZE": 50,
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
    # Brakes against runaway scripts, generous for one human + one Claude
    "DEFAULT_THROTTLE_CLASSES": [
        "rest_framework.throttling.UserRateThrottle",
        "rest_framework.throttling.AnonRateThrottle",
    ],
    "DEFAULT_THROTTLE_RATES": {"user": "3000/hour", "anon": "30/hour"},
}

SPECTACULAR_SETTINGS = {
    "TITLE": "Atlas API",
    "DESCRIPTION": "Everything in the Atlas UI, scriptable. Authenticate with the X-API-Key header.",
    "VERSION": "1.0.0",
    "SERVE_INCLUDE_SCHEMA": False,
    # Two models expose a `kind` choices field with different value sets (ManuscriptFile vs
    # SubmissionEvent); give each enum a distinct schema component name so they don't collide.
    "ENUM_NAME_OVERRIDES": {
        "ManuscriptFileKindEnum": "writing.models.ManuscriptFile.Kind",
        "SubmissionEventKindEnum": "writing.models.SubmissionEvent.Kind",
    },
}

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "core.framing.FrameAncestorsMiddleware",  # #539: frame-ancestors when ATLAS_FRAME_ANCESTORS is set
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "core.ui_middleware.ClassicRedirectMiddleware",  # classic page → SPA twin (one front door)
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.auth.middleware.LoginRequiredMiddleware",
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
                "core.context_processors.pet",
                "core.context_processors.assistant",
            ],
        },
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DATABASES = {
    "default": env.db("DATABASE_URL", default="postgres://atlas:atlas@localhost:5432/atlas"),
}

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "UTC"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = BASE_DIR / "staticfiles"

MEDIA_URL = "media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "login"
LOGIN_REDIRECT_URL = "/"  # the SPA front door (classic dashboard lives at /classic/)
LOGOUT_REDIRECT_URL = "login"

ATLAS_API_KEY = env("ATLAS_API_KEY", default="")
ATLAS_DESKTOP = False  # the desktop settings module flips this (login hint, doctor)
# Optional OpenAlex key: raises the daily budget for the Library's discovery lenses.
ATLAS_OPENALEX_API_KEY = env("ATLAS_OPENALEX_API_KEY", default="")
# #529: optional Semantic Scholar key for the preprint watch (higher rate limits)
ATLAS_S2_API_KEY = env("ATLAS_S2_API_KEY", default="")
ATLAS_CONTACT_EMAIL = env("ATLAS_CONTACT_EMAIL", default="atlas-owner@localhost")
ATLAS_AUTO_FETCH_PDF = env.bool("ATLAS_AUTO_FETCH_PDF", default=True)

REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/0")

HUEY = {
    "huey_class": "huey.RedisHuey",
    "name": "atlas",
    "url": REDIS_URL,
    "immediate": False,
    "consumer": {"workers": 1},
}
