from huey.contrib.djhuey import db_task

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
