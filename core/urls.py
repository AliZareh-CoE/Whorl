from django.urls import path, re_path
from django.views.generic import RedirectView

from . import comments, views

app_name = "core"

# THE CUTOVER (Owner idea #20, cycle 68) + SHARED ROUTE RULE (Backlog #77, cycle 76):
# the SPA owns / and EVERY slash-less path; classic pages keep their trailing-slash URLs.
# A single catch-all replaces the old hand-mirrored route list (which drifted twice, cycles
# 74-75) — adding a React page now needs zero Django changes. core.urls is included last in
# config.urls, so this only ever runs after every classic app route has had its turn.
spa_routes = [
    path("", views.spa_shell, name="spa_home"),
    # old /app/* bookmarks → same path at the root (must precede the catch-all)
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
    path("connect/claude/", views.connect_claude, name="connect_claude"),
    path("connect/claude/skills/", views.install_claude_skills, name="install_claude_skills"),
    path("summarize/", views.summarize_view, name="summarize"),
    # SPA catch-all (Backlog #77): any slash-less path not under app/static/media serves the
    # shell; the React router resolves it (or renders its own 404). Trailing-slash paths fall
    # through to classic/APPEND_SLASH. MUST stay last.
    re_path(r"^(?!api/|app/|static/|media/)(?!.*/$).+$", views.spa_shell, name="spa_catchall"),
]
