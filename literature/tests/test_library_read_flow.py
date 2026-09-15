"""#450 (backlog #85): the reading flow runs over any filtered Library set, not one queue."""

from pathlib import Path

import pytest
from django.conf import settings

from literature import library
from literature.models import ProjectReference, Reference
from projects.tests.factories import ProjectFactory

KEY = "test-key"
HEADERS = {"HTTP_X_API_KEY": KEY}


@pytest.fixture(autouse=True)
def api_key(settings):
    settings.ATLAS_API_KEY = KEY


@pytest.fixture
def owner(django_user_model):
    return django_user_model.objects.create_superuser("owner", password="pw")


@pytest.mark.django_db
def test_flow_honours_filters_and_resolves_the_link(client, owner):
    a_proj, b_proj = ProjectFactory(name="A"), ProjectFactory(name="B")
    both = Reference.objects.create(title="Shared paper", bibtex_key="shared2020", year=2020)
    Reference.objects.create(title="Unfiled paper", bibtex_key="lone2019", year=2019)
    tagged = Reference.objects.create(title="Tagged paper", bibtex_key="tag2021", year=2021)
    ProjectReference.objects.create(project=a_proj, reference=both, reading_status="read")
    unread = ProjectReference.objects.create(
        project=b_proj, reference=both, reading_status="to_read"
    )
    library.bulk([tagged.pk], "tag", value="pilot")
    data = client.get("/api/v1/references/reading-flow/?tag=pilot", **HEADERS).json()
    assert [p["reference"]["bibtex_key"] for p in data["papers"]] == ["tag2021"]
    assert data["papers"][0]["id"] is None and data["papers"][0]["project"] is None
    data = client.get("/api/v1/references/reading-flow/?q=paper&sort=title", **HEADERS).json()
    by = {p["reference"]["bibtex_key"]: p for p in data["papers"]}
    assert by["shared2020"]["id"] == unread.pk and by["shared2020"]["project"] == b_proj.slug
    assert by["lone2019"]["id"] is None
    data = client.get(f"/api/v1/references/reading-flow/?project={a_proj.slug}", **HEADERS).json()
    assert [p["project"] for p in data["papers"]] == [a_proj.slug]
    assert data["papers"][0]["reading_status"] == "read"


def test_ui_wiring():
    app = Path(settings.BASE_DIR) / "frontend" / "src" / "app"
    flow = (app / "pages" / "ReadingFlow.tsx").read_text()
    for needle in (
        "/references/reading-flow/",
        "const libraryMode",
        "in no project yet",
        'navigate("/library")',
    ):
        assert needle in flow, needle
    assert 'path="library/read"' in (app / "main.tsx").read_text()
    lib = (app / "pages" / "Library.tsx").read_text()
    assert 'data-testid="read-these"' in lib and "/library/read?" in lib


@pytest.mark.django_db
def test_flow_rows_carry_progress(client, owner):
    project = ProjectFactory(name="A")
    ref = Reference.objects.create(
        title="Half read", bibtex_key="half2020", year=2020, last_page=5, page_count=12
    )
    ProjectReference.objects.create(project=project, reference=ref, reading_status="skimmed")
    data = client.get("/api/v1/references/reading-flow/", **HEADERS).json()
    assert data["papers"][0]["progress"] == {
        "page": 5,
        "pages": 12,
        "percent": 42,
        "last_read_at": None,
    }
    data = client.get(f"/api/v1/projects/{project.slug}/reading-flow/", **HEADERS).json()
    assert (
        data["papers"][0]["progress"]["page"] == 5
        and data["papers"][0]["progress"]["percent"] == 42
    )
    flow = (
        Path(settings.BASE_DIR) / "frontend" / "src" / "app" / "pages" / "ReadingFlow.tsx"
    ).read_text()
    assert 'data-testid="flow-progress"' in flow and "paper.progress.percent" in flow


def test_author_lens_ui_wiring():
    lib = (
        Path(settings.BASE_DIR) / "frontend" / "src" / "app" / "pages" / "Library.tsx"
    ).read_text()
    for needle in (
        'data-testid="author-facet"',
        'data-testid="author-link"',
        'toggle("author", a.name)',
        'onAuthor={(family) => toggle("author", family)}',
        'author: ""',
    ):
        assert needle in lib, needle


def test_library_address_ui_wiring():
    """#526: every Library view has an address — the filters come from the URL and go back to
    it (replace, after the search debounce), an incoming address resets them, the year range
    has chips, and the header offers "Copy link"."""
    lib = (
        Path(settings.BASE_DIR) / "frontend" / "src" / "app" / "pages" / "Library.tsx"
    ).read_text()
    for needle in (
        "function viewQuery(",
        "function fromUrl(",
        'k === "sort" && f[k] === "added"',
        "useState<Filters>(() => fromUrl(window.location.search))",
        'navigate(qs ? `/library?${qs}` : "/library", { replace: true })',
        "if (qInput !== q || feedQInput !== feedQ) return;",
        'data-testid="mode-copy-link"',
        "}, [location.search]);",
        # #532: the modes have addresses — read on arrival, written on change, cleared by /library
        "function modeFromUrl(",
        "function addressOf(",
        'if (p.get("feeds") === "1") return { kind: "feeds", feed: id("feed"), seen: p.get("seen") === "1", fq:',
        'if (p.get("citing") === "1") return { kind: "citing", reference: id("reference"), seen: p.get("seen") === "1" };',
        'if (p.get("duplicates") === "1") return { kind: "duplicates" };',
        "const qs = addressOf(effective, mode);",
        "setFilters(next); setQInput(next.q); applyMode(nextMode);",
        'const [feedMode, setFeedMode] = useState(mode0.kind === "feeds");',
        'const [citeMode, setCiteMode] = useState(mode0.kind === "citing");',
        'const [dupMode, setDupMode] = useState(mode0.kind === "duplicates");',
        'data-testid="dup-panel"',
        'year_min: "", year_max: ""',
        'if (k === "year_min") return `from ${v}`;',
        'data-testid="copy-link"',
        "Copied a link to this view.",
    ):
        assert needle in lib, needle
