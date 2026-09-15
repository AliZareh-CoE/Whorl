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
