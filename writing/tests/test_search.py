"""#476 — find and replace across the manuscript's text files."""

from pathlib import Path

import pytest

from projects.tests.factories import ProjectFactory
from writing import search as S
from writing.models import Manuscript, ManuscriptFile

pytestmark = pytest.mark.django_db


def _paper(files: dict[str, str]):
    m = Manuscript.objects.create(project=ProjectFactory(), title="P")
    ManuscriptFile.objects.filter(manuscript=m).delete()
    for path, content in files.items():
        ManuscriptFile.objects.create(manuscript=m, path=path, content=content)
    return Manuscript.objects.get(pk=m.pk)


FILES = {
    "main.tex": "Working-memory load degrades vigilance.\nLoad costs shrink.\n\\input{sections/m}",
    "sections/m.tex": "Each block paired a load with a memory set.",
    "references.bib": "@article{load2020, title={Load theory}}",
    "figures/plot.png": "not text",
}


def test_search_plain_case_and_regex():
    m = _paper(FILES)
    out = S.search_files(m, "load")
    assert out["count"] == 5 and out["files"] == ["main.tex", "references.bib", "sections/m.tex"]
    first = out["hits"][0]
    assert first == {
        "file": "main.tex",
        "line": 1,
        "col": 16,
        "end": 20,
        "text": "Working-memory load degrades vigilance.",
    }
    assert S.search_files(m, "Load", case=True)["count"] == 2
    assert [h["line"] for h in S.search_files(m, r"^Load \w+", regex=True)["hits"]] == [2]
    assert S.search_files(m, "(?=e)", regex=True)["count"] == 0  # empty matches are dropped
    assert not out["truncated"] and out["query"] == "load"
    with pytest.raises(S.BadPattern):
        S.search_files(m, "")
    with pytest.raises(S.BadPattern):
        S.search_files(m, "(", regex=True)


def test_search_caps_the_hit_list(monkeypatch):
    monkeypatch.setattr(S, "MAX_HITS", 3)
    out = S.search_files(_paper(FILES), "load")
    assert out["count"] == 3 and out["truncated"] is True


def test_replace_across_files_and_within_a_subset():
    m = _paper(FILES)
    out = S.replace_in_files(m, "load", "demand")
    assert out["replaced"] == 5 and out["files"] == ["main.tex", "references.bib", "sections/m.tex"]
    texts = {f.path: f.content for f in m.files.all()}
    assert (
        texts["main.tex"].startswith("Working-memory demand degrades")
        and "demand costs" in texts["main.tex"]
    )
    assert texts["references.bib"] == "@article{demand2020, title={demand theory}}"
    assert texts["figures/plot.png"] == "not text"  # assets are never touched
    # a subset, case-sensitive, regex groups, and a literal backslash in plain mode
    m = _paper(FILES)
    out = S.replace_in_files(m, "Load", "Demand", case=True, files=["main.tex"])
    assert out["replaced"] == 1 and out["files"] == ["main.tex"]
    assert m.files.get(path="references.bib").content == FILES["references.bib"]
    out = S.replace_in_files(m, r"(\w+)-memory", r"\1–memory", regex=True)
    assert out["replaced"] == 1 and "Working–memory" in m.files.get(path="main.tex").content
    out = S.replace_in_files(m, "memory set", r"memory \emph{set}")
    assert out["replaced"] == 1 and r"\emph{set}" in m.files.get(path="sections/m.tex").content
    assert S.replace_in_files(m, "nowhere", "x")["replaced"] == 0


def test_api_search_and_replace(client_logged_in):
    m = _paper(FILES)
    r = client_logged_in.get(f"/api/v1/manuscripts/{m.id}/search/?q=load")
    assert r.status_code == 200 and r.json()["count"] == 5
    r = client_logged_in.get(f"/api/v1/manuscripts/{m.id}/search/?q=Load&case=1")
    assert r.json()["count"] == 2
    assert (
        client_logged_in.get(f"/api/v1/manuscripts/{m.id}/search/?q=(&regex=1").status_code == 400
    )
    assert client_logged_in.get(f"/api/v1/manuscripts/{m.id}/search/").status_code == 400
    r = client_logged_in.post(
        f"/api/v1/manuscripts/{m.id}/replace/",
        {"q": "load", "replacement": "demand", "files": ["sections/m.tex"]},
        content_type="application/json",
    )
    assert r.status_code == 200 and r.json() == {
        "query": "load",
        "replacement": "demand",
        "replaced": 1,
        "files": ["sections/m.tex"],
    }
    bad = client_logged_in.post(
        f"/api/v1/manuscripts/{m.id}/replace/",
        {"q": "x", "replacement": "y", "files": "no"},
        content_type="application/json",
    )
    assert bad.status_code == 400


def test_studio_has_the_search_panel():
    tsx = Path("frontend/src/app/pages/Studio.tsx").read_text()
    for needle in (
        '["search", SearchIcon, "Search"]',
        'data-testid="studio-search"',
        'data-testid="search-hit"',
        'data-testid="replace-all"',
        "/search/?q=",
        "/replace/`",
        "Find in project",
    ):
        assert needle in tsx, needle
