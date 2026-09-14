"""#500: dates and times written into a capture.

"todo: send the IRB form by Friday 3pm" should land on Today due Friday at three; "milestone:
freeze the design by Oct 1" should carry that due date. `parse_when` reads the first line for
one date phrase and one time phrase, returns them, and hands back the text without them.

Dates: today · tomorrow · day after tomorrow · a weekday (next occurrence; "next Friday" is
next week's when this week's is still ahead) · next week / next month · end of (the) week /
month · in N days|weeks|months · "Oct 1", "October 1st", "1 Oct 2027" · YYYY-MM-DD.
Weekdays and month dates need a lead-in (on / by / before / until / due) or must end the line,
so "the Friday talk" is left alone. Times: at|by|@ 3pm · 3:30 pm · 15:30 · noon · midnight
("at 3" alone is left alone — three what?). The time is the owner's wall clock; callers turn
it into an instant with the caller's zone (see notes.capture.convert).
"""

from __future__ import annotations

import calendar
import re
from datetime import date, time, timedelta

WEEKDAYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")
MONTHS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
NUMBER_WORDS = {
    "a": 1, "an": 1, "one": 1, "two": 2, "three": 3, "four": 4, "five": 5, "six": 6,
    "seven": 7, "eight": 8, "nine": 9, "ten": 10,
}  # fmt: skip
LEAD = r"(?:(?:on|by|before|until|till|due)\s+)"
END = r"(?=[\s,.!?;:)]|$)"
WD = r"(?:mon|tue|wed|thu|fri|sat|sun)[a-z]*"
MO = r"(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?"

TIME_RE = re.compile(
    r"(?:^|\s)(?:(?:at|by|@)\s*)?(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)" + END,
    re.IGNORECASE,
)
CLOCK_RE = re.compile(r"(?:^|\s)(?:(?:at|by|@)\s*)?([01]?\d|2[0-3]):([0-5]\d)" + END)
NOON_RE = re.compile(r"(?:^|\s)(?:(?:at|by)\s+)?(noon|midnight)" + END, re.IGNORECASE)
RELATIVE_RE = re.compile(
    r"(?:^|\s)" + LEAD + r"?(day after tomorrow|tomorrow|today|next week|next month|"
    r"end of (?:the )?(?:week|month)|in (\d+|a|an|one|two|three|four|five|six|seven|eight|nine|ten)"
    r" (days?|weeks?|months?))" + END,
    re.IGNORECASE,
)
WEEKDAY_RE = re.compile(r"(?:^|\s)" + LEAD + r"(next\s+)?(" + WD + r")" + END, re.IGNORECASE)
WEEKDAY_END_RE = re.compile(r"(?:^|\s)(next\s+)?(" + WD + r")[.!?]?\s*$", re.IGNORECASE)
MONTH_DAY_RE = re.compile(
    r"(?:^|\s)" + LEAD + r"?(" + MO + r")\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(\d{4}))?" + END,
    re.IGNORECASE,
)
DAY_MONTH_RE = re.compile(
    r"(?:^|\s)" + LEAD + r"?(\d{1,2})(?:st|nd|rd|th)?\s+(" + MO + r")(?:,?\s+(\d{4}))?" + END,
    re.IGNORECASE,
)
ISO_RE = re.compile(r"(?:^|\s)" + LEAD + r"?(\d{4})-(\d{2})-(\d{2})" + END)


def _cut(text: str, start: int, end: int) -> str:
    return (text[:start] + " " + text[end:]).strip()


def _tidy(text: str) -> str:
    text = re.sub(r"\s+", " ", text).strip()
    return re.sub(r"\s*[,;:\-–—]+\s*$", "", text).strip()


def _weekday(name: str) -> int:
    return WEEKDAYS.index(name[:3].lower())


def _month(name: str) -> int:
    return MONTHS.index(name[:3].lower()) + 1


def _safe_date(year: int, month: int, day: int) -> date | None:
    try:
        return date(year, month, day)
    except ValueError:
        return None


def _next_weekday(today: date, weekday: int, following: bool) -> date:
    ahead = (weekday - today.weekday()) % 7 or 7
    day = today + timedelta(days=ahead)
    if following and ahead <= 6 - today.weekday():
        day += timedelta(days=7)  # "next Friday" said on a Monday: the one after this week's
    return day


