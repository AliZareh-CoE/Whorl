/** #431: "call Sam at 3pm" → a due time on a Today item. Parsed in the browser on purpose:
 *  the time is the owner's local time, whatever zone the server keeps. */

const TIME = /(?:^|\s)(?:at|by|@)\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)?(?=[\s,.!?]|$)/i;
const WORD = /(?:^|\s)(?:at|by)\s+(noon|midnight)(?=[\s,.!?]|$)/i;
const TOMORROW = /(?:^|\s)tomorrow(?=[\s,.!?]|$)/i;
// #546: a day without a time — "on Friday", "by Monday", "next Tuesday", a weekday closing the
// sentence ("ping Sam Friday"), "next week", "in 3 days". A weekday in the middle of a sentence
// with no lead word ("Monday meeting notes") is text, as on the server (notes/when.py).
const WD = "(mon|tue|wed|thu|fri|sat|sun)(?:day|sday|nesday|rsday|urday)?";
const WEEKDAY = new RegExp(`(?:^|\\s)(on|by|next|this)\\s+${WD}(?=[\\s,.!?]|$)`, "i");
const WEEKDAY_END = new RegExp(`(?:^|\\s)(next\\s+)?${WD}[.!?]?\\s*$`, "i");
const NEXT_WEEK = /(?:^|\s)next week(?=[\s,.!?]|$)/i;
const IN_DAYS = /(?:^|\s)in (\d{1,2}|a|one|two|three|four|five|six|seven) days?(?=[\s,.!?]|$)/i;
const WORDS: Record<string, number> = { a: 1, one: 1, two: 2, three: 3, four: 4, five: 5, six: 6, seven: 7 };
const DAYS = ["sun", "mon", "tue", "wed", "thu", "fri", "sat"];

export type Repeat = "" | "daily" | "weekdays" | "weekly" | "monthly";
export type Parsed = { text: string; due_at: string | null; all_day: boolean; repeat: Repeat };

// #547: "every Monday", "every day" / "daily", "every weekday", "every week" / "weekly",
// "every month" / "monthly". Matched BEFORE the day phrases so "every Monday" is a rule, not a date.
const EVERY = new RegExp(`(?:^|\\s)(?:every\\s+(day|weekday|week|month|${WD})|(daily|weekly|monthly))(?=[\\s,.!?]|$)`, "i");

const tidy = (s: string) => s.replace(/\s+/g, " ").trim();
const cut = (text: string, m: RegExpExecArray) => text.slice(0, m.index) + " " + text.slice(m.index + m[0].length);

/** The day phrase in `text`, as days from `now`, with the phrase removed; null when none. */
function parseDay(text: string, now: Date): { days: number; text: string } | null {
  let m = TOMORROW.exec(text);
  if (m) return { days: 1, text: cut(text, m) };
  m = NEXT_WEEK.exec(text);
  if (m) return { days: 7, text: cut(text, m) };
  m = IN_DAYS.exec(text);
  if (m) return { days: WORDS[m[1].toLowerCase()] ?? Number(m[1]), text: cut(text, m) };
  m = WEEKDAY.exec(text);
  const following = m ? m[1].toLowerCase() === "next" : false;
  let name = m ? m[2] : "";
  if (!m) {
    m = WEEKDAY_END.exec(text);
    if (!m) return null;
    name = m[2];
  }
  const target = DAYS.indexOf(name.slice(0, 3).toLowerCase());
  let days = (target - now.getDay() + 7) % 7 || 7;
  const nextWord = following || (m[1] ?? "").toLowerCase().startsWith("next");
  if (nextWord && days <= 6 - ((now.getDay() + 6) % 7)) days += 7; // "next Friday" said on a Monday
  return { days, text: cut(text, m) };
}

/** Returns the text without the time/day phrases, the ISO due time and whether it is an all-day
 *  item (a day without a clock time, anchored at local noon). `due_at: null` when the text carries
 *  neither. "at 3" alone is left alone (3 what?); am/pm or a colon is required. */
