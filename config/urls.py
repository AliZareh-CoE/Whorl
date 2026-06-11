from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

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
    path("projects/", include("plans.urls")),
    path("projects/", include("documents.urls")),
    path("projects/", include("research.urls")),
    path("projects/", include("projects.urls")),
    path("", include("core.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
