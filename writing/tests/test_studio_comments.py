"""#414 — comments inside the Studio: manuscript-wide listing, delete, editor wiring."""

import pytest

from core.models import Comment
from writing.models import ManuscriptFile
from writing.tests.factories import ManuscriptFactory

pytestmark = pytest.mark.django_db


def test_manuscript_comments_listing_and_delete(client_logged_in):
    m = ManuscriptFactory(latex_source="")
    main = ManuscriptFile.objects.create(
        manuscript=m, path="main.tex", content="a\nb", is_main=True
    )
    method = ManuscriptFile.objects.create(
        manuscript=m, path="sections/method.tex", content="c\nd\ne"
    )
    asset = ManuscriptFile.objects.create(manuscript=m, path="fig.png", kind="asset")
    Comment.objects.create(target=main, body="tighten", page=2)
    Comment.objects.create(target=method, body="cite Lavie here", page=3)
    Comment.objects.create(target=method, body="general", page=None)
    Comment.objects.create(target=asset, body="not listed")
    other = ManuscriptFactory(latex_source="")
    other_file = ManuscriptFile.objects.create(manuscript=other, path="main.tex", is_main=True)
    Comment.objects.create(target=other_file, body="someone else's", page=1)

    rows = client_logged_in.get(f"/api/v1/manuscripts/{m.pk}/comments/").json()["comments"]
    assert [(r["path"], r["line"], r["body"]) for r in rows] == [
        ("sections/method.tex", None, "general"),
        ("sections/method.tex", 3, "cite Lavie here"),
        ("main.tex", 2, "tighten"),
    ]
    assert rows[0]["file"] == method.pk
    gone = client_logged_in.delete(f"/api/v1/comments/{rows[2]['id']}/")
    assert gone.status_code == 204 and not Comment.objects.filter(pk=rows[2]["id"]).exists()
    assert client_logged_in.delete(f"/api/v1/comments/{rows[2]['id']}/").status_code == 404
    assert (
        len(client_logged_in.get(f"/api/v1/manuscripts/{m.pk}/comments/").json()["comments"]) == 2
    )


def test_studio_wiring():
    src = open("frontend/src/app/pages/Studio.tsx").read()
    for needle in (
        'data-testid="studio-comments"',
        "ad.setCommentLines(",
        "ad.onGutterClick(",
        "/comments/manuscript_file/${",
        "/comments/${c.id}/",
        '"comments", MessageSquare',
    ):
        assert needle in src, needle
