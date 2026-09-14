/** #517 — the plan review: every open milestone as a card, one at a time, in the order the
 *  server decides (overdue first, then by due date, undated last), with everything Atlas knows
 *  about it — late, blocked, slack, conflict, drift, open tasks. One key decides each card:
 *  k keep · d done · w / W push a week / two · m move to a date · s skip · ← → walk. Verdicts
 *  are ordinary milestone PATCHes; finishing records the sitting (POST /plan/review/). */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { AlertTriangle, ArrowLeft, ArrowRight, Calendar, Check, ClipboardCheck, Lock, SkipForward, X } from "lucide-react";
import { promptDialog } from "../../../components/Dialog";
import { api, petReact } from "../../api";
import { ErrorState } from "../../../components/ErrorState";

export type ReviewRow = { id: number; title: string; phase: string; phase_id: number; due_date: string | null; days: number | null; overdue: boolean; notes: string; blocked: boolean; blocked_by: string[]; slack: number | null; conflict: boolean; baseline: string | null; moves: number; slipped: number | null; open_tasks: number; tasks: number };
export type ReviewState = { last: string | null; days_since: number | null; due: boolean; open: number; summary: { kept: number; completed: number; moved: number; skipped: number; note: string } | null };
type ReviewData = { state: ReviewState; queue: ReviewRow[] };
type Verdict = "kept" | "completed" | "moved" | "skipped";

const DAY = 864e5;
function plusDays(iso: string | null, days: number): string { const base = iso ? new Date(`${iso}T00:00:00Z`).getTime() : Math.floor(Date.now() / DAY) * DAY; return new Date(base + days * DAY).toISOString().slice(0, 10); }
function inTextField(t: EventTarget | null): boolean { const el = t as HTMLElement | null; if (!el) return false; const tag = el.tagName; return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || !!el.isContentEditable; }

export function reviewedLabel(state: ReviewState | undefined): string {
  if (!state || state.days_since == null) return "never reviewed";
  if (state.days_since === 0) return "reviewed today";
  if (state.days_since === 1) return "reviewed yesterday";
  return `reviewed ${state.days_since} d ago`;
}

