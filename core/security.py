"""Security helpers: login throttling and upload validation (Owner idea #2).

No new dependencies: throttling uses Django's cache, validation plain functions
shared by forms (UI) and serializers (API).
"""

from django.contrib.auth import views as auth_views
from django.core.cache import cache
from django.core.exceptions import ValidationError

LOGIN_MAX_FAILURES = 5
LOGIN_LOCKOUT_SECONDS = 300

MAX_UPLOAD_BYTES = 50 * 1024 * 1024  # 50 MB


def _login_key(request):
    ip = request.META.get("REMOTE_ADDR", "unknown")
    return f"login-failures:{ip}"


class ThrottledLoginView(auth_views.LoginView):
    """Locks login out for 5 minutes after 5 failed attempts from one address."""

    def post(self, request, *args, **kwargs):
        failures = cache.get(_login_key(request), 0)
        if failures >= LOGIN_MAX_FAILURES:
            form = self.get_form()
            from .access import record

            record("login_locked", request)
            form.add_error(None, "Too many failed attempts. Try again in a few minutes.")
            return self.render_to_response(self.get_context_data(form=form), status=429)
        return super().post(request, *args, **kwargs)

    def form_invalid(self, form):
        key = _login_key(self.request)
        failures = cache.get(key, 0) + 1
        cache.set(key, failures, LOGIN_LOCKOUT_SECONDS)
        return super().form_invalid(form)

    def form_valid(self, form):
        cache.delete(_login_key(self.request))
        return super().form_valid(form)

    def get_context_data(self, **kwargs):
        """First-run hint (owner, desktop): the bundled app creates the login atlas / atlas and
        nothing on the page said so. Shown only while that default password still works."""
        context = super().get_context_data(**kwargs)
        context["default_login_hint"] = default_login_still_active()
        return context


def default_login_still_active() -> bool:
    import os

    from django.conf import settings
    from django.contrib.auth import get_user_model

    if not getattr(settings, "ATLAS_DESKTOP", False):
        return False
    username = os.environ.get("ATLAS_ADMIN_USER", "atlas")
    password = os.environ.get("ATLAS_ADMIN_PASSWORD", "atlas")
    user = get_user_model().objects.filter(username=username).first()
    return bool(user and user.check_password(password))


def validate_upload_size(file):
    if file and file.size > MAX_UPLOAD_BYTES:
        raise ValidationError(
            f"File is {file.size / (1024 * 1024):.0f} MB; the limit is "
            f"{MAX_UPLOAD_BYTES // (1024 * 1024)} MB."
        )
    return file


def validate_pdf(file):
    if file and not file.name.lower().endswith(".pdf"):
        raise ValidationError("Only .pdf files can be attached here.")
    return validate_upload_size(file)
