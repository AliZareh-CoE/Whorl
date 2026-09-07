"""#430: the README's demo GIF stays present, real, referenced and small."""

from pathlib import Path

from django.conf import settings

BASE = Path(settings.BASE_DIR)


def test_demo_gif_is_present_real_referenced_and_small():
    gif = BASE / "docs" / "demo.gif"
    assert gif.exists(), "run `make demo-gif` against a seeded dev server"
    with gif.open("rb") as fh:
        assert fh.read(6) in (b"GIF89a", b"GIF87a")
    assert gif.stat().st_size < 4_000_000, "the README GIF must stay under 4 MB"
    assert "docs/demo.gif" in (BASE / "README.md").read_text()
    assert "demo-gif:" in (BASE / "Makefile").read_text()


def test_demo_script_covers_the_loop():
    src = (BASE / "scripts" / "demo_gif.py").read_text()
    for needle in ("/library", "/read", "/notes/", "/graph", "/editor", "/matrix", "/connect"):
        assert needle in src, needle
    assert "compile" in src and "add paper" in src
