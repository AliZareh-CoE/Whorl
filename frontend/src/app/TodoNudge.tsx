/** #431: a gentle sidebar nudge — the one Today item whose time is within two hours (or just
 *  passed). Shares the ["todos"] query with the Today page; re-reads once a minute. */
import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { AlarmClock } from "lucide-react";
import { NavLink } from "react-router-dom";
import { api } from "./api";
import { dueState, nextDue, relativeDue } from "./dueTime";

type Todo = { id: number; text: string; done: boolean; due_at: string | null; all_day: boolean };

export function TodoNudge() {
  const { data } = useQuery({
    queryKey: ["todos"],
    queryFn: () => api<{ results: Todo[] }>("/todos/?page_size=200"),
    refetchInterval: 60_000,
  });
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 30_000);
    return () => window.clearInterval(id);
  }, []);
  const next = data ? nextDue(data.results, now) : null;
  if (!next || !next.due_at) return null;
  const state = dueState(next.due_at, now);
  return (
    <NavLink
      to="/today"
      data-testid="todo-nudge"
      data-state={state}
      title="On your Today list — open it"
      className={`mb-2 flex items-center gap-2 rounded-lg border px-2 py-1.5 text-[11px] leading-snug transition-colors ${
        state === "overdue"
          ? "border-red-200 bg-red-50 text-red-700 hover:border-red-300 dark:border-red-500/40 dark:bg-red-500/10 dark:text-red-200"
          : "border-amber-200 bg-amber-50 text-amber-800 hover:border-amber-300 dark:border-amber-500/40 dark:bg-amber-500/10 dark:text-amber-200"
      }`}
    >
      <AlarmClock className="h-3.5 w-3.5 shrink-0" aria-hidden="true" />
      <span className="min-w-0 flex-1 truncate font-medium">{next.text}</span>
      <span className="shrink-0 opacity-80">{relativeDue(next.due_at, now)}</span>
    </NavLink>
  );
}
