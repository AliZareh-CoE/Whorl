from django.urls import path

from . import views

app_name = "notes"

urlpatterns = [
    path("inbox/", views.inbox, name="inbox"),
    path("inbox/<int:pk>/triage/", views.triage, name="triage"),
    path("inbox/bulk/", views.inbox_bulk, name="inbox_bulk"),
    path("projects/<slug:slug>/notes/", views.note_list, name="list"),
    path("projects/<slug:slug>/notes/new/", views.NoteCreateView.as_view(), name="create"),
    path("projects/<slug:slug>/notes/preview/", views.note_preview, name="preview"),
    path("projects/<slug:slug>/notes/<int:pk>/", views.note_detail, name="detail"),
    path("projects/<slug:slug>/notes/<int:pk>/edit/", views.NoteUpdateView.as_view(), name="edit"),
    path(
        "projects/<slug:slug>/notes/<int:pk>/delete/",
        views.NoteDeleteView.as_view(),
        name="delete",
    ),
]
