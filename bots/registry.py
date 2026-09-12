"""The bots themselves (Owner idea #7). Each run function returns a one-line result.

Bots report into the quick-capture inbox — the existing triage point — rather than
inventing a notification system.
"""

import contextvars
import datetime

from django.utils import timezone

from notes.models import QuickCapture

# #423: the BotRun being executed, so captures a bot files carry it
_CURRENT_RUN: contextvars.ContextVar = contextvars.ContextVar("atlas_bot_run", default=None)


def _capture_once(text: str) -> bool:
    """File one capture unless an unprocessed identical one already sits in the inbox."""
    run = _CURRENT_RUN.get()
    _, created = QuickCapture.objects.get_or_create(
        text=text, processed=False, defaults={"bot_run": run}
    )
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


def run_citation_sync() -> str:
    """Refresh OpenAlex citation edges for every active project."""
    from literature.sync import sync_project_citations
    from projects.models import Project

    lines = []
    for project in Project.objects.filter(status__in=["planning", "active"]):
        state = sync_project_citations(project)
        lines.append(f"{project.slug}: {state.message or state.status}")
    return "; ".join(lines) if lines else "no active projects."


def run_retraction_watch() -> str:
    """Weekly-ish retraction sweep over every reference with a DOI."""
    from literature.models import Reference
    from literature.services import check_retractions

    references = Reference.objects.exclude(doi__isnull=True)
    findings = [f for f in check_retractions(references) if f["level"] == "error"]
    for finding in findings:
        _capture_once(f"🚨 {finding['message']}")
    return f"{references.count()} DOI(s) checked, {len(findings)} retraction(s) flagged."


def run_weekly_digest() -> str:
    """Drop a skimmable 'last week' summary into the inbox (Owner idea #94).

    Reuses the weekly-review data layer; runs Monday-ish for the week just ended.
    """
    from core.reviews import weekly_review

    review = weekly_review(weeks_back=1)
    counts = {
        "papers read": len(review["papers_read"]),
        "notes": len(review["notes_written"]),
        "milestones": len(review["milestones_done"]),
        "decisions": len(review["decisions"]),
        "experiments": len(review["experiments"]),
    }
    total = sum(counts.values())
    if total == 0:
        return "quiet week — nothing to report."
    parts = ", ".join(f"{n} {label}" for label, n in counts.items() if n)
    _capture_once(f"📅 Last week ({review['start']}–{review['end']}): {parts}. See /review.")
    return f"digest posted: {parts}."


BOTS = {
    "deadline-reminder": {
        "name": "Deadline reminder",
        "description": "Drops an inbox reminder when a milestone is due within 3 days "
        "or a manuscript deadline within 7.",
        "run": run_deadline_reminder,
    },
    "citation-sync": {
        "name": "Citation sync",
        "description": "Refreshes OpenAlex citation edges and citation counts for every "
        "active project, keeping the knowledge graph current.",
        "run": run_citation_sync,
    },
    "retraction-watch": {
        "name": "Retraction watch",
        "description": "Checks every DOI in the library against Crossref retraction "
        "notices and flags hits to the inbox.",
        "run": run_retraction_watch,
    },
    "weekly-digest": {
        "name": "Weekly digest",
        "description": "Posts a skimmable summary of last week's research — papers read, "
        "notes, milestones, decisions — to the inbox. Pairs with the Review page.",
        "run": run_weekly_digest,
    },
}


def run_bot(slug: str) -> str:
    """Run one bot now, record the outcome on its state row and in run history."""
    from .models import Bot, BotRun

    spec = BOTS[slug]
    state, _ = Bot.objects.get_or_create(slug=slug)
    run = BotRun.objects.create(bot=state, ok=True, result="running")  # #423: exists during the run
    token = _CURRENT_RUN.set(run)
    ok = True
    try:
        result = spec["run"]()
    except Exception as exc:  # bots must never take the scheduler down
        ok = False
        result = f"failed: {exc.__class__.__name__}: {exc}"[:300]
    finally:
        _CURRENT_RUN.reset(token)
    state.last_run_at = timezone.now()
    state.last_result = result[:300]
    state.save()
    run.ok = ok
    run.result = result[:300]
    run.save(update_fields=["ok", "result"])
    # keep history tidy: last 20 runs per bot
    stale = state.runs.values_list("pk", flat=True)[20:]
    if stale:
        BotRun.objects.filter(pk__in=list(stale)).delete()
    return result


def run_enabled_bots() -> list[str]:
    from .models import Bot

    enabled = set(Bot.objects.filter(enabled=True, slug__in=BOTS).values_list("slug", flat=True))
    return [f"{slug}: {run_bot(slug)}" for slug in BOTS if slug in enabled]
