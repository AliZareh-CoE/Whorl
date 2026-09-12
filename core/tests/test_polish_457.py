"""#457 (backlog #105 + #99): every matrix theme links to its candidates; Review sections copy."""

from pathlib import Path

from django.conf import settings

APP = Path(settings.BASE_DIR) / "frontend" / "src" / "app" / "pages"


def test_matrix_theme_links_and_review_section_copy():
    matrix = (APP / "Matrix.tsx").read_text()
    assert 'data-testid="theme-queue"' in matrix and "candidates →" in matrix
    review = (APP / "Review.tsx").read_text()
    assert 'data-testid="section-copy"' in review and "line?: (x: T) => string" in review
    assert review.count("line={") >= 5  # every section passes its Markdown line
