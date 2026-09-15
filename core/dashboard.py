"""Cross-project dashboard: what should I work on today, everywhere?"""

import datetime

from django.db.models import Count, F, Q
from django.utils import timezone

from documents.models import Document
from literature.models import ProjectReference, Reference
from notes.capture import open_captures
from notes.models import Note, QuickCapture
from plans.models import Milestone
from plans.selectors import current_phase, project_progress
from projects.models import DecisionRecord, Project
from research.models import Dataset, Evidence, ExperimentEntry, Hypothesis
from writing.models import Manuscript, SubmissionEvent

HEATMAP_WEEKS = 26

ACTIVITY_MODELS = [
    Project,
    DecisionRecord,
    Document,
    Note,
    QuickCapture,
    Reference,
    ProjectReference,
    Milestone,
    Manuscript,
    SubmissionEvent,
    Hypothesis,
    Evidence,
    ExperimentEntry,
    Dataset,
]


def active_projects():
    projects = Project.objects.filter(
        status__in=[Project.Status.PLANNING, Project.Status.ACTIVE]
    ).prefetch_related("phases")
    rows = []
    for project in projects:
        done, total, percent = project_progress(project)
        rows.append(
            {
                "project": project,
                "phase": current_phase(project),
                "done": done,
                "total": total,
                "percent": percent,
                # grove tree size scales with scope: 64px floor, +5px per milestone, 112px cap
                "tree_size": min(112, 64 + 5 * total),
            }
        )
    return rows


PRIORITY_RANK = {"high": 0, "normal": 1, "low": 2}


def reading_queue_everywhere(today=None, limit: int = 5) -> dict:
    """#486: the head of the reading queue across every planning/active project — highest
    priority first, then the paper that has waited longest — plus how much is unread and how
    much of that is high priority. The dashboard's answer to "what should I read today?"."""
    from literature.models import ProjectReference

    today = today or timezone.localdate()
    links = list(
        ProjectReference.objects.filter(
            reading_status="to_read",
            project__status__in=[Project.Status.PLANNING, Project.Status.ACTIVE],
        )
        .select_related("reference", "project")
        .order_by("created_at")
    )
    queue = sorted(links, key=lambda link: (PRIORITY_RANK.get(link.priority, 1), link.created_at))
    return {
        "to_read": len(links),
        "high_priority": sum(1 for link in links if link.priority == "high"),
        "projects": len({link.project_id for link in links}),
        "next": [
            {
                "id": link.reference_id,
                "title": link.reference.title,
                "first_author": (
                    (link.reference.authors[0].get("family") if link.reference.authors else "")
                    or ""
                ),
                "year": link.reference.year,
                "priority": link.priority,
                "project": link.project.name,
                "project_slug": link.project.slug,
                "waiting_days": (today - timezone.localtime(link.created_at).date()).days,
            }
            for link in queue[:limit]
        ],
    }


WATCH_ROWS = 3


def watches_everywhere(limit: int = WATCH_ROWS) -> dict:
    """#533: the Library's watches at a glance — what the followed feeds announced and which new
    papers cite the library's papers — from the stored rows (the sweeps fill them; nothing is
    fetched here). `feeds.rows` are the newest open entries (the same paper in two feeds once),
    `citations.rows` the newest open citing works with the library papers they cite. `url`s are
    the Library modes' addresses (#532)."""
    from literature.citing import open_alerts
    from literature.feeds import open_items
    from literature.models import Feed

    feed_totals = Feed.objects.aggregate(
        followed=Count("pk"), errors=Count("pk", filter=~Q(last_error=""))
    )
    limit = max(1, min(int(limit or WATCH_ROWS), 20))
    seen: set[str] = set()
    feed_rows = []
    for item in (
        open_items()
        .select_related("feed")
        .order_by(F("published_on").desc(nulls_last=True), "pk")[: limit + 20]
    ):
        key = (
            f"doi:{item.doi.lower()}"
            if item.doi
            else f"arxiv:{item.arxiv_id}"
            if item.arxiv_id
            else f"item:{item.pk}"
        )
        if key in seen:
            continue
        seen.add(key)
        feed_rows.append(
            {
                "id": item.pk,
                "title": item.title,
                "feed": item.feed.title or item.feed.url,
                "feed_id": item.feed_id,
                "published_on": item.published_on.isoformat() if item.published_on else None,
                "link": item.link
                or (f"https://doi.org/{item.doi}" if item.doi else "")
                or (f"https://arxiv.org/abs/{item.arxiv_id}" if item.arxiv_id else ""),
            }
        )
        if len(feed_rows) >= limit:
            break
    citing_rows = [
        {
            "id": work.pk,
            "title": work.title,
            "first_author": (work.authors[0] if work.authors else "") or "",
            "year": work.year,
            "published_on": work.published_on.isoformat() if work.published_on else None,
            "venue": work.venue,
            "cites": [{"id": r.pk, "bibtex_key": r.bibtex_key} for r in work.cites.all()],
        }
        for work in open_alerts()
        .order_by(F("published_on").desc(nulls_last=True), "-created_at")
        .prefetch_related("cites")[:limit]
    ]
    return {
        "feeds": {
            "new": open_items().count(),
            "followed": feed_totals["followed"],
            "errors": feed_totals["errors"],
            "rows": feed_rows,
            "url": "/library?feeds=1",
        },
        "citations": {
            "new": open_alerts().count(),
            "rows": citing_rows,
            "url": "/library?citing=1",
        },
    }


