"""#515 — slack per milestone and the critical chain."""

import datetime
from pathlib import Path

import pytest
from django.conf import settings
from rest_framework.test import APIClient

from plans.dependencies import critical_chain, set_blockers, slack_map
from plans.tests.factories import MilestoneFactory, PhaseFactory
from projects.tests.factories import ProjectFactory

pytestmark = pytest.mark.django_db
D = datetime.date


def _plan():
    project = ProjectFactory(slug="deep")
    phase = PhaseFactory(project=project)
    ethics = MilestoneFactory(phase=phase, title="Ethics", due_date=D(2026, 10, 1))
    sample = MilestoneFactory(phase=phase, title="Sample", due_date=D(2026, 10, 2))  # 0 d slack
    prereg = MilestoneFactory(phase=phase, title="Prereg", due_date=D(2026, 11, 1))  # 29 d
    draft = MilestoneFactory(phase=phase, title="Draft", due_date=D(2026, 12, 1))
    side = MilestoneFactory(
        phase=phase, title="Side", due_date=D(2026, 9, 20)
    )  # 41 d: off the chain
    undated = MilestoneFactory(phase=phase, title="Undated", due_date=None)
    set_blockers(sample, [ethics.pk])
    set_blockers(prereg, [sample.pk, side.pk])
    set_blockers(draft, [prereg.pk])
    set_blockers(undated, [draft.pk])
    return project, ethics, sample, prereg, draft, side, undated


def test_slack_is_the_fewest_days_before_a_dated_dependant_moves():
    project, ethics, sample, prereg, draft, side, undated = _plan()
    s = slack_map(project)
    assert s[ethics.pk] == {"slack": 0, "tight_dependant": sample.pk}
    assert s[sample.pk]["slack"] == 29 and s[side.pk]["slack"] == 41
    assert (
        s[prereg.pk]["slack"] == 29 and s[draft.pk]["slack"] is None
    )  # undated dependants do not count
    assert undated.pk not in s


def test_critical_chain_runs_from_the_last_milestone_up_the_tightest_blockers():
    project, ethics, sample, prereg, draft, side, undated = _plan()
    chain = critical_chain(project)
    assert chain["ids"] == [ethics.pk, sample.pk, prereg.pk, draft.pk]
    assert (
        chain["titles"][0] == "Ethics"
        and chain["from"] == D(2026, 10, 1)
        and chain["to"] == D(2026, 12, 1)
    )
    assert chain["days"] == 61 and chain["slack"] == 0
    # The blocker due latest is the tight one: move Side after Sample and the chain follows it.
    side.due_date = D(2026, 10, 20)
    side.save()
    chain = critical_chain(project)
    assert chain["ids"] == [side.pk, prereg.pk, draft.pk] and chain["slack"] == 11
    assert chain["days"] == 42 and chain["from"] == D(2026, 10, 20)
    assert critical_chain(ProjectFactory(slug="void"))["ids"] == []


def test_slack_and_chain_over_the_api(owner):
    project, ethics, sample, prereg, draft, side, undated = _plan()
    client = APIClient(HTTP_HOST="127.0.0.1")
    client.credentials(HTTP_X_API_KEY=settings.ATLAS_API_KEY)
    plan = client.get("/api/v1/projects/deep/plan/").json()
    by = {m["title"]: m for m in plan["phases"][0]["milestones"]}
    assert by["Ethics"]["slack"] == 0 and by["Draft"]["slack"] is None
    assert plan["critical_chain"]["titles"][-1] == "Draft" and plan["critical_chain"]["slack"] == 0
    road = client.get("/api/v1/projects/deep/roadmap/").json()
    assert road["critical_chain"]["ids"] == plan["critical_chain"]["ids"]
    assert {m["title"]: m["slack"] for m in road["phases"][0]["milestones"]}["Sample"] == 29


def test_plan_and_roadmap_show_slack_and_the_chain():
    root = Path(settings.BASE_DIR) / "frontend" / "src" / "app" / "pages"
    plan = (root / "Plan.tsx").read_text()
    for needle in ('data-testid="slack-chip"', 'data-testid="critical-chain"', "critical_chain"):
        assert needle in plan, needle
    road = (root / "plan" / "Roadmap.tsx").read_text()
    assert "critical_chain" in road and "onChain" in road
