"""#473 — the figure audit: will every figure print well?"""

import struct
import zlib
from pathlib import Path

import pytest
from django.core.files.base import ContentFile

from projects.tests.factories import ProjectFactory
from writing import figures as F
from writing.models import Manuscript, ManuscriptFile

pytestmark = pytest.mark.django_db


def png(w: int, h: int) -> bytes:
    """A minimal valid PNG of the given size (one grey scanline repeated)."""
    raw = b"".join(b"\x00" + b"\x80" * w for _ in range(h))

    def chunk(kind, data):
        return (
            struct.pack(">I", len(data)) + kind + data + struct.pack(">I", zlib.crc32(kind + data))
        )

    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", struct.pack(">IIBBBBB", w, h, 8, 0, 0, 0, 0))
        + chunk(b"IDAT", zlib.compress(raw))
        + chunk(b"IEND", b"")
    )


def jpeg(w: int, h: int) -> bytes:
    # SOI, an APP0 segment, then a SOF0 with the size — enough for the header parser
    app0 = b"\xff\xe0" + struct.pack(">H", 16) + b"JFIF\x00" + b"\x00" * 9
    sof0 = (
        b"\xff\xc0"
        + struct.pack(">H", 11)
        + b"\x08"
        + struct.pack(">HH", h, w)
        + b"\x01\x01\x11\x00"
    )
    return b"\xff\xd8" + app0 + sof0


def test_header_parsers_and_printed_width():
    assert F.image_size(png(320, 200)) == ("png", 320, 200)
    assert F.image_size(jpeg(1200, 800)) == ("jpeg", 1200, 800)
    assert F.image_size(b"GIF89a" + struct.pack("<HH", 40, 30)) == ("gif", 40, 30)
    assert F.image_size(b"%PDF-1.4 ...") is None
    assert F.printed_width_in(r"width=0.8\textwidth") == 5.2
    assert F.printed_width_in(r"width=\columnwidth") == 3.25
    assert F.printed_width_in("width=8cm") == 3.15
    assert F.printed_width_in("width = 3in, keepaspectratio") == 3.0
    assert F.printed_width_in("scale=0.5") is None and F.printed_width_in(None) is None


def _paper(tex: str, assets: dict[str, bytes]):
    m = Manuscript.objects.create(project=ProjectFactory(), title="P")
    ManuscriptFile.objects.filter(manuscript=m).delete()
    ManuscriptFile.objects.create(manuscript=m, path="main.tex", kind="tex", content=tex)
    for path, data in assets.items():
        f = ManuscriptFile.objects.create(manuscript=m, path=path, kind="asset")
        f.asset.save(path.rsplit("/", 1)[-1], ContentFile(data), save=True)
    return Manuscript.objects.get(pk=m.pk)


def test_audit_measures_rasters_passes_vectors_and_flags_missing(monkeypatch):
    tex = "\n".join(
        [
            r"\includegraphics[width=0.6\textwidth]{figures/tiny}",  # 320 px / 3.9 in = 82 dpi
            r"\includegraphics[width=0.5\textwidth]{figures/mid.png}",  # 800 / 3.25 = 246
            r"\includegraphics[width=\columnwidth]{figures/big}",  # 1600 / 3.25 = 492
            r"\includegraphics{figures/plot.pdf}",
            r"\includegraphics{figures/nowhere}",
            r"\includegraphics[width=2in]{figures/photo}",  # jpeg 1200 / 2 = 600
        ]
    )
    m = _paper(
        tex,
        {
            "figures/tiny.png": png(320, 200),
            "figures/mid.png": png(800, 500),
            "figures/big.png": png(1600, 1000),
            "figures/plot.pdf": b"%PDF-1.4 vector",
            "figures/photo.jpg": jpeg(1200, 800),
            "figures/spare.png": png(10, 10),
            "notes.txt": b"not an image",
        },
    )
    out = F.audit_figures(m)
    by = {r["path"]: r for r in out["figures"]}
    assert out["count"] == 6 and out["fails"] == 2 and out["warns"] == 1
    assert by["figures/tiny.png"]["state"] == "fail" and by["figures/tiny.png"]["dpi"] == 82
    assert "≈ 1170 px wide" in by["figures/tiny.png"]["detail"]
    assert by["figures/mid.png"]["state"] == "warn" and by["figures/mid.png"]["dpi"] == 246
    assert by["figures/big.png"]["state"] == "ok" and by["figures/big.png"]["dpi"] == 492
    assert by["figures/plot.pdf"]["state"] == "ok" and by["figures/plot.pdf"]["format"] == "pdf"
    assert by["figures/nowhere"]["state"] == "fail"
    assert by["figures/photo.jpg"]["format"] == "jpeg" and by["figures/photo.jpg"]["dpi"] == 600
    assert by["figures/tiny.png"]["tex"] == "main.tex" and by["figures/tiny.png"]["line"] == 1
    assert out["unused"] == ["figures/spare.png"]
    assert out["summary"] == "2 of 6 figures will not print well."
    # a natural-size raster prints at 72 dpi; a huge file is flagged even when sharp
    monkeypatch.setattr(F, "MAX_BYTES", 100)
    out = F.audit_figures(_paper(r"\includegraphics{big}", {"big.png": png(1600, 1000)}))
    row = out["figures"][0]
    assert row["width_in"] == 22.22 and row["dpi"] == 72 and row["state"] == "fail"
    assert "MB — most venues cap" in row["detail"]


def test_preflight_row_and_api(client_logged_in):
    from writing.preflight import preflight

    m = _paper(r"\includegraphics[width=\textwidth]{f}", {"f.png": png(640, 400)})
    row = {c["key"]: c for c in preflight(m)["checks"]}["figure_quality"]
    assert row["state"] == "fail" and row["fix"] == {"kind": "line", "path": "main.tex", "line": 1}
    assert "98 dpi" in row["detail"]
    ManuscriptFile.objects.filter(manuscript=m, path="main.tex").update(content="no figures")
    keys = {c["key"] for c in preflight(Manuscript.objects.get(pk=m.pk))["checks"]}
    assert "figure_quality" not in keys
    r = client_logged_in.get(f"/api/v1/manuscripts/{m.id}/figure-audit/")
    assert r.status_code == 200 and r.json()["count"] == 0 and r.json()["unused"] == ["f.png"]


def test_studio_shows_the_figures_table_and_the_demo_has_a_figure():
    tsx = Path("frontend/src/app/pages/Studio.tsx").read_text()
    for needle in ('data-testid="figure-audit"', 'data-testid="figure-row"', "/figure-audit/`"):
        assert needle in tsx, needle
    seed = Path("core/management/commands/seed_demo.py").read_text()
    assert "figures/pilot-dprime.png" in seed and "_demo_png(1600, 1000)" in seed