PULSE_WEEKS = 12
QUIET_WEEKS = 3  # #489: an active project silent this long is worth a row in needs-attention


def pulses_everywhere(projects, today=None, weeks: int = PULSE_WEEKS) -> dict[int, dict]:
    """#489: the twelve-week pulse (#483) for many projects at once — one grouped query per
    event source instead of a timeline pass per project, so the dashboard's cost does not
    grow with the number of active projects. Same bins as the overview: Monday-based weeks,
    the current week last. Returns {project_id: {weeks: [counts], total, quiet_weeks,
    last_activity}}."""
    from documents.models import Document
    from literature.models import ProjectReference
    from notes.models import Note
    from plans.models import Milestone
    from projects.models import DecisionRecord
    from research.models import ExperimentEntry, Hypothesis
    from writing.models import Manuscript, SubmissionEvent

    today = today or timezone.localdate()
    ids = [p.pk for p in projects]
    if not ids:
        return {}
    this_monday = today - datetime.timedelta(days=today.weekday())
    first = this_monday - datetime.timedelta(weeks=weeks - 1)
    bins = {pid: [0] * weeks for pid in ids}
    last: dict[int, datetime.date] = {}

    def hit(pid: int, day):
        if day is None:
            return
        if hasattr(day, "date") and not isinstance(day, datetime.date):
            day = day.date()
        elif isinstance(day, datetime.datetime):
            day = timezone.localtime(day).date()
        if pid not in last or day > last[pid]:
            last[pid] = day
        if first <= day <= today:
            bins[pid][(day - first).days // 7] += 1

    since = timezone.make_aware(datetime.datetime.combine(first, datetime.time.min))
    # (project id, when) per source — filtered to the window where the field allows a range
    for pid, when in Milestone.objects.filter(
        phase__project_id__in=ids, completed_at__isnull=False
    ).values_list("phase__project_id", "completed_at"):
        hit(pid, when)
    for pid, created, updated, status in ProjectReference.objects.filter(
        project_id__in=ids
    ).values_list("project_id", "created_at", "updated_at", "reading_status"):
        hit(pid, created)
        if status in ("read", "annotated") and updated.date() > created.date():
            hit(pid, updated)
    for model, field in (
        (Note, "created_at"),
        (Hypothesis, "created_at"),
        (ExperimentEntry, "date"),
        (DecisionRecord, "decided_on"),
    ):
        for pid, when in model.objects.filter(project_id__in=ids).values_list("project_id", field):
            hit(pid, when)
    for pid, when in (
        Document.objects.general()
        .filter(project_id__in=ids)
        .values_list("project_id", "created_at")
    ):
        hit(pid, when)
    for pid, when in SubmissionEvent.objects.filter(manuscript__project_id__in=ids).values_list(
        "manuscript__project_id", "date"
    ):
        hit(pid, when)
    for pid, when in Manuscript.objects.filter(
        project_id__in=ids, compiled_at__isnull=False
    ).values_list("project_id", "compiled_at"):
        hit(pid, when)
    del since
    out = {}
    for pid in ids:
        counts = bins[pid]
        quiet = 0
        for n in reversed(counts):
            if n:
                break
            quiet += 1
        day = last.get(pid)
        out[pid] = {
            "weeks": counts,
            "total": sum(counts),
            "quiet_weeks": quiet,
            "last_activity": day.isoformat() if day else None,
            "days_since": (today - day).days if day else None,
        }
    return out


def quiet_projects(active_rows, pulses: dict[int, dict]) -> list[dict]:
    """#489: active projects whose pulse has been flat for QUIET_WEEKS or more — the
    needs-attention row that says "this one is drifting" before a deadline does."""
    rows = []
    for row in active_rows:
        project = row["project"]
        pulse = pulses.get(project.pk)
        if not pulse or pulse["quiet_weeks"] < QUIET_WEEKS:
            continue
        rows.append(
            {
                "name": project.name,
                "slug": project.slug,
                "url": f"/projects/{project.slug}",
                "quiet_weeks": pulse["quiet_weeks"],
                "last_activity": pulse["last_activity"],
                "days_since": pulse["days_since"],
            }
        )
    rows.sort(key=lambda r: -r["quiet_weeks"])
    return rows


READINESS_ROWS = 4  # Audit #27: pre-flights per dashboard load, most urgent first


def writing_everywhere(today=None, limit: int = 6) -> dict:
    """#487: every live manuscript (not published, not shelved) across planning/active
    projects, the way the project overview shows them — status clock, nudge, pre-flight
    readiness, deadline — sorted by urgency: the nearest deadline first, then papers whose
    editor deserves a nudge, then the rest by id."""
    from projects.overview import WORKING, manuscripts_glance, readiness_of
    from writing.models import Manuscript

    today = today or timezone.localdate()
    statuses = [Project.Status.PLANNING, Project.Status.ACTIVE]
    rows: list[dict] = []
    for project in Project.objects.filter(status__in=statuses):
        # Audit #27 (#488): no pre-flight yet — sort everything first, then run it only for
        # the rows the dashboard shows, so the cost is bounded by `limit`, not by projects
        for m in manuscripts_glance(project, today=today, limit=limit, readiness=False):
            m["project"] = project.name
            m["project_slug"] = project.slug
            rows.append(m)
    rows.sort(
        key=lambda m: (
            m["days"] if m["days"] is not None else 10**6,
            0 if (m.get("clock") or {}).get("nudge", {}).get("due") else 1,
            m["id"],
        )
    )
    shown = rows[:limit]
    # ... and at most READINESS_ROWS pre-flights per dashboard load (each is ~10 queries /
    # ~20 ms): the most urgent working papers get the verdict, the rest show none
    budget_left = READINESS_ROWS
    for m in shown:
        manuscript = m.pop("_manuscript")
        if manuscript.status in WORKING and budget_left > 0:
            m["readiness"] = readiness_of(manuscript)
            budget_left -= 1
    live = (
        Manuscript.objects.filter(project__status__in=statuses)
        .exclude(status__in=("published", "shelved"))
        .count()
    )
    return {"live": live, "rows": shown}


DAY_PROJECTS = 40  # #492: a day panel reads at most this many projects' timelines


def day_activity(day: datetime.date) -> dict:
    """#492: everything that happened on one day, across every project — the readable
    events of the project timelines (milestones done, papers added or read, notes, decisions,
    lab entries, hypotheses, documents, submission events, compiles), newest project first.
    On demand (a click on the heatmap), so a timeline pass per project is acceptable."""
    from core.timeline import project_timeline

    iso = day.isoformat()
    events: list[dict] = []
    for project in Project.objects.order_by("-updated_at")[:DAY_PROJECTS]:
        for e in project_timeline(project, bodies=False):
            if e["date"] == iso:
                events.append(
                    {
                        "kind": e["kind"],
                        "label": e["label"],
                        "detail": e.get("detail", ""),
                        "url": e["url"],
                        "project": project.name,
                        "project_slug": project.slug,
                    }
                )
    return {"date": iso, "count": len(events), "events": events}


def needs_attention(today=None, window_days=14):
    """The lead of the dashboard ([REV] cycle 145): the ANSWER to "what should I
    work on today?", not just data. Overdue milestones, manuscript deadlines
    inside the window, and untriaged inbox items — each one actionable."""
    today = today or timezone.localdate()
    soon = today + datetime.timedelta(days=window_days)
    overdue = list(
        Milestone.objects.filter(
            completed_at__isnull=True,
            due_date__lt=today,
            phase__project__status__in=["planning", "active"],
        )
        .select_related("phase__project")
        .order_by("due_date")
    )
    deadlines = list(
        Manuscript.objects.filter(deadline__isnull=False, deadline__lte=soon)
        .exclude(status__in=["published", "shelved"])
        .select_related("project")
        .order_by("deadline")
    )
    inbox = list(open_captures().order_by("created_at")[:5])  # #495: snoozed ones sleep
    return {
        "overdue": overdue,
        "deadlines": deadlines,
        "inbox": inbox,
        "empty": not (overdue or deadlines or inbox),
    }


def upcoming_milestones(limit=10):
    return (
        Milestone.objects.filter(completed_at__isnull=True, due_date__isnull=False)
        .filter(phase__project__status__in=["planning", "active"])
        .select_related("phase__project")
        .order_by(F("due_date").asc())[:limit]
    )


def upcoming_deadlines(limit=5):
    return (
        Manuscript.objects.filter(deadline__isnull=False)
        .exclude(status__in=["published", "shelved"])
        .select_related("project")
        .order_by("deadline")[:limit]
    )


def activity_heatmap(today=None):
    """GitHub-style: list of weeks, each a list of 7 {date, count, level} cells.

    Cached for 10 minutes — 28 aggregate queries that change at day granularity.
    """
    from django.core.cache import cache

    today = today or timezone.localdate()
    cache_key = f"activity_heatmap:{today.isoformat()}"
    cached = cache.get(cache_key)
    if cached is not None:
        return cached
    weeks = _build_heatmap(today)
    cache.set(cache_key, weeks, 600)
    return weeks


def _build_heatmap(today):
    start = today - datetime.timedelta(weeks=HEATMAP_WEEKS)
    start -= datetime.timedelta(days=start.weekday())  # align to Monday

    from django.db.models import Count
    from django.db.models.functions import TruncDate

    counts: dict[datetime.date, int] = {}
    for model in ACTIVITY_MODELS:
        for field in ("created_at", "updated_at"):
            rows = (
                model.objects.filter(**{f"{field}__date__gte": start})
                .annotate(_day=TruncDate(field))
                .values("_day")
                .annotate(n=Count("pk"))
            )
            for row in rows:
                counts[row["_day"]] = counts.get(row["_day"], 0) + row["n"]

    weeks = []
    cursor = start
    while cursor <= today:
        week = []
        for _ in range(7):
            count = counts.get(cursor, 0)
            level = (
                0
                if count == 0
                else 1
                if count <= 2
                else 2
                if count <= 6
                else 3
                if count <= 15
                else 4
            )
            week.append({"date": cursor, "count": count, "level": level, "future": cursor > today})
            cursor += datetime.timedelta(days=1)
        weeks.append(week)
    return weeks


def monthly_stats(today=None):
    today = today or timezone.localdate()
    month_start = today.replace(day=1)
    return {
        "papers_read": ProjectReference.objects.filter(
            reading_status__in=["read", "annotated"], updated_at__date__gte=month_start
        ).count(),
        "notes_written": Note.objects.filter(created_at__date__gte=month_start).count(),
        "milestones_done": Milestone.objects.filter(completed_at__date__gte=month_start).count(),
        "experiments_logged": ExperimentEntry.objects.filter(date__gte=month_start).count(),
        "words_written": words_written_since(month_start),
    }


TREND_MONTHS = 6


def _month_starts(today, months: int) -> list[datetime.date]:
    first = today.replace(day=1)
    out = [first]
    for _ in range(months - 1):
        first = (first - datetime.timedelta(days=1)).replace(day=1)
        out.append(first)
    return list(reversed(out))


def stats_trend(today=None, months: int = TREND_MONTHS) -> dict:
    """#490: the monthly stats over the last `months` months (oldest first, the current month
    last), one grouped query per stat, with the same definitions `monthly_stats` uses for
    the current month — so the tile and its trend never disagree. `previous` is last month."""
    from writing.models import WordCountSample

    today = today or timezone.localdate()
    starts = _month_starts(today, months)
    window = starts[0]
    index = {(d.year, d.month): i for i, d in enumerate(starts)}
    series = {
        k: [0] * months
        for k in (
            "papers_read",
            "notes_written",
            "milestones_done",
            "experiments_logged",
            "words_written",
        )
    }

    def hit(key: str, day):
        if isinstance(day, datetime.datetime):
            day = timezone.localtime(day).date()
        i = index.get((day.year, day.month))
        if i is not None:
            series[key][i] += 1

    for when in ProjectReference.objects.filter(
        reading_status__in=["read", "annotated"], updated_at__date__gte=window
    ).values_list("updated_at", flat=True):
        hit("papers_read", when)
    for when in Note.objects.filter(created_at__date__gte=window).values_list(
        "created_at", flat=True
    ):
        hit("notes_written", when)
    for when in Milestone.objects.filter(completed_at__date__gte=window).values_list(
        "completed_at", flat=True
    ):
        hit("milestones_done", when)
    for when in ExperimentEntry.objects.filter(date__gte=window).values_list("date", flat=True):
        hit("experiments_logged", when)
    previous: dict[int, int] = {}
    for manuscript_id, day, words in WordCountSample.objects.order_by(
        "manuscript_id", "date"
    ).values_list("manuscript_id", "date", "words"):
        if manuscript_id in previous:
            i = index.get((day.year, day.month))
            if i is not None:
                series["words_written"][i] += max(0, words - previous[manuscript_id])
        previous[manuscript_id] = words
    return {
        "months": [d.strftime("%Y-%m") for d in starts],
        "series": series,
        "previous": {k: v[-2] if months >= 2 else 0 for k, v in series.items()},
    }


def words_written_since(start) -> int:
    """Words added to manuscripts since ``start`` (#418): the sum of positive day-to-day
    deltas of the daily word samples (#413), across every manuscript."""
    from writing.models import WordCountSample

    total = 0
    previous: dict[int, int] = {}
    for sample in WordCountSample.objects.order_by("manuscript_id", "date").values_list(
        "manuscript_id", "date", "words"
    ):
        manuscript_id, day, words = sample
        if manuscript_id in previous and day >= start:
            total += max(0, words - previous[manuscript_id])
        previous[manuscript_id] = words
    return total


def dashboard_context():
    return {
        "active": active_projects(),
        "attention": needs_attention(),
        "milestones": upcoming_milestones(),
        "deadlines": upcoming_deadlines(),
        "heatmap": activity_heatmap(),
        "stats": monthly_stats(),
        "inbox_count": open_captures().count(),
    }


def week_everywhere(today=None, days=7, limit=40):
    """Dashboard v2: overdue and due-within-a-week milestones/tasks across active projects,
    overdue first, each with its project — the cross-project "this week" list."""
    from plans.models import Task

    today = today or timezone.localdate()
    horizon = today + datetime.timedelta(days=days)
    live = ["planning", "active"]
    items = []
    for m in (
        Milestone.objects.filter(
            completed_at__isnull=True, due_date__lte=horizon, phase__project__status__in=live
        )
        .select_related("phase__project")
        .order_by("due_date")[:limit]
    ):
        items.append(
            {
                "kind": "milestone",
                "id": m.pk,
                "title": m.title,
                "due_date": m.due_date,
                "days": (m.due_date - today).days,
                "project": m.phase.project.slug,
                "project_name": m.phase.project.name,
                "color": m.phase.project.color,
                "phase": m.phase.name,
            }
        )
    for t in (
        Task.objects.filter(
            done=False, due_date__lte=horizon, milestone__phase__project__status__in=live
        )
        .select_related("milestone__phase__project")
        .order_by("due_date")[:limit]
    ):
        project = t.milestone.phase.project
        items.append(
            {
                "kind": "task",
                "id": t.pk,
                "title": t.title,
                "due_date": t.due_date,
                "days": (t.due_date - today).days,
                "project": project.slug,
                "project_name": project.name,
                "color": project.color,
                "phase": t.milestone.phase.name,
            }
        )
    items.sort(key=lambda i: (i["due_date"], i["kind"] != "milestone", i["title"]))
    return {
        "today": today,
        "week_ends": horizon,
        "overdue": [i for i in items if i["days"] < 0],
        "due_this_week": [i for i in items if i["days"] >= 0],
    }


def project_health(rows):
    """Attach the current phase's health (from the roadmap) to each active-project row."""
    from plans.roadmap import project_roadmap

    out = {}
    for row in rows:
        project, phase = row["project"], row["phase"]
        if phase is None:
            continue
        match = next((r for r in project_roadmap(project)["phases"] if r["id"] == phase.pk), None)
        if match:
            out[project.slug] = {
                "state": match["state"],
                "label": match["label"],
                "forecast_end": match["forecast_end"],
            }
    return out
