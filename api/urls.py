from django.contrib.auth.decorators import login_not_required
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter

from . import views

router = DefaultRouter()
router.register("projects", views.ProjectViewSet)
router.register("phases", views.PhaseViewSet)
router.register("milestones", views.MilestoneViewSet)
router.register("tasks", views.TaskViewSet)
router.register("questions", views.ResearchQuestionViewSet)
router.register("decisions", views.DecisionRecordViewSet)
router.register("folders", views.FolderViewSet)
router.register("tags", views.TagViewSet)
router.register("documents", views.DocumentViewSet)
router.register("references", views.ReferenceViewSet)
router.register("project-references", views.ProjectReferenceViewSet)
router.register("quick-capture", views.QuickCaptureViewSet)
router.register("notes", views.NoteViewSet)

app_name = "api"

urlpatterns = [
    path("v1/search/", views.SearchAPIView.as_view(), name="search"),
    path("v1/", include(router.urls)),
    path("schema/", login_not_required(SpectacularAPIView.as_view()), name="schema"),
    path(
        "docs/",
        login_not_required(SpectacularSwaggerView.as_view(url_name="api:schema")),
        name="docs",
    ),
]
