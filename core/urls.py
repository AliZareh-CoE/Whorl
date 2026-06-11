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
    path("pet/", views.pet_page, name="pet"),
]