def _month_date(today: date, month: int, day: int, year: str | None) -> date | None:
    if year:
        return _safe_date(int(year), month, day)
    found = _safe_date(today.year, month, day)
    if found is None:
        return None
    return found if found >= today else _safe_date(today.year + 1, month, day)


def parse_time(text: str) -> tuple[time | None, str]:
    """(time, text without the phrase)."""
    m = NOON_RE.search(text)
    if m:
        return time(12 if m.group(1).lower() == "noon" else 0, 0), _cut(text, m.start(), m.end())
    m = TIME_RE.search(text)
    if m:
        hour, minute = int(m.group(1)), int(m.group(2) or 0)
        ap = m.group(3).lower().replace(".", "")
        if hour <= 12 and minute <= 59:
            if ap == "pm" and hour < 12:
                hour += 12
            if ap == "am" and hour == 12:
                hour = 0
            return time(hour, minute), _cut(text, m.start(), m.end())
    m = CLOCK_RE.search(text)
    if m:
        return time(int(m.group(1)), int(m.group(2))), _cut(text, m.start(), m.end())
    return None, text


def parse_date(text: str, today: date) -> tuple[date | None, str]:
    """(date, text without the phrase)."""
    m = RELATIVE_RE.search(text)
    if m:
        phrase = m.group(1).lower()
        if phrase == "today":
            day = today
        elif phrase == "tomorrow":
            day = today + timedelta(days=1)
        elif phrase == "day after tomorrow":
            day = today + timedelta(days=2)
        elif phrase == "next week":
            day = today + timedelta(days=7)
        elif phrase == "next month":
            year, month = (
                (today.year + 1, 1) if today.month == 12 else (today.year, today.month + 1)
            )
            day = date(year, month, 1)
        elif phrase.startswith("end of") and phrase.endswith("week"):
            day = (
                today + timedelta(days=(4 - today.weekday()) % 7 or 7)
                if today.weekday() > 4
                else today + timedelta(days=4 - today.weekday())
            )
        elif phrase.startswith("end of"):
            day = date(today.year, today.month, calendar.monthrange(today.year, today.month)[1])
        else:
            raw, unit = m.group(2).lower(), m.group(3).lower()
            n = NUMBER_WORDS.get(raw, None)
            n = int(raw) if n is None else n
            n = max(1, min(n, 365))
            if unit.startswith("day"):
                day = today + timedelta(days=n)
            elif unit.startswith("week"):
                day = today + timedelta(weeks=n)
            else:
                month0 = today.month - 1 + n
                year, month = today.year + month0 // 12, month0 % 12 + 1
                day = date(year, month, min(today.day, calendar.monthrange(year, month)[1]))
        return day, _cut(text, m.start(), m.end())
    m = ISO_RE.search(text)
    if m:
        day = _safe_date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
        if day:
            return day, _cut(text, m.start(), m.end())
    m = MONTH_DAY_RE.search(text)
    if m:
        day = _month_date(today, _month(m.group(1)), int(m.group(2)), m.group(3))
        if day:
            return day, _cut(text, m.start(), m.end())
    m = DAY_MONTH_RE.search(text)
    if m:
        day = _month_date(today, _month(m.group(2)), int(m.group(1)), m.group(3))
        if day:
            return day, _cut(text, m.start(), m.end())
    m = WEEKDAY_RE.search(text) or WEEKDAY_END_RE.search(text)
    if m:
        day = _next_weekday(today, _weekday(m.group(2)), bool(m.group(1)))
        return day, _cut(text, m.start(), m.end())
    return None, text


def parse_when(text: str, today: date) -> dict:
    """{date, time, text} — date/time as objects or None; text is the first line without the
    phrases (the rest of the capture is untouched, callers join it back if they need it)."""
    raw = (text or "").strip()
    first, sep, rest = raw.partition("\n")
    when_time, first = parse_time(first)
    when_date, first = parse_date(first, today)
    cleaned = _tidy(first) + (sep + rest if sep else "")
    return {"date": when_date, "time": when_time, "text": cleaned}
