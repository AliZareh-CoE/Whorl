"""#453 (backlog #133): every archive Atlas writes names its members through one guard."""

import io
import zipfile
from pathlib import Path

import pytest
from django.conf import settings

from core.archives import is_safe_archive_name, safe_archive_name


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("main.tex", "main.tex"),
        ("sections/intro.tex", "sections/intro.tex"),
        ("./figures//fig.png", "figures/fig.png"),
        ("figures\\fig.png", "figures/fig.png"),
        ("/etc/passwd", None),
        ("\\\\server\\share", None),
        ("C:\\Users\\x.tex", None),
        ("../outside.tex", None),
        ("sections/../../outside.tex", None),
        ("bad\x00name.tex", None),
        ("", None),
        (".", None),
        ("..", None),
    ],
)
def test_safe_archive_name(raw, expected):
    assert safe_archive_name(raw) == expected
    assert is_safe_archive_name(raw) is (expected is not None)


def test_every_archive_writer_goes_through_the_guard():
    base = Path(settings.BASE_DIR)
    for rel in ("writing/views.py", "projects/vault.py", "core/backup.py"):
        src = (base / rel).read_text()
        assert "safe_archive_name" in src, rel


@pytest.mark.django_db
def test_submission_zip_skips_an_unsafe_row(client, django_user_model):
    from writing.models import ManuscriptFile
    from writing.tests.factories import ManuscriptFactory

    django_user_model.objects.create_superuser("owner", password="pw")
    client.login(username="owner", password="pw")
    ms = ManuscriptFactory()
    ManuscriptFile.objects.create(
        manuscript=ms, path="main.tex", content="x", kind="tex", is_main=True
    )
    # a row injected past validation (the model validator refuses this on save via full_clean only)
    ManuscriptFile.objects.bulk_create(
        [ManuscriptFile(manuscript=ms, path="../evil.tex", content="boom", kind="tex")]
    )
    r = client.get(f"/projects/{ms.project.slug}/writing/{ms.pk}/submission.zip")
    assert r.status_code == 200
    names = zipfile.ZipFile(io.BytesIO(r.content)).namelist()
    assert "main.tex" in names and not any(".." in n for n in names)
