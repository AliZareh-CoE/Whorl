from django.urls import path

from . import views

app_name = "writing"

urlpatterns = [
    path("writing/", views.writing_home, name="home"),
    path("projects/<slug:slug>/writing/", views.project_writing, name="project"),
    path("projects/<slug:slug>/writing/new/", views.ManuscriptCreateView.as_view(), name="create"),
    path("projects/<slug:slug>/writing/<int:pk>/", views.manuscript_detail, name="detail"),
    path(
        "projects/<slug:slug>/writing/<int:pk>/edit/",
        views.ManuscriptUpdateView.as_view(),
        name="edit",
    ),
    path(
        "projects/<slug:slug>/writing/<int:pk>/delete/",
        views.ManuscriptDeleteView.as_view(),
        name="delete",
    ),
    path("projects/<slug:slug>/writing/<int:pk>/editor/", views.latex_editor, name="editor"),
    path("projects/<slug:slug>/writing/<int:pk>/files/", views.manuscript_files, name="files"),
    path(
        "projects/<slug:slug>/writing/<int:pk>/word-count/",
        views.word_count_view,
        name="word_count",
    ),
    path(
        "projects/<slug:slug>/writing/<int:pk>/files/upload/",
        views.file_upload,
        name="file_upload",
    ),
    path(
        "projects/<slug:slug>/writing/<int:pk>/files/<int:file_pk>/",
        views.file_content,
        name="file_content",
    ),
    path(
        "projects/<slug:slug>/writing/<int:pk>/files/<int:file_pk>/save/",
        views.file_save,
        name="file_save",
    ),
    path(
        "projects/<slug:slug>/writing/<int:pk>/files/<int:file_pk>/rename/",
        views.file_rename,
        name="file_rename",
    ),
    path(
        "projects/<slug:slug>/writing/<int:pk>/files/<int:file_pk>/delete/",
        views.file_delete,
        name="file_delete",
    ),
    path(
        "projects/<slug:slug>/writing/<int:pk>/compile/",
        views.compile_manuscript_view,
        name="compile",
    ),
    path(
        "projects/<slug:slug>/writing/<int:pk>/compile/status/",
        views.compile_status,
        name="compile_status",
    ),
    path(
        "projects/<slug:slug>/writing/<int:pk>/references/add/",
        views.add_reference,
        name="add_reference",
    ),
    path(
        "projects/<slug:slug>/writing/<int:pk>/references/<int:link_pk>/remove/",
        views.remove_reference,
        name="remove_reference",
    ),
    path("projects/<slug:slug>/writing/<int:pk>/export.bib", views.export_bib, name="export_bib"),
    path("projects/<slug:slug>/writing/<int:pk>/events/add/", views.add_event, name="add_event"),
    path(
        "projects/<slug:slug>/writing/<int:pk>/events/<int:event_pk>/delete/",
        views.delete_event,
        name="delete_event",
    ),
]
