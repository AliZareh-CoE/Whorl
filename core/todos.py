"""#546: the Today list has a Later. An open item belongs to today unless its day is still
ahead — then it waits, out of sight, until that day. One boundary shared by the page, the
dashboard, the brief and the API so "on today's list" means the same thing everywhere.

Day-only items ("review the draft on Friday") carry `all_day=True` and `due_at` at local noon
of that day: noon keeps the same calendar date in every zone within twelve hours of UTC, so
the server's UTC boundary and the browser's local one agree."""

import calendar
from datetime import date, datetime, time, timedelta

from django.db.models import Max, Q, QuerySet
from django.utils import timezone

from core.models import TodoItem

NOON = time(12, 0)
REPEATS = ("daily", "weekdays", "weekly", "monthly")
TRASH_DAYS = 30  # #570: how long a deleted item waits in the Trash before the sweep removes it


def day_end(today: date | None = None) -> datetime:
    """The first instant of tomorrow in the server's zone — everything due before it is today's."""
    today = today or timezone.localdate()
    return timezone.make_aware(datetime.combine(today + timedelta(days=1), time.min))


def day_start(today: date | None = None) -> datetime:
    """The first instant of today in the server's zone."""
    today = today or timezone.localdate()
    return timezone.make_aware(datetime.combine(today, time.min))


def done_today_q(today: date | None = None) -> Q:
    """Ticked today — the rows the Done section shows (#550)."""
    return Q(done=True, done_at__gte=day_start(today), done_at__lt=day_end(today))


def logbook_q(today: date | None = None) -> Q:
    """Ticked on an earlier day, or done without a stamp (a row re-created by an undo) — the
    Logbook (#550). What `clear-done` with scope "earlier" removes."""
    return Q(done=True) & (Q(done_at__lt=day_start(today)) | Q(done_at__isnull=True))


def today_q(today: date | None = None) -> Q:
    """Open items that belong on today's list: undated, due today, or overdue from earlier days."""
    return Q(done=False) & (Q(due_at__isnull=True) | Q(due_at__lt=day_end(today)))


def later_q(today: date | None = None) -> Q:
    """Open items whose day is still ahead."""
    return Q(done=False, due_at__gte=day_end(today))


def open_today(queryset: QuerySet | None = None, today: date | None = None) -> QuerySet:
    qs = TodoItem.objects.all() if queryset is None else queryset
    return qs.filter(today_q(today)).order_by("position", "id")


def open_later(queryset: QuerySet | None = None, today: date | None = None) -> QuerySet:
    qs = TodoItem.objects.all() if queryset is None else queryset
    return qs.filter(later_q(today)).order_by("due_at", "position", "id")


def day_instant(day: date, tz=None) -> datetime:
    """Local noon of `day` in `tz` (the server's zone when None) — an all-day item's due_at."""
    zone = tz or timezone.get_current_timezone()
    return datetime.combine(day, NOON, tzinfo=zone)


def due_day(until: str | date | None, today: date | None = None) -> date | None:
    """The snooze vocabulary ("tomorrow", "monday", "next-week", "weekend", YYYY-MM-DD) as a
    day after today; "" or None means no day. Raises ValueError otherwise."""
    from notes.capture import snooze_date

    return snooze_date(until, today)


def snooze(item: TodoItem, until: str | date | None, today: date | None = None) -> TodoItem:
    """Push the item to a later day: a timed item keeps its clock time on the new day, a plain
    or all-day one becomes an all-day item. "" brings it back to today: an all-day item loses
    its day, a timed one keeps its time on today's date. Returns the saved item."""
    today = today or timezone.localdate()
    day = due_day(until, today)
    if day is None:
        if item.all_day or item.due_at is None:
            item.due_at, item.all_day = None, False
        else:
            local = timezone.localtime(item.due_at)
            item.due_at = local.replace(year=today.year, month=today.month, day=today.day)
    elif item.due_at is not None and not item.all_day:
        local = timezone.localtime(item.due_at)
        item.due_at = local.replace(year=day.year, month=day.month, day=day.day)
    else:
        item.due_at, item.all_day = day_instant(day), True
    item.save(update_fields=["due_at", "all_day", "updated_at"])
    return item


# ---- #547: repeating items ---------------------------------------------------------------


def _add_months(day: date, months: int) -> date:
    """The same day-of-month `months` on, clamped to the month's length (31 Jan → 28 Feb)."""
    month0 = day.month - 1 + months
    year = day.year + month0 // 12
    month = month0 % 12 + 1
    return date(year, month, min(day.day, calendar.monthrange(year, month)[1]))


