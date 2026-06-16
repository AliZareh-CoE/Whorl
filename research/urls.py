from django.urls import path

from . import views

app_name = "research"

urlpatterns = [
    path("<slug:slug>/research/", views.hypothesis_ledger, name="ledger"),
    path(
        "<slug:slug>/research/hypotheses/new/",
        views.HypothesisCreateView.as_view(),
        name="hypothesis_create",
    ),
    path(
        "<slug:slug>/research/hypotheses/<int:pk>/edit/",
        views.HypothesisUpdateView.as_view(),
        name="hypothesis_edit",
    ),
    path(
        "<slug:slug>/research/hypotheses/<int:pk>/delete/",
        views.HypothesisDeleteView.as_view(),
        name="hypothesis_delete",
    ),
    path(
        "<slug:slug>/research/hypotheses/<int:hypothesis_pk>/evidence/new/",
        views.evidence_create,
        name="evidence_create",
    ),
    path(
        "<slug:slug>/research/evidence/<int:pk>/delete/",
        views.evidence_delete,
        name="evidence_delete",
    ),
    path("<slug:slug>/research/experiments/", views.experiment_log, name="experiments"),
    path(
        "<slug:slug>/research/experiments/new/",
        views.ExperimentCreateView.as_view(),
        name="experiment_create",
    ),
    path(
        "<slug:slug>/research/experiments/<int:pk>/edit/",
        views.ExperimentUpdateView.as_view(),
        name="experiment_edit",
    ),
    path(
        "<slug:slug>/research/experiments/<int:pk>/delete/",
        views.ExperimentDeleteView.as_view(),
        name="experiment_delete",
    ),
    path("<slug:slug>/research/datasets/", views.dataset_list, name="datasets"),
    path(
        "<slug:slug>/research/datasets/new/",
        views.DatasetCreateView.as_view(),
        name="dataset_create",
    ),
    path(
        "<slug:slug>/research/datasets/<int:pk>/edit/",
        views.DatasetUpdateView.as_view(),
        name="dataset_edit",
    ),
    path(
        "<slug:slug>/research/datasets/<int:pk>/delete/",
        views.DatasetDeleteView.as_view(),
        name="dataset_delete",
    ),
    path("<slug:slug>/research/protocols/", views.protocol_list, name="protocols"),
    path(
        "<slug:slug>/research/protocols/new/",
        views.ProtocolCreateView.as_view(),
        name="protocol_create",
    ),
    path(
        "<slug:slug>/research/protocols/<int:pk>/new-version/",
        views.protocol_new_version,
        name="protocol_new_version",
    ),
]
