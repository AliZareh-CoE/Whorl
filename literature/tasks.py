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
