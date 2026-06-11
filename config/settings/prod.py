from .base import *  # noqa: F403

DEBUG = False

# Set ATLAS_BEHIND_TLS=false only for LAN/localhost compose deployments without a
# reverse proxy; anything reachable from the internet should keep TLS on.
_behind_tls = env.bool("ATLAS_BEHIND_TLS", default=True)

SECURE_HSTS_SECONDS = 31536000 if _behind_tls else 0
SECURE_HSTS_INCLUDE_SUBDOMAINS = _behind_tls
SECURE_HSTS_PRELOAD = _behind_tls
SECURE_SSL_REDIRECT = _behind_tls
SECURE_REFERRER_POLICY = "same-origin"
SESSION_COOKIE_SECURE = _behind_tls
CSRF_COOKIE_SECURE = _behind_tls

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"},
}
