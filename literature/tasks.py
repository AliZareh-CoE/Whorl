from huey.contrib.djhuey import db_task

from projects.models import Project

from .sync import sync_project_citations


@db_task()
def sync_citations_task(project_id: int):
    project = Project.objects.get(pk=project_id)
    return sync_project_citations(project)
