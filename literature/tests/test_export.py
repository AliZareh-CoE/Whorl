"""#525: the library in every format colleagues use — RIS, CSL-JSON, CSV next to BibTeX."""

import csv
import io
import json
from pathlib import Path

import pytest
from django.conf import settings

from literature import export, library
from literature.importers import parse_csl_json, parse_ris
from literature.models import ProjectReference, Reference
from projects.tests.factories import ProjectFactory


@pytest.fixture
def refs(db):
    a = Reference.objects.create(
        title="Attention and Load: A Review",
        bibtex_key="lavie2020attention",
        year=2020,
        venue="J Attn",
        entry_type="article",
        authors=[{"family": "Lavie", "given": "Nilli"}, {"family": "de Fockert", "given": "J."}],
        doi="10.1/a",
        url="https://example.org/a",
        abstract="Load theory says\nthings.",
        extra={"volume": "12", "issue": "3", "pages": "100–120"},
        citation_count=42,
    )
    b = Reference.objects.create(
        title="Talk on Memory",
        bibtex_key="cowan2018talk",
        year=2018,
        venue="Proc. CogSci",
        entry_type="inproceedings",
        authors=[{"family": "Cowan", "given": ""}],
    )
    library.bulk([a.pk], "tag", value="load")
    project = ProjectFactory(name="P")
    ProjectReference.objects.create(project=project, reference=a, reading_status="read")
    return a, b, project


def _rows():
    return list(Reference.objects.prefetch_related("tags", "project_links__project").order_by("id"))


def test_ris_round_trips_through_the_importer(refs):
    a, b, _ = refs
    text = export.export_ris(_rows())
    assert "TY  - JOUR" in text and "TY  - CONF" in text and text.count("ER  - ") == 2
    assert "AU  - Lavie, Nilli" in text and "AU  - de Fockert, J." in text and "AU  - Cowan" in text
    assert "SP  - 100" in text and "EP  - 120" in text and "KW  - load" in text
    assert "AB  - Load theory says things." in text  # newlines folded
    metas = parse_ris(text)
    assert [m["title"] for m in metas] == [a.title, b.title]
    assert metas[0]["doi"] == "10.1/a" and metas[0]["year"] == 2020
    assert metas[0]["authors"][0] == {"family": "Lavie", "given": "Nilli"}
    assert metas[0]["venue"] == "J Attn" and metas[0]["entry_type"] == "article"
    assert metas[1]["entry_type"] == "inproceedings" and metas[1]["venue"] == "Proc. CogSci"


def test_csl_json_round_trips_through_the_importer(refs):
    a, b, _ = refs
    text = export.export_csl_json(_rows())
    items = json.loads(text)
    assert items[0]["id"] == "lavie2020attention" and items[0]["type"] == "article-journal"
    assert items[0]["issued"] == {"date-parts": [[2020]]} and items[0]["page"] == "100–120"
    assert items[0]["keyword"] == "load" and items[1]["type"] == "paper-conference"
    assert "issued" not in json.loads(export.export_csl_json([b]))[0] or b.year
    metas = parse_csl_json(text)
    assert [m["title"] for m in metas] == [a.title, b.title]
    assert metas[0]["doi"] == "10.1/a" and metas[0]["authors"][1]["family"] == "de Fockert"
    assert metas[1]["entry_type"] == "inproceedings"


def test_csv_has_one_row_per_paper_with_a_bom(refs):
    a, b, project = refs
    text = export.export_csv(_rows())
    assert text.startswith("﻿")
    rows = list(csv.reader(io.StringIO(text.lstrip("﻿"))))
    assert rows[0] == list(export.CSV_COLUMNS)
    first = dict(zip(rows[0], rows[1], strict=True))
    assert first["authors"] == "Lavie, Nilli; de Fockert, J." and first["year"] == "2020"
    assert first["volume"] == "12" and first["pages"] == "100–120" and first["doi"] == "10.1/a"
    assert first["tags"] == "load" and first["projects"] == f"{project.slug}: read"
    assert first["has_pdf"] == "no" and first["citation_count"] == "42"
    second = dict(zip(rows[0], rows[2], strict=True))
    assert second["authors"] == "Cowan" and second["projects"] == "" and second["year"] == "2018"


def test_render_picks_writer_and_refuses_unknown(refs):
    text, ctype, name = export.render(_rows(), "ris")
    assert ctype.startswith("application/x-research-info-systems") and name == "atlas-library.ris"
    _text, ctype, name = export.render(_rows(), "csl-json")
    assert "csl+json" in ctype and name == "atlas-library.json"
    _text, ctype, name = export.render(_rows(), "")
    assert ctype.startswith("application/x-bibtex") and name == "atlas-library.bib"
    with pytest.raises(ValueError, match="Unknown export format"):
        export.render(_rows(), "docx")
    assert export.export_ris([]) == "" and export.export_csl_json([]) == "[]\n"


def test_api_export_formats(client, refs, settings, owner):
    a, b, project = refs
    settings.ATLAS_API_KEY = "k"
    headers = {"HTTP_HOST": "127.0.0.1", "HTTP_X_API_KEY": "k"}
    resp = client.get("/api/v1/references/export/?fmt=ris", **headers)
    assert resp.status_code == 200 and resp["Content-Type"].startswith(
        "application/x-research-info-systems"
    )
    assert resp["Content-Disposition"] == 'attachment; filename="atlas-library.ris"'
    assert resp.content.decode().count("ER  - ") == 2
    resp = client.get(f"/api/v1/references/export/?fmt=csv&project={project.slug}", **headers)
    assert resp["Content-Disposition"].endswith('"atlas-library.csv"')
    body = resp.content.decode()
    assert "lavie2020attention" in body and "cowan2018talk" not in body
    resp = client.get(f"/api/v1/references/export/?fmt=csl&ids={b.pk}", **headers)
    assert [i["id"] for i in json.loads(resp.content)] == ["cowan2018talk"]
    resp = client.get("/api/v1/references/export/?author=lavie", **headers)  # default: BibTeX
    assert resp["Content-Type"].startswith("application/x-bibtex")
    assert b"@article{lavie2020attention" in resp.content
    resp = client.get("/api/v1/references/export/?fmt=docx", **headers)
    assert resp.status_code == 400 and "Unknown export format" in resp.json()["fmt"][0]
    assert client.get("/api/v1/references/export/?fmt=ris").status_code == 401


def test_ui_wiring():
    lib = (
        Path(settings.BASE_DIR) / "frontend" / "src" / "app" / "pages" / "Library.tsx"
    ).read_text()
    for needle in (
        'data-testid="export-links"',
        '<ExportLinks query={toQuery(effective, 1)} what="this view"',
        'what="the selection"',
        '["ris", ".ris"',
        '["csv", ".csv"',
        "fmt=${fmt}",
    ):
        assert needle in lib, needle


@pytest.mark.django_db
def test_csv_neutralises_formula_cells():
    from literature.export import CSV_COLUMNS, _cell, export_csv

    titles = ['=HYPERLINK("http://evil")', "+1", "-x", "@cmd", "Plain"]
    refs = [
        Reference.objects.create(title=title, bibtex_key=f"inj{i}")
        for i, title in enumerate(titles)
    ]
    rows = list(csv.reader(io.StringIO(export_csv(refs).lstrip("\ufeff"))))
    col = CSV_COLUMNS.index("title")
    got = [row[col] for row in rows[1:]]
    assert got == ['\'=HYPERLINK("http://evil")', "'+1", "'-x", "'@cmd", "Plain"]
    assert _cell(None) == ""
