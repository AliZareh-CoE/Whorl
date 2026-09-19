import os

from huey import crontab
from huey.contrib.djhuey import db_periodic_task, task

# Changes whenever this file is redeployed — lets `doctor` spot stale workers.
CODE_STAMP = os.path.getmtime(__file__)


@task()
def doctor_ping():
    """Round-trip task for `manage.py doctor`: proves a worker is alive and current."""
    return CODE_STAMP


@db_periodic_task(crontab(hour=5, minute=40))
def prune_todo_trash_task():
    """#570: the nightly Trash sweep — Today items deleted more than thirty days ago go for
    good. The desktop runs the same sweep from its scheduler thread."""
    from core.todos import prune_trash

    return prune_trash()
