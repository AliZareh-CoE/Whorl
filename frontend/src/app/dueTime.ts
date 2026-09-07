/** #431: "call Sam at 3pm" → a due time on a Today item. Parsed in the browser on purpose:
 *  the time is the owner's local time, whatever zone the server keeps. */

const TIME = /(?:^|\s)(?:at|by|@)\s*(\d{1,2})(?::(\d{2}))?\s*(am|pm|a\.m\.|p\.m\.)?(?=[\s,.!?]|$)/i;
const WORD = /(?:^|\s)(?:at|by)\s+(noon|midnight)(?=[\s,.!?]|$)/i;
const TOMORROW = /(?:^|\s)tomorrow(?=[\s,.!?]|$)/i;

export type Parsed = { text: string; due_at: string | null };

const tidy = (s: string) => s.replace(/\s+/g, " ").trim();

/** Returns the text without the time phrase and the ISO due time, or `due_at: null` when the
 *  text carries no time. "at 3" alone is left alone (3 what?); am/pm or a colon is required. */
export function parseDue(raw: string, now: Date = new Date()): Parsed {
  let text = raw;
  let hour: number | null = null;
  let minute = 0;
  const word = WORD.exec(text);
  if (word) {
    hour = word[1].toLowerCase() === "noon" ? 12 : 0;
    text = text.slice(0, word.index) + " " + text.slice(word.index + word[0].length);
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
        else text = text.slice(0, m.index) + " " + text.slice(m.index + m[0].length);
      }
    }
  }
  if (hour === null) return { text: tidy(raw), due_at: null };
  const due = new Date(now);
  due.setHours(hour, minute, 0, 0);
  const tomorrow = TOMORROW.exec(text);
  if (tomorrow) {
    due.setDate(due.getDate() + 1);
    text = text.slice(0, tomorrow.index) + " " + text.slice(tomorrow.index + tomorrow[0].length);
  } else if (due.getTime() < now.getTime() - 3_600_000) {
    due.setDate(due.getDate() + 1); // that time is already an hour gone — they mean tomorrow
  }
  return { text: tidy(text) || tidy(raw), due_at: due.toISOString() };
}

export function formatDue(iso: string, now: Date = new Date()): string {
  const d = new Date(iso);
  const time = d.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" });
  if (d.toDateString() === now.toDateString()) return time;
  const tomorrow = new Date(now);
  tomorrow.setDate(now.getDate() + 1);
  if (d.toDateString() === tomorrow.toDateString()) return `tomorrow ${time}`;
  return `${d.toLocaleDateString(undefined, { weekday: "short" })} ${time}`;
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
export function nextDue<T extends { due_at: string | null; done: boolean }>(items: T[], now: number = Date.now()): T | null {
  const ahead = 2 * 3_600_000;
  const grace = 12 * 3_600_000;
  const due = items
    .filter((t) => !t.done && t.due_at)
    .map((t) => ({ t, at: new Date(t.due_at as string).getTime() }))
    .filter(({ at }) => at - now <= ahead && now - at <= grace)
    .sort((a, b) => a.at - b.at);
  return due[0]?.t ?? null;
}
