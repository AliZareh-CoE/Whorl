from django.urls import path

from . import views

app_name = "plans"

urlpatterns = [
    path("<slug:slug>/plan/", views.plan, name="plan"),
    path("<slug:slug>/plan/phases/new/", views.PhaseCreateView.as_view(), name="phase_create"),
    path(
        "<slug:slug>/plan/phases/<int:pk>/edit/",
        views.PhaseUpdateView.as_view(),
        name="phase_edit",
    ),
    path(
        "<slug:slug>/plan/phases/<int:pk>/delete/",
        views.PhaseDeleteView.as_view(),
        name="phase_delete",
    ),
    path(
        "<slug:slug>/plan/phases/<int:phase_pk>/milestones/new/",
        views.MilestoneCreateView.as_view(),
        name="milestone_create",
    ),
    path(
        "<slug:slug>/plan/milestones/<int:pk>/edit/",
        views.MilestoneUpdateView.as_view(),
        name="milestone_edit",
    ),
    path(
        "<slug:slug>/plan/milestones/<int:pk>/delete/",
        views.MilestoneDeleteView.as_view(),
        name="milestone_delete",
    ),
    path(
        "<slug:slug>/plan/milestones/<int:pk>/toggle/",
        views.milestone_toggle,
        name="milestone_toggle",
    ),
    path(
        "<slug:slug>/plan/milestones/<int:milestone_pk>/tasks/new/",
        views.TaskCreateView.as_view(),
        name="task_create",
    ),
    path("<slug:slug>/plan/tasks/<int:pk>/edit/", views.TaskUpdateView.as_view(), name="task_edit"),
    path(
        "<slug:slug>/plan/tasks/<int:pk>/delete/",
        views.TaskDeleteView.as_view(),
        name="task_delete",
    ),
    path("<slug:slug>/plan/tasks/<int:pk>/toggle/", views.task_toggle, name="task_toggle"),
    path("<slug:slug>/questions/", views.QuestionListView.as_view(), name="questions"),
    path("<slug:slug>/questions/new/", views.QuestionCreateView.as_view(), name="question_create"),
    path(
        "<slug:slug>/questions/<int:pk>/edit/",
        views.QuestionUpdateView.as_view(),
        name="question_edit",
    ),
    path(
        "<slug:slug>/questions/<int:pk>/delete/",
        views.QuestionDeleteView.as_view(),
        name="question_delete",
    ),
]
