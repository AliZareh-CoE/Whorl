/** Plan v2 slice 3 — "This week" strip: overdue first, then due within seven days, then the
 *  next milestones of the current phase. Shared by the Plan page and the project overview.
 *  Data: GET /projects/{slug}/focus/ (also embedded in /overview/). */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CalendarClock, Check, Sparkles } from "lucide-react";
import { api, petReact } from "../../api";

export type FocusItem = { kind: "milestone" | "task"; id: number; title: string; due_date: string | null; days: number | null; phase: string; phase_id: number; milestone: string | null; milestone_id: number | null };
export type FocusData = { project: string; today: string; week_ends: string; overdue: FocusItem[]; due_this_week: FocusItem[]; next_up: FocusItem[]; current_phase: { id: number; name: string; status: string } | null };

function when(i: FocusItem): string {
  if (i.days == null) return "no date";
  if (i.days < 0) return `${-i.days} d late`;
  if (i.days === 0) return "today";
  if (i.days === 1) return "tomorrow";
  return `in ${i.days} d`;
}

export default function Focus({ slug, initial, compact = false, onChanged }: { slug: string; initial?: FocusData; compact?: boolean; onChanged?: () => void }) {
  const queryClient = useQueryClient();
  const { data } = useQuery({ queryKey: ["focus", slug], queryFn: () => api<FocusData>(`/projects/${slug}/focus/`), initialData: initial, staleTime: initial ? 30_000 : 0 });
  const complete = useMutation({
    mutationFn: (i: FocusItem) => i.kind === "milestone"
      ? api(`/milestones/${i.id}/`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ completed_at: new Date().toISOString() }) })
      : api(`/tasks/${i.id}/`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ done: true }) }),
    onMutate: (i) => {
      if (i.kind === "milestone") petReact("milestone");
      queryClient.setQueryData<FocusData>(["focus", slug], (old) => old ? { ...old, overdue: old.overdue.filter((x) => !(x.kind === i.kind && x.id === i.id)), due_this_week: old.due_this_week.filter((x) => !(x.kind === i.kind && x.id === i.id)), next_up: old.next_up.filter((x) => !(x.kind === i.kind && x.id === i.id)) } : old);
    },
    onSettled: () => { queryClient.invalidateQueries({ queryKey: ["focus", slug] }); queryClient.invalidateQueries({ queryKey: ["plan", slug] }); queryClient.invalidateQueries({ queryKey: ["overview", slug] }); queryClient.invalidateQueries({ queryKey: ["roadmap", slug] }); queryClient.invalidateQueries({ queryKey: ["dashboard"] }); onChanged?.(); },
  });
  if (!data) return null;
  const groups: { key: string; label: string; icon: typeof AlertTriangle; items: FocusItem[]; tone: string }[] = [
    { key: "overdue", label: "Overdue", icon: AlertTriangle, items: data.overdue, tone: "text-red-600 dark:text-red-300" },
    { key: "week", label: `Due by ${new Date(`${data.week_ends}T00:00:00`).toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" })}`, icon: CalendarClock, items: data.due_this_week, tone: "text-indigo-600 dark:text-indigo-300" },
    { key: "next", label: data.current_phase ? `Next in ${data.current_phase.name}` : "Next up", icon: Sparkles, items: data.next_up, tone: "text-stone-500 dark:text-stone-400" },
  ].filter((g) => g.items.length > 0);
  if (groups.length === 0) {
    return (
      <div className="rounded-2xl border border-dashed border-stone-200 px-4 py-3 text-xs text-stone-400 dark:border-stone-800" data-testid="focus-empty">
        Nothing due this week and nothing queued in the current phase — a good time to plan the next one.
      </div>
    );
  }
  return (
    <div className={`rounded-2xl border border-stone-200 bg-white dark:border-stone-800 dark:bg-stone-900 ${compact ? "p-3" : "p-4"}`} data-testid="focus-strip">
      <div className="mb-2 flex items-baseline justify-between">
        <p className="text-[10px] font-semibold uppercase tracking-[0.14em] text-stone-400 dark:text-stone-500">This week</p>
        <p className="text-[11px] text-stone-400">{data.overdue.length > 0 ? `${data.overdue.length} overdue · ` : ""}{data.due_this_week.length} due · {data.next_up.length} next</p>
      </div>
      <div className={`grid gap-3 ${groups.length > 1 ? "md:grid-cols-2 lg:grid-cols-3" : ""}`}>
        {groups.map((g) => (
          <div key={g.key} className="min-w-0">
            <p className={`mb-1 flex items-center gap-1 text-[11px] font-medium ${g.tone}`}><g.icon className="h-3 w-3" aria-hidden="true" />{g.label}</p>
            <ul className="space-y-1">
              {g.items.slice(0, compact ? 4 : 8).map((i) => (
                <li key={`${i.kind}-${i.id}`} className="group flex items-center gap-2 text-sm">
                  <button type="button" onClick={() => complete.mutate(i)} aria-label={`Complete ${i.title}`} className={`flex h-4 w-4 shrink-0 items-center justify-center rounded border text-transparent transition-colors hover:border-indigo-400 hover:text-indigo-500 ${i.kind === "milestone" ? "rounded-md border-stone-300 dark:border-stone-600" : "border-stone-200 dark:border-stone-700"}`}><Check className="h-2.5 w-2.5" aria-hidden="true" /></button>
                  <span className="min-w-0 flex-1 truncate text-stone-800 dark:text-stone-200" title={`${i.title} · ${i.milestone ? `${i.milestone} · ` : ""}${i.phase}`}>{i.title}{i.kind === "task" && <span className="ml-1 text-[10px] text-stone-400">task</span>}</span>
                  <span className={`shrink-0 text-[11px] tabular-nums ${i.days != null && i.days < 0 ? "font-medium text-red-600 dark:text-red-300" : "text-stone-400"}`}>{when(i)}</span>
                </li>
              ))}
              {g.items.length > (compact ? 4 : 8) && <li className="text-[11px] text-stone-400">… {g.items.length - (compact ? 4 : 8)} more</li>}
            </ul>
          </div>
        ))}
      </div>
    </div>
  );
}
