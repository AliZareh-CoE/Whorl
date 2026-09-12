"""#443 (backlog #78 + #107): timeline events carry their rendered body and open in place."""

from datetime import date
from pathlib import Path

import pytest

from core.timeline import project_timeline
from notes.models import Note
from projects.models import DecisionRecord
from projects.tests.factories import ProjectFactory
from research.models import ExperimentEntry

pytestmark = pytest.mark.django_db


def test_events_carry_rendered_bodies():
    project = ProjectFactory()
    DecisionRecord.objects.create(
        project=project,
        title="Dual task",
        context="Load alone was *ambiguous*.",
        decision="Use a dual-task paradigm.",
        alternatives="Single task with load; rejected.",
        decided_on=date(2026, 9, 1),
    )
    Note.objects.create(project=project, title="Pilot", body="n=9 so far, see [[Plan]].")
    ExperimentEntry.objects.create(project=project, title="Run 1", body="Setup: **two** blocks.")
    by = {e["kind"]: e for e in project_timeline(project)}
    assert "<strong>Context.</strong>" in by["decision"]["body_html"]
    assert "<em>ambiguous</em>" in by["decision"]["body_html"]
    assert "Alternatives." in by["decision"]["body_html"]
    assert "n=9 so far" in by["note"]["body_html"]
    assert "<strong>two</strong>" in by["experiment"]["body_html"]
    assert all("body_html" in e for e in project_timeline(project))


def test_long_note_is_previewed_and_empty_bodies_stay_empty():
    project = ProjectFactory()
    Note.objects.create(project=project, title="Long", body="word " * 1000)
    ExperimentEntry.objects.create(project=project, title="Bare", body="")
    by = {e["kind"]: e for e in project_timeline(project)}
    assert by["note"]["body_html"].endswith("…</p>") and len(by["note"]["body_html"]) < 2000
    assert by["experiment"]["body_html"] == ""


def test_api_and_page_wiring(client, settings, django_user_model):
    settings.ATLAS_API_KEY = "k"
    django_user_model.objects.create_superuser("owner", password="pw")
    project = ProjectFactory()
    DecisionRecord.objects.create(
        project=project, title="D", decision="Yes.", decided_on=date(2026, 9, 2)
    )
    data = client.get(f"/api/v1/projects/{project.slug}/timeline/", HTTP_X_API_KEY="k").json()
    events = data["events"] if isinstance(data, dict) else data
    assert any(e["kind"] == "decision" and "Yes." in e["body_html"] for e in events)
    src = (
        Path(settings.BASE_DIR) / "frontend" / "src" / "app" / "pages" / "Timeline.tsx"
    ).read_text()
    for needle in (
        'data-testid="timeline-expand"',
        'data-testid="timeline-body"',
        "<Prose html={e.body_html}",
        "aria-expanded",
    ):
        assert needle in src, needle


def test_bodies_can_be_skipped_and_the_overview_digest_skips_them(monkeypatch):
    """#444: the overview's week digest must not render every timeline body."""
    from core import timeline as timeline_mod
    from projects import overview as overview_mod

    project = ProjectFactory()
    DecisionRecord.objects.create(
        project=project, title="D", decision="Yes.", decided_on=date.today()
    )
    Note.objects.create(project=project, title="N", body="body")
    lean = project_timeline(project, bodies=False)
    assert lean and all(e["body_html"] == "" for e in lean)
    calls = []
    import core.rendering as rendering

    monkeypatch.setattr(rendering, "render_body", lambda *a, **k: calls.append(1) or "<p>x</p>")
    timeline_mod.project_timeline(project)  # bodies on → renders
    assert calls
    calls.clear()
    overview_mod.week_digest(project)
    assert calls == []
