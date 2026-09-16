from django.conf import settings
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path, re_path
from django.views.static import serve

from core.security import ThrottledLoginView

urlpatterns = [
    path("admin/", admin.site.urls),
    path("login/", ThrottledLoginView.as_view(), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
    path("api/", include("api.urls")),
    path("", include("literature.urls")),
    path("", include("writing.urls")),
    path("", include("notes.urls")),
    path("", include("prompts.urls")),
    path("", include("bots.urls")),
    path("projects/", include("plans.urls")),
    path("projects/", include("documents.urls")),
    path("projects/", include("research.urls")),
    path("projects/", include("projects.urls")),
    path("", include("core.urls")),
]

# Uploaded files (PDFs, compiled manuscripts, figures) are served by Django itself, in every
# settings module: this is a single-user app whose desktop build has no reverse proxy, and
# with DEBUG off the classic `static()` helper silently served nothing — the studio's PDF
# pane showed "Missing PDF" on the desktop (owner report, 2026-09-06). LoginRequiredMiddleware
# keeps the files behind the login like every other page. `MEDIA_ROOT` is read per request,
# not bound at import, so a settings override (tests, the desktop's per-profile data dir)
# is honoured (Audit #34).


def media(request, path):
    return serve(request, path, document_root=settings.MEDIA_ROOT)


urlpatterns += [
    re_path(r"^media/(?P<path>.*)$", media, name="media"),
]
