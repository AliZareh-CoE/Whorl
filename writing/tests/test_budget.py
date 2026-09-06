"""Writing v2 slice 3 — venue budget."""

import pytest

from literature.tests.factories import ReferenceFactory
from projects.tests.factories import ProjectFactory
from writing import budget
from writing.models import Manuscript, ManuscriptFile, ManuscriptReference

pytestmark = pytest.mark.django_db


def test_clean_limits():
    assert budget.clean_limits(
        {"words": "8000", "figures": 6, "pages": "", "bogus": 3, "tables": "x", "references": 0}
    ) == {"words": 8000, "figures": 6}
    assert budget.clean_limits("nope") == {} and budget.clean_limits(None) == {}


def test_budget_states_and_summary():
    project = ProjectFactory()
    m = Manuscript.objects.create(
        project=project,
        title="Paper",
        target_venue="JEP:G",
        abstract="one two three four",
        venue_limits={"words": 10, "abstract_words": 4, "figures": 1, "references": 5},
    )
    ManuscriptFile.objects.create(
        manuscript=m,
        path="main.tex",
        content=r"\section{Intro} "
        + "word " * 12
        + r"\begin{figure}x\end{figure}\begin{figure*}y\end{figure*}\begin{table}t\end{table}",
        is_main=True,
    )
    ManuscriptReference.objects.create(manuscript=m, reference=ReferenceFactory())
    out = budget.budget(m)
    by = {i["key"]: i for i in out["items"]}
    assert by["words"]["used"] >= 12 and by["words"]["state"] == "over"
    assert by["abstract_words"] == {
        "key": "abstract_words",
        "label": "Abstract words",
        "used": 4,
        "limit": 4,
        "ratio": 1.0,
        "state": "near",
    }
    assert by["figures"]["used"] == 2 and by["figures"]["state"] == "over"
    assert (
        by["tables"]["used"] == 1
        and by["tables"]["limit"] is None
        and by["tables"]["state"] == "unset"
    )
    assert by["references"]["used"] == 1 and by["references"]["state"] == "ok"
    assert "pages" not in by  # unknown without a compile and no limit set
    assert (
        out["over"] == ["words", "figures"] and out["summary"] == "over the limit on words, figures"
    )
    m.venue_limits = {}
    m.save()
    assert budget.budget(m)["summary"] == "no limits set"


def test_budget_api_and_limits_validation(client, settings, django_user_model):
    settings.ATLAS_API_KEY = "k"
    django_user_model.objects.create_superuser("owner", password="pw")
    m = Manuscript.objects.create(project=ProjectFactory(slug="deep"), title="Paper")
    patched = client.patch(
        f"/api/v1/manuscripts/{m.pk}/",
        {"venue_limits": {"words": "7000", "junk": 1, "pages": "12"}},
        content_type="application/json",
        HTTP_X_API_KEY="k",
    )
    assert patched.status_code == 200 and patched.json()["venue_limits"] == {
        "words": 7000,
        "pages": 12,
    }
    out = client.get(f"/api/v1/manuscripts/{m.pk}/budget/", HTTP_X_API_KEY="k").json()
    assert out["limits"] == {"words": 7000, "pages": 12} and out["summary"] == "within every limit"
    pages = next(i for i in out["items"] if i["key"] == "pages")
    assert pages["used"] is None and pages["limit"] == 12 and pages["state"] == "unset"