def advance(day: date, repeat: str) -> date:
    """The next occurrence's day after `day` for a repeat rule."""
    if repeat == "daily":
        return day + timedelta(days=1)
    if repeat == "weekdays":
        step = {4: 3, 5: 2}.get(day.weekday(), 1)  # Fri → Mon, Sat → Mon
        return day + timedelta(days=step)
    if repeat == "weekly":
        return day + timedelta(days=7)
    if repeat == "monthly":
        return _add_months(day, 1)
    raise ValueError(f"unknown repeat rule {repeat!r}")


def next_due(item: TodoItem, today: date | None = None) -> datetime:
    """When the occurrence after `item` is due: advanced from the item's own day (today when it
    has none) and kept advancing until it lies after today, so a chain three weeks behind
    spawns one successor ahead, not three stale ones. A timed item keeps its clock time
    (stored in UTC — a DST change shifts the local hour by one; the server has no zone to
    correct with), an all-day one stays at noon."""
    today = today or timezone.localdate()
    if item.due_at is None or item.all_day:
        day = timezone.localtime(item.due_at).date() if item.due_at else today
        day = advance(day, item.repeat)
        while day <= today:
            day = advance(day, item.repeat)
        return day_instant(day)
    local = timezone.localtime(item.due_at)
    day = advance(local.date(), item.repeat)
    while day <= today:
        day = advance(day, item.repeat)
    return local.replace(year=day.year, month=day.month, day=day.day)


def spawn_next(item: TodoItem, today: date | None = None) -> TodoItem | None:
    """Create the next occurrence of a ticked repeating item — once: an open successor that
    already exists is returned instead. The new row goes to the bottom of the list and lands
    in Today or Later by the usual boundary."""
    if not item.repeat:
        return None
    # #570: the chain's open successor may sit in the Trash — a re-tick brings it back rather
    # than spawning a second occurrence (one open occurrence per chain, trashed or live)
    existing = TodoItem.all_objects.filter(repeat_of=item, done=False).first()
    if existing is not None:
        if existing.deleted_at is not None:
            restore(existing)
        return existing
    top = TodoItem.objects.aggregate(m=Max("position"))["m"] or 0
    return TodoItem.objects.create(
        text=item.text,
        project=item.project,
        position=top + 1,
        due_at=next_due(item, today),
        all_day=item.due_at is None or item.all_day,
        repeat=item.repeat,
        repeat_of=item,
    )


def unspawn(item: TodoItem) -> int:
    """An untick takes the successor back while it is still untouched (open, same text).
    An edited or ticked successor is the owner's now and stays."""
    deleted, _ = TodoItem.all_objects.filter(repeat_of=item, done=False, text=item.text).delete()
    return deleted


def trash(item: TodoItem) -> TodoItem:
    """#570: into the Trash — out of every list and count, back with `restore` for TRASH_DAYS.
    A done row keeps its stamp, a successor its chain; save() so the ETag moves."""
    item.deleted_at = timezone.now()
    item.save(update_fields=["deleted_at", "updated_at"])
    return item


def restore(item: TodoItem) -> TodoItem:
    """Back from the Trash exactly as it was — its day, its rule, its stamp, its place."""
    item.deleted_at = None
    item.save(update_fields=["deleted_at", "updated_at"])
    return item


def prune_trash(now: datetime | None = None) -> int:
    """Remove what has waited in the Trash longer than TRASH_DAYS — the nightly sweep (huey)
    and the desktop scheduler both call this. A pruned parent detaches its successors
    (SET_NULL), the same as clearing done rows always did."""
    cutoff = (now or timezone.now()) - timedelta(days=TRASH_DAYS)
    deleted, _ = TodoItem.all_objects.filter(deleted_at__lt=cutoff).delete()
    return deleted


def repeat_label(item: TodoItem) -> str:
    """ "every Monday" / "every weekday" / "every day" / "monthly on the 3rd" — for rows and Claude."""
    if not item.repeat:
        return ""
    if item.repeat == "weekly":
        day = timezone.localtime(item.due_at) if item.due_at else timezone.localtime()
        return f"every {day.strftime('%A')}"
    if item.repeat == "monthly":
        day = timezone.localtime(item.due_at).day if item.due_at else timezone.localdate().day
        return f"monthly on the {day}{_ordinal(day)}"
    return {"daily": "every day", "weekdays": "every weekday"}[item.repeat]


def _ordinal(n: int) -> str:
    if 11 <= n % 100 <= 13:
        return "th"
    return {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
