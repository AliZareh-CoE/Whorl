"""The bots themselves (Owner idea #7). Each run function returns a one-line result.

Bots report into the quick-capture inbox — the existing triage point — rather than
inventing a notification system.
"""

import datetime

from django.utils import timezone

from notes.models import QuickCapture


def _capture_once(text: str) -> bool:
    """Drop a line in the inbox unless the identical line is already there unprocessed."""
    _, created = QuickCapture.objects.get_or_create(text=text, processed=False)
    return created


def run_deadline_reminder() -> str:
    """Inbox reminders for milestones due within 3 days and manuscripts within 7."""
    from plans.models import Milestone
    from writing.models import Manuscript

    today = timezone.localdate()
    created = 0
    milestones = Milestone.objects.filter(
        completed_at__isnull=True,
        due_date__lte=today + datetime.timedelta(days=3),
    ).select_related("phase__project")
    for milestone in milestones:
        when = (
            f"OVERDUE since {milestone.due_date}"
            if milestone.due_date < today
            else f"due {milestone.due_date}"
        )
        created += _capture_once(
            f"⏰ Milestone “{milestone.title}” ({milestone.phase.project.name}) is {when}."
        )
    manuscripts = Manuscript.objects.filter(
        deadline__gte=today, deadline__lte=today + datetime.timedelta(days=7)
    ).exclude(status__in=["published", "shelved"])
    for manuscript in manuscripts:
        created += _capture_once(
            f"⏰ Manuscript “{manuscript.title}” deadline is {manuscript.deadline}."
        )
    return f"{created} new reminder(s)."


def run_retraction_watch() -> str:
    """Weekly-ish retraction sweep over every reference with a DOI."""
    from literature.models import Reference
    from literature.services import check_retractions

    references = Reference.objects.exclude(doi__isnull=True)
    findings = [f for f in check_retractions(references) if f["level"] == "error"]
    for finding in findings:
        _capture_once(f"🚨 {finding['message']}")
    return f"{references.count()} DOI(s) checked, {len(findings)} retraction(s) flagged."


BOTS = {
    "deadline-reminder": {
        "name": "Deadline reminder",
        "description": "Drops an inbox reminder when a milestone is due within 3 days "
        "or a manuscript deadline within 7.",
        "run": run_deadline_reminder,
    },
    "retraction-watch": {
        "name": "Retraction watch",
        "description": "Checks every DOI in the library against Crossref retraction "
        "notices and flags hits to the inbox.",
        "run": run_retraction_watch,
    },
}


def run_bot(slug: str) -> str:
    """Run one bot now and record the outcome on its state row."""
    from .models import Bot

    spec = BOTS[slug]
    state, _ = Bot.objects.get_or_create(slug=slug)
    try:
        result = spec["run"]()
    except Exception as exc:  # bots must never take the scheduler down
        result = f"failed: {exc.__class__.__name__}: {exc}"[:300]
    state.last_run_at = timezone.now()
    state.last_result = result[:300]
    state.save()
    return result


def run_enabled_bots() -> list[str]:
    from .models import Bot

    enabled = set(Bot.objects.filter(enabled=True, slug__in=BOTS).values_list("slug", flat=True))
    return [f"{slug}: {run_bot(slug)}" for slug in BOTS if slug in enabled]