export default function Review({ slug, onClose, onFinished }: { slug: string; onClose: () => void; onFinished: (state: ReviewState) => void }) {
  const queryClient = useQueryClient();
  const { data, isLoading, error, refetch } = useQuery({ queryKey: ["plan-review", slug], queryFn: () => api<ReviewData>(`/projects/${slug}/plan/review/`), staleTime: Infinity });
  const [index, setIndex] = useState(0);
  const [verdicts, setVerdicts] = useState<Record<number, { verdict: Verdict; to?: string }>>({});
  const [note, setNote] = useState("");
  const queue = useMemo(() => data?.queue ?? [], [data]);
  const current = queue[index];
  const done = index >= queue.length && queue.length > 0;
  const counts = useMemo(() => { const c = { kept: 0, completed: 0, moved: 0, skipped: 0 }; Object.values(verdicts).forEach((v) => { c[v.verdict] += 1; }); return c; }, [verdicts]);
  const invalidate = () => { ["plan", "roadmap", "focus", "overview"].forEach((k) => queryClient.invalidateQueries({ queryKey: [k, slug] })); queryClient.invalidateQueries({ queryKey: ["dashboard"] }); };
  const patch = useMutation({
    mutationFn: ({ id, body }: { id: number; body: Record<string, unknown> }) => api(`/milestones/${id}/`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
    onSuccess: invalidate,
  });
  const finish = useMutation({
    mutationFn: () => api<ReviewState>(`/projects/${slug}/plan/review/`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ...counts, note }) }),
    onSuccess: (state) => { queryClient.removeQueries({ queryKey: ["plan-review", slug] }); invalidate(); onFinished(state); },
  });
  const decide = (verdict: Verdict, to?: string) => {
    if (!current) return;
    setVerdicts((v) => ({ ...v, [current.id]: { verdict, to } }));
    if (verdict === "completed") { petReact("milestone"); patch.mutate({ id: current.id, body: { completed_at: new Date().toISOString() } }); }
    if (verdict === "moved" && to) patch.mutate({ id: current.id, body: { due_date: to } });
    setIndex((i) => i + 1);
  };
  const pickDate = async () => {
    if (!current) return;
    const iso = await promptDialog({ title: `Move “${current.title}”`, label: "New due date (YYYY-MM-DD)", initial: current.due_date ?? plusDays(null, 7), validate: (v) => (/^\d{4}-\d{2}-\d{2}$/.test(v.trim()) && !Number.isNaN(Date.parse(v.trim())) ? null : "Write the date as YYYY-MM-DD.") });
    if (iso && iso.trim() !== current.due_date) decide("moved", iso.trim());
  };
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.metaKey || e.ctrlKey || e.altKey || inTextField(e.target)) return;
      if (e.key === "Escape") { e.preventDefault(); onClose(); return; }
      if (e.key === "ArrowLeft") { e.preventDefault(); setIndex((i) => Math.max(0, i - 1)); return; }
      if (e.key === "ArrowRight") { e.preventDefault(); setIndex((i) => Math.min(queue.length, i + 1)); return; }
      if (!current) return;
      if (e.key === "k") { e.preventDefault(); decide("kept"); }
      else if (e.key === "d") { e.preventDefault(); decide("completed"); }
      else if (e.key === "w") { e.preventDefault(); decide("moved", plusDays(current.due_date, 7)); }
      else if (e.key === "W") { e.preventDefault(); decide("moved", plusDays(current.due_date, 14)); }
      else if (e.key === "m") { e.preventDefault(); void pickDate(); }
      else if (e.key === "s") { e.preventDefault(); decide("skipped"); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }); // re-bound each render on purpose: `current` and `queue` change as the walk advances
  const chip = (cls: string, text: string, key: string) => <span key={key} className={`rounded-md px-1.5 py-0.5 text-[11px] ${cls}`}>{text}</span>;
  const facts = (m: ReviewRow) => {
    const out: JSX.Element[] = [];
    if (m.overdue) out.push(chip("bg-red-500/10 font-medium text-red-600 dark:text-red-300", `${-(m.days as number)} d late`, "late"));
    else if (m.days != null) out.push(chip("bg-stone-100 text-stone-500 dark:bg-stone-800 dark:text-stone-400", m.days === 0 ? "due today" : `due in ${m.days} d`, "due"));
    else out.push(chip("bg-stone-100 text-stone-500 dark:bg-stone-800 dark:text-stone-400", "no date", "undated"));
    if (m.blocked) out.push(chip("bg-amber-500/10 text-amber-800 dark:text-amber-200", `waits for ${m.blocked_by.join(", ")}`, "blocked"));
    if (m.conflict) out.push(chip("bg-amber-500/10 text-amber-800 dark:text-amber-200", "due before its blocker", "conflict"));
    if (m.slack != null && m.slack >= 0 && m.slack <= 7) out.push(chip("bg-amber-500/10 text-amber-800 dark:text-amber-200", m.slack === 0 ? "no slack" : `${m.slack} d slack`, "slack"));
    if (m.moves > 0 && m.slipped) out.push(chip("bg-stone-100 text-stone-500 dark:bg-stone-800 dark:text-stone-400", `${m.slipped > 0 ? `slipped ${m.slipped} d` : `pulled in ${-m.slipped} d`}${m.moves > 1 ? ` · ${m.moves}×` : ""}`, "slip"));
    if (m.tasks > 0) out.push(chip("bg-stone-100 text-stone-500 dark:bg-stone-800 dark:text-stone-400", `${m.tasks - m.open_tasks}/${m.tasks} tasks`, "tasks"));
    return out;
  };
  const btn = "inline-flex items-center gap-1.5 rounded-lg border border-stone-300 px-3 py-1.5 text-sm text-stone-700 hover:border-indigo-400 hover:text-indigo-700 dark:border-stone-700 dark:text-stone-200 dark:hover:text-indigo-300";
  const kbd = (k: string) => <kbd className="rounded border border-stone-300 bg-stone-50 px-1 font-mono text-[10px] text-stone-500 dark:border-stone-600 dark:bg-stone-800 dark:text-stone-400">{k}</kbd>;
  return (
    <section className="rise mx-auto max-w-2xl" data-testid="plan-review" aria-label="Plan review">
      <div className="mb-3 flex items-center justify-between text-xs text-stone-400">
        <span className="inline-flex items-center gap-1.5"><ClipboardCheck className="h-3.5 w-3.5" aria-hidden="true" />Plan review · {reviewedLabel(data?.state)}</span>
        <span className="flex items-center gap-3">
          {queue.length > 0 && <span data-testid="review-progress">{Math.min(index, queue.length)} / {queue.length}</span>}
          <button type="button" onClick={onClose} className="rounded-md p-1 hover:bg-stone-100 dark:hover:bg-stone-800" aria-label="Leave the review"><X className="h-4 w-4" aria-hidden="true" /></button>
        </span>
      </div>
      {queue.length > 0 && <div className="mb-4 h-1 w-full overflow-hidden rounded-full bg-stone-100 dark:bg-stone-800"><div className="h-1 rounded-full bg-indigo-500 transition-[width]" style={{ width: `${(Math.min(index, queue.length) / queue.length) * 100}%` }} /></div>}
      {error ? (
        <ErrorState message="Couldn't load the plan review." onRetry={() => refetch()} />
      ) : isLoading ? (
        <p className="text-sm text-stone-400">Loading the plan…</p>
      ) : queue.length === 0 ? (
        <div className="rounded-2xl border border-dashed border-stone-200 p-8 text-center text-sm text-stone-400 dark:border-stone-800" data-testid="review-empty">Nothing open to review — every milestone is done.</div>
      ) : current ? (
        <div className="rounded-2xl border border-stone-200 bg-white p-6 shadow-sm dark:border-stone-800 dark:bg-stone-900" data-testid="review-card">
          <p className="mb-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-stone-400">{current.phase}</p>
          <h2 className="font-display text-2xl font-semibold leading-snug text-stone-900 dark:text-stone-100">{current.title}</h2>
          <div className="mt-3 flex flex-wrap items-center gap-1.5" data-testid="review-facts">{facts(current)}</div>
          {current.notes && <p className="mt-3 whitespace-pre-line text-sm text-stone-500 dark:text-stone-400">{current.notes}</p>}
          <div className="mt-6 flex flex-wrap gap-2">
            <button type="button" onClick={() => decide("kept")} className={btn} data-testid="review-keep"><Check className="h-4 w-4 text-emerald-500" aria-hidden="true" />Keep {kbd("k")}</button>
            <button type="button" onClick={() => decide("completed")} className={btn} data-testid="review-done"><Check className="h-4 w-4 text-indigo-500" aria-hidden="true" />Done {kbd("d")}</button>
            <button type="button" onClick={() => decide("moved", plusDays(current.due_date, 7))} className={btn} data-testid="review-week"><Calendar className="h-4 w-4 text-amber-500" aria-hidden="true" />+1 week {kbd("w")}</button>
            <button type="button" onClick={() => decide("moved", plusDays(current.due_date, 14))} className={btn}><Calendar className="h-4 w-4 text-amber-500" aria-hidden="true" />+2 weeks {kbd("W")}</button>
            <button type="button" onClick={() => void pickDate()} className={btn} data-testid="review-move"><Calendar className="h-4 w-4 text-stone-400" aria-hidden="true" />Move to… {kbd("m")}</button>
            <button type="button" onClick={() => decide("skipped")} className={btn} data-testid="review-skip"><SkipForward className="h-4 w-4 text-stone-400" aria-hidden="true" />Skip {kbd("s")}</button>
          </div>
          {current.blocked && <p className="mt-4 flex items-center gap-1.5 text-xs text-stone-400"><Lock className="h-3 w-3" aria-hidden="true" />Waiting milestones usually keep their date; the blocker's review decides.</p>}
          {current.overdue && !current.blocked && <p className="mt-4 flex items-center gap-1.5 text-xs text-stone-400"><AlertTriangle className="h-3 w-3" aria-hidden="true" />Late: mark it done if it is, or give it a real date — a stale date hides the plan.</p>}
          <div className="mt-4 flex items-center justify-between text-xs text-stone-400">
            <button type="button" onClick={() => setIndex((i) => Math.max(0, i - 1))} disabled={index === 0} className="inline-flex items-center gap-1 disabled:opacity-40"><ArrowLeft className="h-3 w-3" aria-hidden="true" />previous</button>
            <button type="button" onClick={() => setIndex((i) => Math.min(queue.length, i + 1))} className="inline-flex items-center gap-1">next<ArrowRight className="h-3 w-3" aria-hidden="true" /></button>
          </div>
        </div>
      ) : done ? (
        <div className="rounded-2xl border border-stone-200 bg-white p-6 dark:border-stone-800 dark:bg-stone-900" data-testid="review-summary">
          <h2 className="font-display text-xl font-semibold text-stone-900 dark:text-stone-100">Reviewed {queue.length} milestone{queue.length === 1 ? "" : "s"}</h2>
          <p className="mt-1 text-sm text-stone-500 dark:text-stone-400">{counts.kept} kept · {counts.completed} completed · {counts.moved} moved · {counts.skipped} skipped</p>
          <ul className="mt-3 space-y-1 text-sm">
            {queue.map((m) => { const v = verdicts[m.id]; return <li key={m.id} className="flex items-center gap-2 text-stone-600 dark:text-stone-300"><span className={`w-20 shrink-0 text-[11px] uppercase tracking-wider ${v?.verdict === "completed" ? "text-indigo-500" : v?.verdict === "moved" ? "text-amber-600 dark:text-amber-300" : "text-stone-400"}`}>{v?.verdict ?? "unseen"}</span><span className="truncate">{m.title}</span>{v?.to && <span className="shrink-0 text-xs text-stone-400">→ {v.to}</span>}</li>; })}
          </ul>
          <textarea value={note} onChange={(e) => setNote(e.target.value)} rows={2} placeholder="A line for the record — what is the risk this week?" className="mt-4 w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm dark:border-stone-700 dark:bg-stone-800 dark:text-stone-100" aria-label="Review note" data-testid="review-note" />
          <div className="mt-3 flex gap-2">
            <button type="button" onClick={() => finish.mutate()} disabled={finish.isPending} className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50" data-testid="review-finish"><ClipboardCheck className="h-4 w-4" aria-hidden="true" />{finish.isPending ? "Recording…" : "Finish review"}</button>
            <button type="button" onClick={() => setIndex(0)} className={btn}>Walk it again</button>
          </div>
        </div>
      ) : null}
    </section>
  );
}
