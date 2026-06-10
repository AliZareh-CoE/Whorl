from django.urls import path

from . import views

app_name = "literature"

urlpatterns = [
    path("library/", views.library_index, name="index"),
    path("library/add/", views.add_by_identifier, name="add"),
    path("library/new/", views.ReferenceCreateView.as_view(), name="create"),
    path("library/import/", views.import_bibtex, name="import"),
    path("library/<int:pk>/", views.reference_detail, name="detail"),
    path("library/<int:pk>/edit/", views.ReferenceUpdateView.as_view(), name="edit"),
    path("library/<int:pk>/delete/", views.ReferenceDeleteView.as_view(), name="delete"),
    path("library/<int:pk>/link/", views.link_to_project, name="link"),
    path("library/<int:pk>/read/", views.read_pdf, name="read"),
    path("library/<int:pk>/read/highlight/", views.save_highlight, name="highlight"),
    path("projects/<slug:slug>/literature/", views.project_literature, name="project"),
    path(
        "projects/<slug:slug>/literature/link/",
        views.ProjectReferenceCreateView.as_view(),
        name="project_link",
    ),
    path(
        "projects/<slug:slug>/literature/<int:pk>/edit/",
        views.ProjectReferenceUpdateView.as_view(),
        name="project_ref_edit",
    ),
    path(
        "projects/<slug:slug>/literature/<int:pk>/remove/",
        views.ProjectReferenceDeleteView.as_view(),
        name="project_ref_delete",
    ),
    path(
        "projects/<slug:slug>/literature/<int:pk>/status/",
        views.set_reading_status,
        name="set_status",
    ),
    path("projects/<slug:slug>/literature/queue/", views.reading_queue, name="queue"),
    path("projects/<slug:slug>/literature/matrix/", views.review_matrix, name="matrix"),
    path(
        "projects/<slug:slug>/literature/matrix/themes/new/",
        views.ThemeCreateView.as_view(),
        name="theme_create",
    ),
    path(
        "projects/<slug:slug>/literature/matrix/themes/<int:pk>/edit/",
        views.ThemeUpdateView.as_view(),
        name="theme_edit",
    ),
    path(
        "projects/<slug:slug>/literature/matrix/themes/<int:pk>/delete/",
        views.ThemeDeleteView.as_view(),
        name="theme_delete",
    ),
    path(
        "projects/<slug:slug>/literature/matrix/<int:theme_pk>/<int:link_pk>/toggle/",
        views.toggle_mark,
        name="toggle_mark",
    ),
    path(
        "projects/<slug:slug>/literature/matrix/marks/<int:pk>/note/",
        views.edit_mark_note,
        name="mark_note",
    ),
    path("projects/<slug:slug>/literature/export.bib", views.export_bib, name="export_bib"),
    path("projects/<slug:slug>/literature/report/", views.bib_report, name="report"),
]
