"""Card-section headings use the .card-title token (Backlog #155).

The standalone section-heading pattern (mb-2 + the uppercase label classes) has one
home: the .card-title component class. New templates must use it, not re-roll the
classes — same grep-guard discipline as .card / the escape and density lints. (Table
headers and tight editor-rail labels with bespoke spacing are intentionally exempt.)
"""

from pathlib import Path

from django.conf import settings

TEMPLATES = Path(settings.BASE_DIR) / "templates"
HAND_ROLLED = "mb-2 text-xs font-medium uppercase tracking-wide text-stone-400"


def test_section_headings_use_card_title():
    offenders = [
        str(t.relative_to(TEMPLATES))
        for t in TEMPLATES.rglob("*.html")
        if HAND_ROLLED in t.read_text()
    ]
    assert not offenders, 'Hand-rolled section heading — use class="card-title":\n' + "\n".join(
        offenders
    )
