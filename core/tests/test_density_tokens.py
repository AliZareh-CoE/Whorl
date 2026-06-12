"""Density lint (Backlog #154, Owner idea #25).

.card / .card-title in assets/css/app.css define the one card rhythm. New templates
must use the token instead of hand-rolling the pattern, or every #25 density pass
has to re-hunt the same class soup. Deliberate outliers (p-2 chips, p-6 heroes)
remain legal — only the card-sized paddings are flagged.
"""

from pathlib import Path

from django.conf import settings

TEMPLATES = Path(settings.BASE_DIR) / "templates"
HAND_ROLLED = (
    "rounded border border-stone-200 bg-white p-4",
    "rounded border border-stone-200 bg-white p-5",
)


def test_templates_use_the_card_token():
    offenders = []
    for template in TEMPLATES.rglob("*.html"):
        text = template.read_text()
        for pattern in HAND_ROLLED:
            if pattern in text:
                offenders.append(f"{template.relative_to(TEMPLATES)}: {pattern}")
    assert not offenders, 'Hand-rolled card markup — use class="card" instead:\n' + "\n".join(
        offenders
    )


def test_card_token_exists_in_css_source():
    css = (Path(settings.BASE_DIR) / "assets" / "css" / "app.css").read_text()
    assert ".card {" in css and ".card-title {" in css
