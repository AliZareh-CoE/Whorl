from huey import crontab
from huey.contrib.djhuey import db_periodic_task

from .registry import run_enabled_bots


@db_periodic_task(crontab(hour=6, minute=0))
def run_bots_daily():
    """One daily tick; each enabled bot decides what's worth surfacing."""
    return run_enabled_bots()