export function parseDue(raw: string, now: Date = new Date()): Parsed {
  let text = raw;
  let hour: number | null = null;
  let minute = 0;
  let repeat: Repeat = "";
  let everyDay: string | null = null; // "every Monday" also sets the first day
  const ev = EVERY.exec(text);
  if (ev) {
    const word = (ev[1] ?? ev[3]).toLowerCase(); // group 2 is the weekday stem inside WD
    if (word === "day" || word === "daily") repeat = "daily";
    else if (word === "weekday") repeat = "weekdays";
    else if (word === "week" || word === "weekly") repeat = "weekly";
    else if (word === "month" || word === "monthly") repeat = "monthly";
    else { repeat = "weekly"; everyDay = word; }
    text = cut(text, ev);
  }
  const word = WORD.exec(text);
  if (word) {
    hour = word[1].toLowerCase() === "noon" ? 12 : 0;
    text = cut(text, word);
  } else {
    const m = TIME.exec(text);
    if (m) {
      const ap = m[3]?.toLowerCase().replace(/\./g, "");
      if (ap || m[2]) {
        hour = Number(m[1]);
        minute = m[2] ? Number(m[2]) : 0;
        if (ap === "pm" && hour < 12) hour += 12;
        if (ap === "am" && hour === 12) hour = 0;
        if (hour > 23 || minute > 59) hour = null;
        else text = cut(text, m);
      }
    }
  }
  let day = parseDay(text, now);
  if (day) text = day.text;
  else if (everyDay) {
    const target = DAYS.indexOf(everyDay.slice(0, 3).toLowerCase());
    day = { days: (target - now.getDay() + 7) % 7 || 7, text }; // the coming one, a week off when today
  }
  if (hour === null && !day) {
    if (!repeat) return { text: tidy(raw), due_at: null, all_day: false, repeat: "" };
    if (repeat === "weekly" || repeat === "monthly") { // a rule needs a day to count from: today
      const anchor = new Date(now); anchor.setHours(12, 0, 0, 0);
      return { text: tidy(text) || tidy(raw), due_at: anchor.toISOString(), all_day: true, repeat };
    }
    return { text: tidy(text) || tidy(raw), due_at: null, all_day: false, repeat };
  }
  const due = new Date(now);
  if (hour === null) {
    due.setDate(due.getDate() + (day as { days: number }).days);
    due.setHours(12, 0, 0, 0); // noon: the same calendar date in every zone within ±12 h
    return { text: tidy(text) || tidy(raw), due_at: due.toISOString(), all_day: true, repeat };
  }
  due.setHours(hour, minute, 0, 0);
  if (day) {
    due.setDate(due.getDate() + day.days);
  } else if (due.getTime() < now.getTime() - 3_600_000) {
    due.setDate(due.getDate() + 1); // that time is already an hour gone — they mean tomorrow
  }
  return { text: tidy(text) || tidy(raw), due_at: due.toISOString(), all_day: false, repeat };
}

/** #547: the rule as a person says it — "every Monday", "every weekday", "monthly on the 3rd". */
export function repeatLabel(repeat: Repeat, iso: string | null, now: Date = new Date()): string {
  if (!repeat) return "";
  const d = iso ? new Date(iso) : now;
  if (repeat === "weekly") return `every ${d.toLocaleDateString(undefined, { weekday: "long" })}`;
  if (repeat === "monthly") { const n = d.getDate(); const suf = n % 100 >= 11 && n % 100 <= 13 ? "th" : ({ 1: "st", 2: "nd", 3: "rd" } as Record<number, string>)[n % 10] ?? "th"; return `monthly on the ${n}${suf}`; }
  return repeat === "daily" ? "every day" : "every weekday";
}

/** "tomorrow" / "Friday" / "Fri 25 Sep" for a day; a clock time appended unless `allDay`. */
export function formatDue(iso: string, allDay = false, now: Date = new Date()): string {
  const d = new Date(iso);
  const time = d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
  if (d.toDateString() === now.toDateString()) return allDay ? "today" : time;
  const label = dayLabel(iso, now);
  return allDay ? label : `${label} ${time}`;
}

/** The day a due time falls on, as a person says it: "tomorrow", a weekday within the week,
 *  "Fri 25 Sep" further out, "yesterday" / "Tue 9 Sep" for days gone. */
export function dayLabel(iso: string, now: Date = new Date()): string {
  const d = new Date(iso);
  const start = new Date(now);
  start.setHours(0, 0, 0, 0);
  const days = Math.round((new Date(d).setHours(0, 0, 0, 0) - start.getTime()) / 86_400_000);
  if (days === 0) return "today";
  if (days === 1) return "tomorrow";
  if (days === -1) return "yesterday";
  if (days > 1 && days < 7) return d.toLocaleDateString(undefined, { weekday: "long" });
  return d.toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" });
}

/** #546: an item is on today's list unless its day is still ahead (local midnight boundary). */
export function isLater(iso: string | null, now: Date = new Date()): boolean {
  if (!iso) return false;
  const end = new Date(now);
  end.setHours(24, 0, 0, 0);
  return new Date(iso).getTime() >= end.getTime();
}

export type DueState = "overdue" | "soon" | "later";

/** overdue: past; soon: within two hours; later: further out. */
export function dueState(iso: string, now: number = Date.now()): DueState {
  const delta = new Date(iso).getTime() - now;
  return delta < 0 ? "overdue" : delta <= 2 * 3_600_000 ? "soon" : "later";
}

export function relativeDue(iso: string, now: number = Date.now()): string {
  const mins = Math.round((new Date(iso).getTime() - now) / 60_000);
  if (mins <= -60) return `${Math.round(-mins / 60)} h overdue`;
  if (mins < 0) return `${-mins} min overdue`;
  if (mins < 1) return "now";
  if (mins < 60) return `in ${mins} min`;
  return `in ${Math.round(mins / 60)} h`;
}

/** The one item worth a nudge: the earliest open due time within the next two hours, or
 *  overdue by less than twelve hours (older ones are yesterday's business, shown on the page). */
export function nextDue<T extends { due_at: string | null; done: boolean; all_day?: boolean }>(items: T[], now: number = Date.now()): T | null {
  const ahead = 2 * 3_600_000;
  const grace = 12 * 3_600_000;
  const due = items
    .filter((t) => !t.done && t.due_at && !t.all_day) // an all-day item has no moment to nudge for
    .map((t) => ({ t, at: new Date(t.due_at as string).getTime() }))
    .filter(({ at }) => at - now <= ahead && now - at <= grace)
    .sort((a, b) => a.at - b.at);
  return due[0]?.t ?? null;
}
