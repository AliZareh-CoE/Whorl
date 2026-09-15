from huey import crontab
from huey.contrib.djhuey import db_periodic_task, db_task

from projects.models import Project

from .sync import sync_project_citations


@db_task()
def sync_citations_task(project_id: int):
    project = Project.objects.get(pk=project_id)
    return sync_project_citations(project)


@db_task()
def fetch_oa_pdf_task(reference_id: int):
    from .models import Reference
    from .oa import fetch_and_attach_pdf

    return fetch_and_attach_pdf(Reference.objects.get(pk=reference_id))


@db_task()
def extract_text_task(reference_id: int):
    from .fulltext import extract_text
    from .models import Reference

    reference = Reference.objects.filter(pk=reference_id).first()
    return extract_text(reference) if reference else None


@db_periodic_task(crontab(hour=4, minute=20))
def check_retractions_task():
    """#527: the daily retraction sweep — stale papers (30 days) against Crossref, bounded."""
    from .retractions import check_stale

    return check_stale()


@db_periodic_task(crontab(hour=4, minute=40))
def check_preprints_task():
    """#529: the daily preprint sweep — stale arXiv preprints against arXiv / Semantic Scholar."""
    from .preprints import check_stale

    return check_stale()


@db_periodic_task(crontab(hour=5, minute=0))
def check_citations_task():
    """#530: the daily citation sweep — papers not asked about for seven days, against OpenAlex."""
    from .citing import check_stale

    return check_stale()


@db_periodic_task(crontab(hour=5, minute=20))
def find_pdfs_task():
    """#544: the nightly PDF sweep — papers without a PDF, never looked at first, then the
    ones not asked about for thirty days; off when ATLAS_AUTO_FETCH_PDF is false."""
    from django.conf import settings

    if not settings.ATLAS_AUTO_FETCH_PDF:
        return None
    from .oa import sweep_missing

    return sweep_missing()


@db_periodic_task(crontab(hour="*/6", minute=20))
def refresh_feeds_task():
    """#531: the feed sweep — feeds not fetched for twelve hours, every six hours."""
    from .feeds import refresh_stale

    return refresh_stale()
