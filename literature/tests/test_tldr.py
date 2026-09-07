"""tl;dr per section (#395)."""

import pytest

from literature import tldr as mod
from literature.models import Reference, ReferenceText

PAGES = [
    "A Study of Attention\nAlice Author\nAbstract\nWe study attention under load. Load changes what is attended. "
    "Our experiments show a strategic effect. This matters for theories of capacity.\n1 Introduction\n"
    "Attention research has long asked whether load is structural. Many studies disagree on this point. "
    "We argue the effect is strategic rather than structural. The rest of the paper tests this claim.",
    "2 Methods\nForty participants completed a dual task. Load was manipulated by set size. "
    "Accuracy and reaction time were recorded. Trials were counterbalanced across blocks.\n"
    "3 Results\nHigh load reduced accuracy on the secondary task. The effect vanished when the task was easy. "
    "Reaction times followed the same pattern. The interaction was reliable.",
    "4 Discussion\nThe pattern favours a strategic account. Structural accounts predict a constant cost. "
    "We found none. Future work should vary incentives.\nReferences\nSmith 2001. Jones 2004.",
]


def test_split_sections_finds_headings_and_pages():
    sections = mod.split_sections(PAGES)
    titles = [s["title"] for s in sections]
    assert titles == ["Abstract", "Introduction", "Methods", "Results", "Discussion"]
    assert [s["page"] for s in sections] == [1, 1, 2, 2, 3]
    assert "Smith 2001" not in " ".join(s["text"] for s in sections)  # stops at the references


def test_heading_rules():
    assert mod._is_heading("3.2 Experimental Setup", known_only=False) == "Experimental Setup"
    assert mod._is_heading("Results", known_only=True) == "Results"
    assert mod._is_heading("This is a sentence that ends here.", known_only=False) is None
    assert (
        mod._is_heading("Some Arbitrary Capitalised Line", known_only=False) is None
    )  # unnumbered, unknown


@pytest.mark.django_db
def test_tldr_from_pdf_text_then_abstract_then_nothing():
    ref = Reference.objects.create(title="T", bibtex_key="t", abstract="")
    assert mod.tldr(ref)["source"] == "none"
    ref.abstract = (
        "We study attention. Load matters. The effect is strategic. Capacity theories must adapt."
    )
    ref.save()
    out = mod.tldr(ref)
    assert out["source"] == "abstract" and out["sections"][0]["sentences"]
    ReferenceText.objects.create(reference=ref, pages=PAGES, body=" ".join(PAGES), page_count=3)
    ref = Reference.objects.get(pk=ref.pk)
    out = mod.tldr(ref)
    assert out["source"] == "pdf-text"
    assert [s["title"] for s in out["sections"]][:2] == ["Abstract", "Introduction"]
    assert all(1 <= len(s["sentences"]) <= 2 for s in out["sections"])


@pytest.mark.django_db
def test_tldr_endpoint(client, settings, django_user_model):
    settings.ATLAS_API_KEY = "k"
    django_user_model.objects.create_superuser("owner", password="pw")
    ref = Reference.objects.create(title="T", bibtex_key="t", abstract="One. Two. Three.")
    data = client.get(f"/api/v1/references/{ref.pk}/tldr/", HTTP_X_API_KEY="k").json()
    assert data["source"] == "abstract" and data["sections"][0]["title"] == "Abstract"


def test_ui_uses_the_section_tldr():
    from pathlib import Path

    from django.conf import settings

    base = Path(settings.BASE_DIR)
    library = (base / "frontend/src/app/pages/Library.tsx").read_text()
    flow = (base / "frontend/src/app/pages/ReadingFlow.tsx").read_text()
    assert 'data-testid="tldr-block"' in library and "/tldr/`" in library
    assert 'data-testid="flow-tldr"' in flow and "/tldr/`" in flow


def test_reader_has_margin_comment_markers():
    """#396: comments anchored to a page show as bubbles in the reader's margin."""
    from pathlib import Path

    from django.conf import settings

    base = Path(settings.BASE_DIR)
    reader = (base / "frontend/src/app/pages/library/PdfReader.tsx").read_text()
    library = (base / "frontend/src/app/pages/Library.tsx").read_text()
    assert 'data-testid="comment-marker"' in reader and 'data-testid="comment-add"' in reader
    assert "comments={(readerComments.data?.comments ?? [])" in library and "line: page" in library
    assert ".pdf-margin-marker" in (base / "assets/css/app.css").read_text()
