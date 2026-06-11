from django.urls import path, re_path
from django.views.generic import RedirectView

from . import comments, views

app_name = "core"

# THE CUTOVER (Owner idea #20, cycle 68): the SPA owns / and the slash-less routes;
# classic pages keep their trailing-slash URLs, with the old dashboard at /classic/.
spa_routes = [
    path("", views.spa_shell, name="spa_home"),
    re_path(r"^projects/[^/]+$", views.spa_shell),
    re_path(
        r"^projects/[^/]+/(plan|documents|literature|queue|read|notes|research|decisions|graph)$",
        views.spa_shell,
    ),
    re_path(r"^projects/[^/]+/notes/(new|\d+)$", views.spa_shell),
    re_path(r"^(library|writing|inbox|prompts|search|automations)$", views.spa_shell),
    re_path(r"^manuscripts/\d+$", views.spa_shell),
    re_path(r"^references/\d+$", views.spa_shell),
    # old bookmarks: /app/* → same path at the root
    path("app/", RedirectView.as_view(url="/", permanent=False)),
    path("app/<path:rest>", views.spa_redirect),
]

urlpatterns = spa_routes + [
    path("classic/", views.dashboard, name="dashboard"),
    path("search/", views.search, name="search"),
    path("search/suggest/", views.search_suggest, name="search_suggest"),
    path("tts/", views.read_aloud, name="tts"),
    path("comments/<slug:kind>/<int:object_id>/add/", comments.add_comment, name="comment_add"),
    path("comments/<int:pk>/delete/", comments.delete_comment, name="comment_delete"),
    path("assistant/context/", views.assistant_context_view, name="assistant_context"),
    path("pet/", views.pet_page, name="pet"),
    path("summarize/", views.summarize_view, name="summarize"),
]
