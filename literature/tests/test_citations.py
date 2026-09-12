"""Formatted citations: six styles, in-text forms, bibliographies, graceful gaps."""

import pytest

from literature import citations
from literature.models import Reference


def _ref(**kw):
    base = dict(
        title="Perceptual load as a necessary condition for selective attention",
        bibtex_key="lavie1995perceptual",
        authors=[{"family": "Lavie", "given": "Nilli"}],
        year=1995,
        venue="Journal of Experimental Psychology: Human Perception and Performance",
        entry_type="article",
        doi="10.1037/0096-1523.21.3.451",
        extra={"volume": "21", "issue": "3", "pages": "451-468"},
    )
    base.update(kw)
    return Reference(**base)


TWO = [{"family": "Lavie", "given": "Nilli"}, {"family": "Cowan", "given": "Nelson"}]
MANY = [{"family": f"Author{i}", "given": f"G{i}"} for i in range(8)]


def test_apa_entry_and_intext():
    c = citations.cite(_ref(), "apa")
    assert c["text"] == (
        "Lavie, N. (1995). Perceptual load as a necessary condition for selective attention. "
        "Journal of Experimental Psychology: Human Perception and Performance, 21(3), 451-468. "
        "https://doi.org/10.1037/0096-1523.21.3.451"
    )
    assert (
        "<i>Journal of Experimental Psychology: Human Perception and Performance</i>" in c["html"]
    )
    assert c["intext"] == "(Lavie, 1995)"
    assert citations.cite(_ref(authors=TWO), "apa")["intext"] == "(Lavie & Cowan, 1995)"
    assert citations.cite(_ref(authors=MANY), "apa")["intext"] == "(Author0 et al., 1995)"
    assert citations.cite(_ref(authors=TWO), "apa")["text"].startswith(
        "Lavie, N., & Cowan, N. (1995)."
    )


def test_mla_entry_and_intext():
    c = citations.cite(_ref(authors=TWO), "mla")
    assert c["text"] == (
        "Lavie, Nilli, and Nelson Cowan. “Perceptual load as a necessary condition for selective attention.” "
        "Journal of Experimental Psychology: Human Perception and Performance, vol. 21, no. 3, 1995, "
        "pp. 451-468, https://doi.org/10.1037/0096-1523.21.3.451."
    )
    assert c["intext"] == "(Lavie and Cowan)"
    assert citations.cite(_ref(authors=MANY), "mla")["text"].startswith("Author0, G0, et al.")


def test_chicago_harvard_vancouver_ieee_entries():
    r = _ref(authors=TWO)
    assert citations.cite(r, "chicago")["text"] == (
        "Lavie, Nilli and Nelson Cowan. 1995. “Perceptual load as a necessary condition for selective attention.” "
        "Journal of Experimental Psychology: Human Perception and Performance 21 (3): 451-468. "
        "https://doi.org/10.1037/0096-1523.21.3.451"
    )
    assert citations.cite(r, "chicago")["intext"] == "(Lavie and Cowan 1995)"
    assert citations.cite(r, "harvard")["text"] == (
        "Lavie, N. and Cowan, N. (1995) ‘Perceptual load as a necessary condition for selective attention’, "
        "Journal of Experimental Psychology: Human Perception and Performance, 21(3), pp. 451-468. "
        "Available at: https://doi.org/10.1037/0096-1523.21.3.451."
    )
    assert citations.cite(r, "vancouver")["text"] == (
        "Lavie N, Cowan N. Perceptual load as a necessary condition for selective attention. "
        "Journal of Experimental Psychology: Human Perception and Performance. 1995;21(3):451-468. "
        "doi:10.1037/0096-1523.21.3.451"
    )
    assert citations.cite(r, "ieee")["text"] == (
        "N. Lavie and N. Cowan, “Perceptual load as a necessary condition for selective attention,” "
        "Journal of Experimental Psychology: Human Perception and Performance, vol. 21, no. 3, pp. 451-468, 1995, "
        "doi: 10.1037/0096-1523.21.3.451."
    )


def test_author_count_rules():
    assert citations.cite(_ref(authors=MANY), "vancouver")["text"].startswith(
        "Author0 G, Author1 G, Author2 G, Author3 G, Author4 G, Author5 G, et al."
    )
    assert citations.cite(_ref(authors=MANY), "ieee")["text"].startswith("G. Author0 et al.,")
    assert citations.cite(_ref(authors=MANY), "harvard")["text"].startswith(
        "Author0, G. et al. (1995)"
    )


def test_missing_fields_degrade_gracefully():
    stub = _ref(authors=[], year=None, venue="", doi=None, extra={}, url="")
    apa = citations.cite(stub, "apa")
    assert apa["text"].startswith(
        "Perceptual load as a necessary condition for selective attention. (n.d.)."
    )
    assert apa["intext"] == "(Perceptual load as a necessary condition, n.d.)"
    proc = _ref(entry_type="inproceedings", venue="Proc. CogSci", extra={})
    assert "In Proc. CogSci." in citations.cite(proc, "apa")["text"]
    assert "In: Proc. CogSci" in citations.cite(proc, "harvard")["text"]


def test_html_escapes_and_italicises():
    c = citations.cite(_ref(title="Load & <attention>"), "apa")
    assert "Load &amp; &lt;attention&gt;" in c["html"]
    assert "<i>" in c["html"] and "<i>" not in c["text"]


def test_unknown_style_rejected():
    with pytest.raises(ValueError):
        citations.cite(_ref(), "bluebook")


@pytest.mark.django_db
def test_bibliography_sorts_author_date_and_numbers_ieee():
    b = Reference.objects.create(
        title="Beta", bibtex_key="b", year=2001, authors=[{"family": "Zed", "given": "A"}]
    )
    a = Reference.objects.create(
        title="Alpha", bibtex_key="a", year=2000, authors=[{"family": "Adams", "given": "B"}]
    )
    apa = citations.bibliography([b, a], "apa")
    assert [e["reference_id"] for e in apa["entries"]] == [a.pk, b.pk]  # alphabetical
    assert apa["text"].startswith("Adams, B. (2000).") and "<p>" in apa["html"]
    ieee = citations.bibliography([b, a], "ieee")
    assert [e["reference_id"] for e in ieee["entries"]] == [b.pk, a.pk]  # given order
    assert (
        ieee["entries"][0]["text"].startswith("[1] A. Zed,")
        and ieee["entries"][1]["intext"] == "[2]"
    )
    van = citations.bibliography([a], "vancouver")
    assert (
        van["entries"][0]["text"].startswith("1. Adams B.") and van["entries"][0]["intext"] == "(1)"
    )


def test_metadata_mappers_keep_volume_issue_pages():
    from literature.services import _crossref_to_meta, _openalex_to_meta

    cr = _crossref_to_meta(
        {
            "DOI": "10.1/x",
            "title": ["T"],
            "volume": "12",
            "issue": "4",
            "page": "1-9",
            "issued": {"date-parts": [[2020]]},
        }
    )
    assert (cr["extra"]["volume"], cr["extra"]["issue"], cr["extra"]["pages"]) == ("12", "4", "1-9")
    oa = _openalex_to_meta(
        {
            "id": "https://openalex.org/W1",
            "title": "T",
            "biblio": {"volume": "3", "issue": None, "first_page": "10", "last_page": "20"},
        }
    )
    assert (oa["extra"]["volume"], oa["extra"]["issue"], oa["extra"]["pages"]) == ("3", "", "10-20")
