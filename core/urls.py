from django.urls import path

from . import comments, views

app_name = "core"

urlpatterns = [
    path("", views.dashboard, name="dashboard"),
    path("search/", views.search, name="search"),
    path("search/suggest/", views.search_suggest, name="search_suggest"),
    path("tts/", views.read_aloud, name="tts"),
    path("comments/<slug:kind>/<int:object_id>/add/", comments.add_comment, name="comment_add"),
    path("comments/<int:pk>/delete/", comments.delete_comment, name="comment_delete"),
    path("assistant/context/", views.assistant_context_view, name="assistant_context"),
    path("app/", views.spa_shell, name="spa"),
    path("app/<path:rest>", views.spa_shell, name="spa_rest"),
    path("pet/", views.pet_page, name="pet"),
    path("summarize/", views.summarize_view, name="summarize"),
]
