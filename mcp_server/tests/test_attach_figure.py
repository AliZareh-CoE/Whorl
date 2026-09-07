"""#441 (backlog #127): Claude can put a figure into a manuscript's source tree."""

import pytest

from mcp_server import client as mcp_client
from mcp_server import server
from mcp_server.client import AtlasClientError

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 24


def test_client_posts_multipart_for_a_new_asset(monkeypatch, tmp_path):
    fig = tmp_path / "pilot-dprime.png"
    fig.write_bytes(PNG)
    seen = {}
    monkeypatch.setattr(mcp_client, "list_manuscript_files", lambda mid: {"results": []})

    def fake(method, path, **kw):
        seen.update(method=method, path=path, data=kw.get("data"), files=kw.get("files"))
        return {"id": 9, "path": kw["data"]["path"], "kind": "asset"}

    monkeypatch.setattr(mcp_client, "_request", fake)
    out = server.attach_manuscript_figure(3, "figures/pilot-dprime.png", str(fig))
    assert seen["method"] == "POST" and seen["path"] == "/manuscript-files/"
    assert seen["data"] == {"manuscript": 3, "path": "figures/pilot-dprime.png", "kind": "asset"}
    name, _handle, ctype = seen["files"]["asset"]
    assert name == "pilot-dprime.png" and ctype == "image/png"
    assert out["id"] == 9
    assert "\\includegraphics[width=\\linewidth]{figures/pilot-dprime.png}" in out["include"]
    assert (
        "\\label{fig:pilot-dprime}" in out["include"]
        and "\\caption{pilot dprime}" in out["include"]
    )


def test_client_patches_an_existing_asset(monkeypatch, tmp_path):
    fig = tmp_path / "fig.pdf"
    fig.write_bytes(b"%PDF-1.4\n")
    monkeypatch.setattr(
        mcp_client,
        "list_manuscript_files",
        lambda mid: {"results": [{"id": 12, "path": "figures/fig.pdf"}]},
    )
    seen = {}
    monkeypatch.setattr(
        mcp_client, "_request", lambda m, p, **kw: seen.update(method=m, path=p) or {"id": 12}
    )
    mcp_client.attach_manuscript_asset(3, "figures/fig.pdf", str(fig))
    assert seen == {"method": "PATCH", "path": "/manuscript-files/12/"}


def test_missing_local_file_is_a_clear_error(tmp_path):
    with pytest.raises(AtlasClientError, match="No such file"):
        mcp_client.attach_manuscript_asset(1, "figures/x.png", str(tmp_path / "nope.png"))
