"""#546: the Today list has a Later. An open item belongs to today unless its day is still
ahead — then it waits, out of sight, until that day. One boundary shared by the page, the
dashboard, the brief and the API so "on today's list" means the same thing everywhere.

Day-only items ("review the draft on Friday") carry `all_day=True` and `due_at` at local noon
of that day: noon keeps the same calendar date in every zone within twelve hours of UTC, so
the server's UTC boundary and the browser's local one agree."""

from datetime import date, datetime, time, timedelta

from django.db.models import Q, QuerySet
from django.utils import timezone

from core.models import TodoItem

NOON = time(12, 0)


def day_end(today: date | None = None) -> datetime:
    """The first instant of tomorrow in the server's zone — everything due before it is today's."""
    today = today or timezone.localdate()
    return timezone.make_aware(datetime.combine(today + timedelta(days=1), time.min))


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
