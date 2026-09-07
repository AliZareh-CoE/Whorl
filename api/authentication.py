from django.conf import settings
from django.contrib.auth.models import User
from django.utils.crypto import constant_time_compare
from rest_framework.authentication import BaseAuthentication
from rest_framework.exceptions import AuthenticationFailed


class APIKeyAuthentication(BaseAuthentication):
    """Sole API auth: X-API-Key header compared against the ATLAS_API_KEY env setting."""

    def authenticate(self, request):
        key = request.headers.get("X-API-Key")
        if not key:
            return None
        expected = settings.ATLAS_API_KEY
        if not expected or not constant_time_compare(key, expected):
            from core.access import record

            record("api_key_rejected", request, detail=request.path[:120])
            raise AuthenticationFailed("Invalid API key.")
        user = User.objects.filter(is_superuser=True).order_by("pk").first()
        if user is None:
            raise AuthenticationFailed("No owner account exists yet.")
        return (user, None)

    def authenticate_header(self, request):
        return "X-API-Key"


class QueryKeyAuthentication(APIKeyAuthentication):
    """`?key=` variant for feeds that calendar apps fetch without headers (calendar.ics only).
    The URL therefore carries the API key — the Dashboard says so when it hands it out."""

    def authenticate(self, request):
        key = request.query_params.get("key")
        if not key:
            return None
        expected = settings.ATLAS_API_KEY
        if not expected or not constant_time_compare(key, expected):
            from core.access import record

            record("api_key_rejected", request, detail=request.path[:120])
            raise AuthenticationFailed("Invalid API key.")
        user = User.objects.filter(is_superuser=True).order_by("pk").first()
        if user is None:
            raise AuthenticationFailed("No owner account exists yet.")
        return (user, None)
