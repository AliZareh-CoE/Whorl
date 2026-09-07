"""SyncTeX parsing and lookups (#378)."""

import gzip

import pytest

from writing import synctex

SAMPLE = """SyncTeX Version:1
Input:1:{work}/main.tex
Input:2:
Input:7:{work}/sections/method.tex
Output:pdf
Magnification:1000
Unit:1
X Offset:0
Y Offset:0
Content:
!362
{{1
[1,7:4736287,46220575:26673152,41484288,0
(1,3:8799519,8868410:22609920,658715,11324
g1,3:8799519,8868410
k1,3:31409439,8868410:19263496
)
(1,5:8799519,10304500:22609920,462029,126483
g1,4:10492314,10304500
g1,4:12478710,10304500
g1,5:31409439,10304500
)
(7,2:8799519,20000000:22609920,462029,126483
g7,2:8799519,20000000
)
]
}}1
"""


def _map(tmp_path):
    return synctex.parse_synctex(SAMPLE.format(work=tmp_path), tmp_path)


def test_parse_folds_records_into_one_rect_per_line(tmp_path):
    mapping = _map(tmp_path)
    assert mapping["files"] == ["main.tex", "sections/method.tex"]
    rows = mapping["pages"]["1"]
    lines = {(r[0], r[1]) for r in rows}
    assert (0, 3) in lines and (0, 4) in lines and (0, 5) in lines and (1, 2) in lines
    # the section box on line 3: 22609920 sp wide ≈ 345 pt, y ≈ 135 pt from the top
    row3 = next(r for r in rows if r[:2] == [0, 3])
    assert 340 < row3[4] < 350 and 120 < row3[3] < 136
    assert "7" not in mapping["pages"]  # only page 1 exists


def test_forward_and_inverse_lookups(tmp_path):
    mapping = _map(tmp_path)
    spot = synctex.forward(mapping, "main.tex", 4)
    assert spot["page"] == 1 and spot["line"] == 4
    assert synctex.forward(mapping, "main.tex", 1)["line"] == 3  # nearest line after it
    assert synctex.forward(mapping, "sections/method.tex", 2)["page"] == 1
    assert synctex.forward(mapping, "nope.tex", 1) is None
    hit = synctex.inverse(mapping, 1, x=200, y=135)
    assert hit == {"file": "main.tex", "line": 3}
    assert synctex.inverse(mapping, 1, x=200, y=305)["file"] == "sections/method.tex"
    assert synctex.inverse(mapping, 2, 0, 0) is None
    assert synctex.inverse({}, 1, 0, 0) is None


def test_read_gzipped_file(tmp_path):
    path = tmp_path / "main.synctex.gz"
    path.write_bytes(gzip.compress(SAMPLE.format(work=tmp_path).encode()))
    assert synctex.read_synctex(path, tmp_path)["files"][0] == "main.tex"


@pytest.mark.django_db
def test_synctex_api(client_logged_in):
    from writing.tests.factories import ManuscriptFactory

    m = ManuscriptFactory()
    assert client_logged_in.get(f"/api/v1/manuscripts/{m.id}/synctex/").json() == {
        "files": [],
        "pages": {},
    }
    m.synctex = {"files": ["main.tex"], "pages": {"1": [[0, 3, 72.0, 100.0, 300.0, 12.0]]}}
    m.save()
    assert client_logged_in.get(f"/api/v1/manuscripts/{m.id}/synctex/").json()["files"] == [
        "main.tex"
    ]
    assert (
        client_logged_in.get(f"/api/v1/manuscripts/{m.id}/compile-status/").json()["synctex"]
        is True
    )
