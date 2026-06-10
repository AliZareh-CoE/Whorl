from django.urls import path

from . import views

app_name = "projects"

urlpatterns = [
    path("", views.ProjectListView.as_view(), name="list"),
    path("new/", views.ProjectCreateView.as_view(), name="create"),
    path("<slug:slug>/", views.project_overview, name="overview"),
    path("<slug:slug>/edit/", views.ProjectUpdateView.as_view(), name="edit"),
    path("<slug:slug>/delete/", views.ProjectDeleteView.as_view(), name="delete"),
    path("<slug:slug>/archive/", views.project_archive, name="archive"),
    path("<slug:slug>/graph/", views.project_graph_page, name="graph"),
    path("<slug:slug>/graph.json", views.project_graph_json, name="graph_json"),
    path("<slug:slug>/graph/sync/", views.project_graph_sync, name="graph_sync"),
    path("<slug:slug>/decisions/", views.DecisionListView.as_view(), name="decisions"),
    path("<slug:slug>/decisions/new/", views.DecisionCreateView.as_view(), name="decision_create"),
    path(
        "<slug:slug>/decisions/<int:pk>/edit/",
        views.DecisionUpdateView.as_view(),
        name="decision_edit",
    ),
    path(
        "<slug:slug>/decisions/<int:pk>/delete/",
        views.DecisionDeleteView.as_view(),
        name="decision_delete",
    ),
]
