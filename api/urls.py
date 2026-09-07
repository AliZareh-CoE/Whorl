from django.conf import settings
from django.contrib.auth.decorators import login_not_required, login_required
from django.http import HttpResponse
from django.urls import include, path
from django.utils.crypto import constant_time_compare
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from rest_framework.routers import DefaultRouter

from . import views


@login_not_required
def _schema_view(request):
    """Schema for humans (session) and machines (X-API-Key) — never anonymous."""
    key = request.headers.get("X-API-Key", "")
    key_ok = settings.ATLAS_API_KEY and constant_time_compare(key, settings.ATLAS_API_KEY)
    if not (request.user.is_authenticated or key_ok):
        return HttpResponse(status=401, headers={"WWW-Authenticate": "X-API-Key"})
    return SpectacularAPIView.as_view()(request)


router = DefaultRouter()
router.register("projects", views.ProjectViewSet)
router.register("phases", views.PhaseViewSet)
router.register("milestones", views.MilestoneViewSet)
router.register("tasks", views.TaskViewSet)
router.register("questions", views.ResearchQuestionViewSet)
router.register("decisions", views.DecisionRecordViewSet)
router.register("manuscript-files", views.ManuscriptFileViewSet, basename="manuscript-files")
router.register("folders", views.FolderViewSet)
router.register("tags", views.TagViewSet)
router.register("documents", views.DocumentViewSet)
router.register("references", views.ReferenceViewSet)
router.register("library-tags", views.LibraryTagViewSet)
router.register("library-views", views.SavedViewViewSet)
router.register("highlights", views.HighlightViewSet)
router.register("project-references", views.ProjectReferenceViewSet)
router.register("quick-capture", views.QuickCaptureViewSet)
router.register("todos", views.TodoItemViewSet)
router.register("notes", views.NoteViewSet)
router.register("hypotheses", views.HypothesisViewSet)
router.register("evidence", views.EvidenceViewSet)
router.register("experiments", views.ExperimentEntryViewSet)
router.register("datasets", views.DatasetViewSet)
router.register("protocols", views.ProtocolViewSet)
router.register("manuscripts", views.ManuscriptViewSet)
router.register("prompts", views.PromptViewSet)

app_name = "api"

urlpatterns = [
    path("v1/search/", views.SearchAPIView.as_view(), name="search"),
    path("v1/dashboard/", views.DashboardAPIView.as_view(), name="dashboard"),
    path("v1/weekly-review/", views.WeeklyReviewAPIView.as_view(), name="weekly_review"),
    path(
        "v1/comments/<slug:kind>/<int:object_id>/",
        views.CommentsAPIView.as_view(),
        name="comments",
    ),
    path("v1/pet/", views.PetAPIView.as_view(), name="pet"),
    path("v1/achievements/", views.AchievementsAPIView.as_view(), name="achievements"),
    path("v1/connect/", views.ConnectAPIView.as_view(), name="connect"),
    path("v1/demo/", views.DemoAPIView.as_view(), name="demo"),
    path("v1/diagnostics/", views.DiagnosticsAPIView.as_view(), name="diagnostics"),
    path("v1/diagnostics/warm-latex/", views.LatexWarmupAPIView.as_view(), name="latex_warmup"),
    path("v1/client-errors/", views.ClientErrorAPIView.as_view(), name="client_errors"),
    path("v1/access-events/", views.AccessEventsAPIView.as_view(), name="access_events"),
    path("v1/calendar.ics", views.CalendarFeedView.as_view(), name="calendar_ics"),
    path("v1/backup.zip", views.BackupView.as_view(), name="backup_zip"),
    path("v1/restore/", views.RestoreAPIView.as_view(), name="restore"),
    path("v1/connect/skills/", views.ConnectSkillsAPIView.as_view(), name="connect_skills"),
    path("v1/connect/test/", views.ConnectTestAPIView.as_view(), name="connect_test"),
    path("v1/bots/", views.BotsAPIView.as_view(), name="bots"),
    path("v1/bots/<slug:slug>/action/", views.BotActionAPIView.as_view(), name="bot_action"),
    path("v1/", include(router.urls)),
    path("schema/", _schema_view, name="schema"),
    # DRF APIViews opt out of LoginRequiredMiddleware, so gate the docs page explicitly
    path(
        "docs/",
        login_required(SpectacularSwaggerView.as_view(url_name="api:schema")),
        name="docs",
    ),
]
