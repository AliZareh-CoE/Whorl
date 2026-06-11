import os

from huey.contrib.djhuey import task

# Changes whenever this file is redeployed — lets `doctor` spot stale workers.
CODE_STAMP = os.path.getmtime(__file__)


@task()
def doctor_ping():
    """Round-trip task for `manage.py doctor`: proves a worker is alive and current."""
    return CODE_STAMP
