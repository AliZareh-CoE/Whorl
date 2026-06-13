"""No-CDN guard for vendored pdf.js (file-workspace epic #30, slice 2c-i).

pdf.js is vendored under static/vendor/pdfjs/ and served locally so the app works
offline. This fails the build if a CDN pdf.js reference creeps back into the editor
glue or any template (the class of bug that broke the offline editor before).
"""

import re
from pathlib import Path

from django.conf import settings

ROOT = Path(settings.BASE_DIR)
CDN_PDFJS = re.compile(r"(jsdelivr|cdnjs|unpkg)\S*pdfjs", re.IGNORECASE)


def test_no_cdn_pdfjs_references():
    offenders = []
    targets = [ROOT / "static" / "js" / "latex-editor.js", *(ROOT / "templates").rglob("*.html")]
    for path in targets:
        if CDN_PDFJS.search(path.read_text()):
            offenders.append(str(path.relative_to(ROOT)))
    assert not offenders, (
        "CDN pdf.js reference — vendor it under static/vendor/pdfjs/:\n" + "\n".join(offenders)
    )


def test_vendored_pdfjs_present():
    base = ROOT / "static" / "vendor" / "pdfjs"
    assert (base / "pdf.min.mjs").exists()
    assert (base / "pdf.worker.min.mjs").exists()
