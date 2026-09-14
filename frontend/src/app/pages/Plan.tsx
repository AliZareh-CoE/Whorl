/** Plan v2 (Observatory) — the plan as a document. Read view: phases as glass panels with
 *  milestone/task check-off, status cycling and quick-add. Outline mode: the whole plan as a
 *  Markdown outline with a live dry-run preview (created / renamed / deleted) before saving.
 *  Everything here is also in the API (/projects/{slug}/plan/, /outline/) and MCP. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { AlertTriangle, CalendarRange, Check, FileText, HelpCircle, History, LayoutList, Loader2, Lock, Pencil, Plus, Route, Save, Trash2, X } from "lucide-react";
import { api, petReact } from "../api";
import { confirmDialog, errorDialog, promptDialog } from "../../components/Dialog";
import { Kebab } from "../../components/Menu";
import { Skeleton, SkeletonCard } from "../../components/Skeleton";
import { ErrorState } from "../../components/ErrorState";
import Roadmap from "./plan/Roadmap";
import Orbit from "./plan/Orbit";
import Focus from "./plan/Focus";
import MilestoneDrawer, { type DrawerMilestone } from "./plan/MilestoneDrawer";

type Task = { id: number; title: string; done: boolean; due_date?: string | null };
type Milestone = { id: number; title: string; due_date: string | null; completed_at: string | null; overdue: boolean; notes?: string; tasks: Task[]; blocked_by: { id: number; title: string }[]; blocked: boolean; blocks: number[]; slack: number | null; baseline: string | null; moves: number; slipped: number | null; history: DateMove[] };
type DateMove = { from: string | null; to: string | null; at: string; reason: string }; // #516
type Question = { id: number; question: string; status: string };
type Phase = { id: number; name: string; order: number; status: string; progress: number; objective: string; target_start: string | null; target_end: string | null; questions: Question[]; milestones: Milestone[] };
type Conflict = { id: number; title: string; due_date: string; blocker_id: number; blocker_title: string; blocker_due: string; suggested: string };
type Chain = { ids: number[]; titles: string[]; from: string | null; to: string | null; days: number; slack: number | null }; // #515
type Drift = { total: number; moved: number; most: { id: number; title: string; phase: string; slipped: number; baseline: string | null; due_date: string | null } | null; baseline_end: string | null; current_end: string | null }; // #516
type PlanData = { project: string; project_name: string; project_color: string; questions: Question[]; phases: Phase[]; conflicts: Conflict[]; critical_chain: Chain; drift: Drift };
const TIGHT_DAYS = 7; // mirrors plans.dependencies.TIGHT_DAYS
type Summary = { phases: number; milestones: number; tasks: number; created: string[]; renamed: string[]; deleted: string[]; errors: { line: number; message: string }[]; applied?: boolean; markdown?: string };

const STATUS_ORDER = ["not_started", "in_progress", "blocked", "done"];
const STATUS_LABEL: Record<string, string> = { not_started: "not started", in_progress: "in progress", blocked: "blocked", done: "done" };
const statusCls: Record<string, string> = {
  done: "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300",
  in_progress: "bg-indigo-500/15 text-indigo-700 dark:text-indigo-200",
  blocked: "bg-red-500/10 text-red-700 dark:text-red-300",
  not_started: "bg-stone-100 text-stone-500 dark:bg-stone-800 dark:text-stone-300",
};
const panel = "rounded-2xl border border-stone-200 bg-white dark:border-stone-800 dark:bg-stone-900";
const STARTER = `# Literature review  [in_progress]  (${new Date().toISOString().slice(0, 10)} → )
> What this phase must settle before the next one can start.
- [ ] Annotated bibliography of the key papers
  - [ ] Pull the citing papers
  - [ ] Rate each on the review matrix
- [ ] Paradigm chosen

# Pilot study
- [ ] Ethics approval  (due ${new Date(Date.now() + 45 * 864e5).toISOString().slice(0, 10)})
- [ ] Five participants run
`;

function Ring({ percent, color, size = 44 }: { percent: number; color: string; size?: number }) {
  const r = (size - 4) / 2; const c = 2 * Math.PI * r; const off = c * (1 - Math.max(0, Math.min(100, percent)) / 100);
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="orbit-ring shrink-0" aria-hidden="true">
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="currentColor" strokeWidth="3" className="text-stone-100 dark:text-stone-800" />
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth="3" strokeLinecap="round" strokeDasharray={c} strokeDashoffset={off} transform={`rotate(-90 ${size / 2} ${size / 2})`} style={{ transition: "stroke-dashoffset 900ms cubic-bezier(.2,.7,.2,1)" }} />
    </svg>
  );
}

function useDebounced<T>(value: T, ms: number): T {
  const [v, setV] = useState(value);
  useEffect(() => { const t = setTimeout(() => setV(value), ms); return () => clearTimeout(t); }, [value, ms]);
  return v;
}

export default function Plan() {
  const { slug } = useParams();
  const queryClient = useQueryClient();
  const { data, isLoading, error, refetch } = useQuery({ queryKey: ["plan", slug], queryFn: () => api<PlanData>(`/projects/${slug}/plan/`) });
  const [mode, setMode] = useState<"cards" | "roadmap" | "outline">(() => { try { return (localStorage.getItem("atlas-plan-mode") as "cards" | "roadmap" | "outline") || "cards"; } catch { return "cards"; } });
  const outlineMode = mode === "outline";
  const setOutlineMode = (v: boolean | ((prev: boolean) => boolean)) => setMode((prev) => ((typeof v === "function" ? v(prev === "outline") : v) ? "outline" : "cards"));
  useEffect(() => { try { localStorage.setItem("atlas-plan-mode", mode); } catch { /* private mode */ } }, [mode]);
  const [toast, setToast] = useState("");
  const [drawerId, setDrawerId] = useState<number | null>(null);
  const flash = (msg: string) => { setToast(msg); setTimeout(() => setToast(""), 4000); };
  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["plan", slug] });
    queryClient.invalidateQueries({ queryKey: ["overview", slug] });
    queryClient.invalidateQueries({ queryKey: ["dashboard"] });
  };
  function patchPlan(update: (plan: PlanData) => PlanData) { queryClient.setQueryData<PlanData>(["plan", slug], (old) => (old ? update(old) : old)); }

  // #513: dates that contradict the dependencies — one click pushes them, blockers first
  const fixConflicts = useMutation({
    mutationFn: () => api<{ changes: { id: number; title: string; from: string; to: string }[] }>(`/projects/${slug}/plan/reschedule-conflicts/`, { method: "POST" }),
    onSuccess: (out) => { invalidate(); setToast(out.changes.length ? `Moved ${out.changes.map((c) => `${c.title} → ${c.to}`).join(", ")}` : "Nothing to move."); window.setTimeout(() => setToast(""), 5000); },
  });
  const conflictIds = new Set((data?.conflicts ?? []).map((c) => c.id));
  const chainIds = new Set(data?.critical_chain?.ids ?? []); // #515
  const toggleMilestone = useMutation({
    mutationFn: (m: Milestone) => api(`/milestones/${m.id}/`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ completed_at: m.completed_at ? null : new Date().toISOString() }) }),
    onMutate: async (m) => {
      if (!m.completed_at) petReact("milestone");
      patchPlan((plan) => ({ ...plan, phases: plan.phases.map((ph) => ({ ...ph, milestones: ph.milestones.map((x) => (x.id === m.id ? { ...x, completed_at: x.completed_at ? null : new Date().toISOString() } : x)) })) }));
    },
    // #512: completing a blocker frees the milestones that waited only on it
    onSuccess: (_r, m) => {
      if (m.completed_at) return;
      const plan = queryClient.getQueryData<PlanData>(["plan", slug]); if (!plan) return;
      const all = plan.phases.flatMap((ph) => ph.milestones);
      const freed = all.filter((x) => x.id !== m.id && !x.completed_at && (x.blocked_by ?? []).some((b) => b.id === m.id) && (x.blocked_by ?? []).every((b) => b.id === m.id || all.find((y) => y.id === b.id)?.completed_at));
      if (freed.length) { setToast(`Unblocked: ${freed.map((x) => x.title).join(", ")}`); window.setTimeout(() => setToast(""), 4000); }
    },
    onSettled: invalidate,
  });
  const toggleTask = useMutation({
    mutationFn: (t: Task) => api(`/tasks/${t.id}/`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ done: !t.done }) }),
    onMutate: async (t) => { patchPlan((plan) => ({ ...plan, phases: plan.phases.map((ph) => ({ ...ph, milestones: ph.milestones.map((m) => ({ ...m, tasks: m.tasks.map((x) => (x.id === t.id ? { ...x, done: !x.done } : x)) })) })) })); },
    onSettled: invalidate,
  });
  const setStatus = useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) => api(`/phases/${id}/`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ status }) }),
    onMutate: async ({ id, status }) => { patchPlan((plan) => ({ ...plan, phases: plan.phases.map((ph) => (ph.id === id ? { ...ph, status } : ph)) })); },
    onSettled: invalidate,
  });
  const patchPhase = useMutation({
    mutationFn: ({ id, ...body }: { id: number; objective?: string; target_start?: string | null; target_end?: string | null }) => api(`/phases/${id}/`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
    onSettled: invalidate,
  });
  // CRUD sweep 2026-09-06: phases can be added, renamed and deleted here, not only via the outline
  // #429: drag a phase to reorder; drag a milestone onto another phase to move it
  const reorderPhases = useMutation({
    mutationFn: (ids: number[]) => api(`/projects/${slug}/phases/reorder/`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ids }) }),
    onMutate: (ids) => patchPlan((plan) => { const by = new Map(plan.phases.map((p) => [p.id, p])); const ordered = ids.map((id) => by.get(id)!).filter(Boolean); return { ...plan, phases: ordered.map((p, i) => ({ ...p, order: i + 1 })) }; }),
    onSettled: invalidate,
  });
  const moveMilestone = useMutation({
    mutationFn: ({ id, phase }: { id: number; phase: number }) => api(`/milestones/${id}/`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ phase }) }),
    onMutate: ({ id, phase }) => patchPlan((plan) => { const m = plan.phases.flatMap((p) => p.milestones).find((x) => x.id === id); if (!m) return plan; return { ...plan, phases: plan.phases.map((p) => ({ ...p, milestones: p.id === phase ? [...p.milestones.filter((x) => x.id !== id), m] : p.milestones.filter((x) => x.id !== id) })) }; }),
    onSettled: invalidate,
  });
  const dropPhaseBefore = (dragged: number, target: number) => {
    if (!data || dragged === target) return;
    const ids = data.phases.map((p) => p.id).filter((id) => id !== dragged);
    ids.splice(ids.indexOf(target), 0, dragged);
    reorderPhases.mutate(ids);
  };
  const addPhase = useMutation({
    mutationFn: (name: string) => api(`/phases/`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ project: slug, name, order: (data?.phases.reduce((n, p) => Math.max(n, p.order), 0) ?? 0) + 1 }) }),
    onSuccess: invalidate,
    onError: (e) => void errorDialog("Couldn't add the phase", e),
  });
  const renamePhase = useMutation({
    mutationFn: ({ id, name }: { id: number; name: string }) => api(`/phases/${id}/`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name }) }),
    onSuccess: invalidate,
    onError: (e) => void errorDialog("Couldn't rename the phase", e),
  });
  const deletePhase = useMutation({
    mutationFn: (id: number) => api(`/phases/${id}/`, { method: "DELETE" }),
    onSuccess: invalidate,
    onError: (e) => void errorDialog("Couldn't delete the phase", e),
  });
  const askAddPhase = async () => { const name = await promptDialog({ title: "New phase", label: "Name", placeholder: "e.g. Pilot study", validate: (v) => (v.trim() ? null : "Name the phase.") }); if (name) addPhase.mutate(name.trim()); };
  const attachQuestion = useMutation({
    mutationFn: ({ question, phases }: { question: number; phases: number[] }) => api(`/questions/${question}/`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ phases }) }),
    onSettled: invalidate,
  });
  const addMilestone = useMutation({
    mutationFn: ({ phase, title }: { phase: number; title: string }) => api(`/milestones/`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ phase, title }) }),
    onSuccess: invalidate,
  });
  const addTask = useMutation({
    mutationFn: ({ milestone, title }: { milestone: number; title: string }) => api(`/tasks/`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ milestone, title }) }),
    onSuccess: invalidate,
  });

  if (isLoading)
    return (
      <div role="status" aria-label="Loading" className="space-y-4">
        <Skeleton className="h-4 w-40" />
        <div className="flex items-baseline justify-between gap-4"><Skeleton className="h-7 w-24" /><Skeleton className="h-4 w-40" /></div>
        {Array.from({ length: 3 }).map((_, i) => <SkeletonCard key={i} />)}
      </div>
    );
  if (error || !data) return <ErrorState message="Couldn't load the plan." onRetry={() => refetch()} />;

  const totalMilestones = data.phases.reduce((n, p) => n + p.milestones.length, 0);
  const doneMilestones = data.phases.reduce((n, p) => n + p.milestones.filter((m) => m.completed_at).length, 0);
  const percent = totalMilestones ? Math.round((100 * doneMilestones) / totalMilestones) : 0;
  const accent = data.project_color || "var(--color-indigo-500)";
  const overdue = data.phases.flatMap((p) => p.milestones).filter((m) => m.overdue && !m.completed_at).length;

  return (
    <div>
      <nav className="mb-4 text-sm text-stone-500 dark:text-stone-400">
        <Link to="/projects" className="hover:underline">Projects</Link> /{" "}
        <Link to={`/projects/${slug}`} className="hover:underline">{data.project_name}</Link> / Plan
      </nav>

      <div className="mb-5 flex flex-wrap items-center gap-4">
        <Ring percent={percent} color={accent} />
        <div className="min-w-0 flex-1">
          <h1 className="font-display text-3xl font-bold tracking-tight dark:text-stone-100">
            Plan {totalMilestones > 0 && <span className="text-gradient">· {doneMilestones}/{totalMilestones} milestones</span>}
          </h1>
          <p className="mt-0.5 text-sm text-stone-400">
            {data.phases.length} phase{data.phases.length === 1 ? "" : "s"}
            {overdue > 0 && <span className="ml-2 rounded-full bg-red-500/10 px-2 py-0.5 text-xs font-medium text-red-600 dark:text-red-300">{overdue} overdue</span>}
          </p>
        </div>
        <div className="flex overflow-hidden rounded-lg border border-stone-300 text-sm dark:border-stone-700" role="tablist" aria-label="Plan view">
          {([["cards", "Phases", LayoutList], ["roadmap", "Roadmap", CalendarRange], ["outline", "Outline", FileText]] as const).map(([k, label, Icon]) => (
            <button key={k} type="button" role="tab" aria-selected={mode === k} onClick={() => setMode(k)} className={`inline-flex items-center gap-1.5 px-3 py-1.5 font-medium transition-colors ${mode === k ? "bg-indigo-600 text-white" : "text-stone-600 hover:bg-stone-100 dark:text-stone-300 dark:hover:bg-stone-800"}`} title={k === "outline" ? "Write the whole plan as a Markdown outline" : k === "roadmap" ? "Phases on a time axis — drag to reschedule" : "Phase cards with check-off and quick-add"}>
              <Icon className="h-4 w-4" aria-hidden="true" />{label}
            </button>
          ))}
        </div>
      </div>

      {(data.critical_chain?.ids?.length ?? 0) > 1 && mode !== "roadmap" && (
        <p className="rise mb-4 flex min-w-0 items-center gap-2 text-xs text-stone-500 dark:text-stone-400" data-testid="critical-chain" title="The dependency chain that decides when the plan ends: from the milestone due last, back through the blocker with the least room at each step">
          <Route className="h-3.5 w-3.5 shrink-0 text-indigo-500 dark:text-indigo-300" aria-hidden="true" />
          <span className="shrink-0 font-medium text-stone-700 dark:text-stone-200">Critical chain</span>
          <span className="min-w-0 truncate">{data.critical_chain.titles.join(" → ")}</span>
          <span className="shrink-0 text-stone-400">· {data.critical_chain.days} d</span>
          <span className={`shrink-0 rounded-md px-1.5 py-0.5 ${(data.critical_chain.slack ?? 99) <= TIGHT_DAYS ? "bg-amber-500/10 text-amber-800 dark:text-amber-200" : "bg-stone-100 text-stone-500 dark:bg-stone-800 dark:text-stone-400"}`}>{data.critical_chain.slack == null ? "no dated dependants" : data.critical_chain.slack < 0 ? `${-data.critical_chain.slack} d over` : data.critical_chain.slack === 0 ? "no slack" : `${data.critical_chain.slack} d of slack`}</span>
        </p>
      )}
      {(data.drift?.moved ?? 0) > 0 && mode !== "roadmap" && (
        <p className="rise mb-4 flex min-w-0 flex-wrap items-center gap-x-2 gap-y-1 text-xs text-stone-500 dark:text-stone-400" data-testid="plan-drift" title="Every due-date change is logged; a milestone's baseline is the first date it was given">
          <History className="h-3.5 w-3.5 shrink-0 text-stone-400" aria-hidden="true" />
          <span className="shrink-0 font-medium text-stone-700 dark:text-stone-200">Drift</span>
          <span className={`shrink-0 rounded-md px-1.5 py-0.5 ${data.drift.total > 0 ? "bg-amber-500/10 text-amber-800 dark:text-amber-200" : "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"}`}>{data.drift.total > 0 ? `+${data.drift.total} d` : data.drift.total < 0 ? `${data.drift.total} d` : "±0 d"} since the baseline</span>
          <span className="shrink-0">· {data.drift.moved} milestone{data.drift.moved === 1 ? "" : "s"} moved</span>
          {data.drift.most && <span className="min-w-0 truncate">· <span className="font-medium text-stone-700 dark:text-stone-200">{data.drift.most.title}</span> slipped most (+{data.drift.most.slipped} d)</span>}
          {data.drift.baseline_end && data.drift.current_end && data.drift.baseline_end !== data.drift.current_end && <span className="shrink-0">· ends {data.drift.current_end}, first planned {data.drift.baseline_end}</span>}
        </p>
      )}
      {(data.conflicts?.length ?? 0) > 0 && (
        <div className="rise mb-4 flex flex-wrap items-center gap-x-4 gap-y-2 rounded-2xl border border-amber-300/60 bg-amber-500/10 px-4 py-2.5 text-sm text-amber-900 dark:border-amber-500/40 dark:text-amber-100" role="status" data-testid="conflict-banner">
          <AlertTriangle className="h-4 w-4 shrink-0 text-amber-600 dark:text-amber-300" aria-hidden="true" />
          <span className="font-medium">{data.conflicts.length} date{data.conflicts.length === 1 ? "" : "s"} contradict{data.conflicts.length === 1 ? "s" : ""} a dependency</span>
          <ul className="min-w-0 flex-1 text-xs">
            {data.conflicts.slice(0, 3).map((c) => <li key={c.id} className="truncate"><span className="font-medium">{c.title}</span> is due {c.due_date} but waits for <span className="font-medium">{c.blocker_title}</span> (due {c.blocker_due}) — suggest {c.suggested}</li>)}
            {data.conflicts.length > 3 && <li className="text-amber-700/80 dark:text-amber-200/80">…and {data.conflicts.length - 3} more</li>}
          </ul>
          <button type="button" onClick={() => fixConflicts.mutate()} disabled={fixConflicts.isPending} className="shrink-0 rounded-md bg-amber-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-amber-700 disabled:opacity-50" data-testid="conflict-fix">{fixConflicts.isPending ? "Moving…" : "Push the dates"}</button>
        </div>
      )}
      {mode === "roadmap" ? (
        <Roadmap slug={slug!} accent={accent} onChanged={invalidate} />
      ) : outlineMode ? (
        <OutlineEditor slug={slug!} empty={data.phases.length === 0} onSaved={(s) => { setOutlineMode(false); invalidate(); flash(`Plan updated — ${s.phases} phase${s.phases === 1 ? "" : "s"}, ${s.milestones} milestone${s.milestones === 1 ? "" : "s"}${s.created.length ? `, ${s.created.length} new` : ""}${s.deleted.length ? `, ${s.deleted.length} removed` : ""}.`); }} />
      ) : data.phases.length === 0 ? (
        <div className={`${panel} rise p-10 text-center`}>
          <FileText className="mx-auto mb-2 h-7 w-7 text-indigo-400" aria-hidden="true" />
          <p className="mb-1 font-medium text-stone-700 dark:text-stone-100">No plan yet</p>
          <p className="mx-auto mb-4 max-w-md text-sm text-stone-400">A plan is a few phases, each with milestones and optional tasks. Write it like a document: one line per item, checkboxes, due dates in parentheses.</p>
          <button type="button" onClick={() => setOutlineMode(true)} className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700"><FileText className="h-4 w-4" aria-hidden="true" />Write the plan</button>
        </div>
      ) : (
        <div className="space-y-4">
          <Orbit phases={data.phases} accent={accent} onOpen={(id) => document.getElementById(`phase-${id}`)?.scrollIntoView({ behavior: "smooth", block: "start" })} />
          <Focus slug={slug!} onChanged={invalidate} />
          {data.phases.map((phase, pi) => (
            <PhaseCard key={phase.id} phase={phase} index={pi} accent={accent} conflictIds={conflictIds} chainIds={chainIds} onDropPhase={(dragged) => dropPhaseBefore(dragged, phase.id)} onDropMilestone={(id) => moveMilestone.mutate({ id, phase: phase.id })} onToggleMilestone={(m) => toggleMilestone.mutate(m)} onToggleTask={(t) => toggleTask.mutate(t)} onCycleStatus={() => setStatus.mutate({ id: phase.id, status: STATUS_ORDER[(STATUS_ORDER.indexOf(phase.status) + 1) % STATUS_ORDER.length] })} onAddMilestone={(title) => addMilestone.mutate({ phase: phase.id, title })} onAddTask={(milestone, title) => addTask.mutate({ milestone, title })} onOpen={(id) => setDrawerId(id)} allQuestions={data.questions} onPatchPhase={(body) => patchPhase.mutate({ id: phase.id, ...body })} onRename={async () => { const name = await promptDialog({ title: "Rename phase", label: "Name", initial: phase.name, validate: (v) => (v.trim() ? null : "Name the phase.") }); if (name && name.trim() !== phase.name) renamePhase.mutate({ id: phase.id, name: name.trim() }); }} onDelete={async () => { const n = phase.milestones.length; if (await confirmDialog({ title: `Delete the phase “${phase.name}”?`, body: n ? `Its ${n} milestone${n === 1 ? "" : "s"} and their tasks go with it.` : "The phase has no milestones.", danger: true, confirmLabel: "Delete phase" })) deletePhase.mutate(phase.id); }} onAttachQuestion={(qid, attach) => { const q = data.questions.find((x) => x.id === qid); const current = data.phases.filter((ph) => ph.questions.some((x) => x.id === qid)).map((ph) => ph.id); if (!q) return; attachQuestion.mutate({ question: qid, phases: attach ? [...new Set([...current, phase.id])] : current.filter((id) => id !== phase.id) }); }} />
          ))}
          <button type="button" onClick={() => void askAddPhase()} className="inline-flex items-center gap-1.5 rounded-lg border border-dashed border-stone-300 px-3 py-2 text-sm text-stone-500 hover:border-indigo-400 hover:text-indigo-700 dark:border-stone-700 dark:text-stone-400 dark:hover:text-indigo-300" data-testid="add-phase"><Plus className="h-4 w-4" aria-hidden="true" />Add a phase</button>
        </div>
      )}

      {mode === "cards" && (
        <p className="mt-4 text-xs text-stone-400">
          Tick to complete · click a status to cycle it · type at the bottom of a phase to add a milestone · ⋯ on a phase to rename or delete it
        </p>
      )}
      {drawerId !== null && (() => {
        const found = data.phases.flatMap((ph) => ph.milestones.map((m) => ({ ...m, phase: ph.name }))).find((m) => m.id === drawerId);
        const options = data.phases.flatMap((ph) => ph.milestones.map((m) => ({ id: m.id, title: m.title, phase: ph.name, completed: !!m.completed_at })));
        return found ? <MilestoneDrawer slug={slug!} milestone={found as DrawerMilestone} onClose={() => setDrawerId(null)} options={options} /> : null;
      })()}
      {toast && <div role="status" className="fixed bottom-5 right-5 z-30 rounded-xl border border-stone-200 bg-white px-4 py-2.5 text-sm shadow-lg dark:border-stone-700 dark:bg-stone-900 dark:text-stone-100">{toast}</div>}
    </div>
  );
}

function PhaseCard({ phase, index, accent, onDropPhase, onDropMilestone, onToggleMilestone, onToggleTask, onCycleStatus, onAddMilestone, onAddTask, onOpen, allQuestions, onPatchPhase, onRename, onDelete, onAttachQuestion, conflictIds, chainIds }: { conflictIds?: Set<number>; chainIds?: Set<number>; onRename: () => void; onDelete: () => void; onDropPhase: (draggedPhaseId: number) => void; onDropMilestone: (milestoneId: number) => void; phase: Phase; index: number; accent: string; onToggleMilestone: (m: Milestone) => void; onToggleTask: (t: Task) => void; onCycleStatus: () => void; onAddMilestone: (title: string) => void; onAddTask: (milestone: number, title: string) => void; onOpen: (id: number) => void; allQuestions: Question[]; onPatchPhase: (body: { objective?: string; target_start?: string | null; target_end?: string | null }) => void; onAttachQuestion: (question: number, attach: boolean) => void }) {
  const [draft, setDraft] = useState("");
  const [taskFor, setTaskFor] = useState<number | null>(null);
  const [taskDraft, setTaskDraft] = useState("");
  const [editingObjective, setEditingObjective] = useState(false);
  const [objective, setObjective] = useState(phase.objective);
  useEffect(() => { if (!editingObjective) setObjective(phase.objective); }, [phase.objective, editingObjective]);
  const done = phase.milestones.filter((m) => m.completed_at).length;
  const dates = phase.target_start || phase.target_end ? `${phase.target_start ?? "…"} → ${phase.target_end ?? "…"}` : "";
  const unattached = allQuestions.filter((q) => !phase.questions.some((x) => x.id === q.id));
  const [over, setOver] = useState<"phase" | "milestone" | null>(null);
  const PHASE_MIME = "application/x-atlas-phase", MS_MIME = "application/x-atlas-milestone";
  const kindOf = (dt: DataTransfer) => (dt.types.includes(PHASE_MIME) ? "phase" : dt.types.includes(MS_MIME) ? "milestone" : null);
  return (
    <section id={`phase-${phase.id}`} className={`${panel} rise scroll-mt-4 p-5 transition-shadow ${over === "phase" ? "ring-2 ring-indigo-400" : over === "milestone" ? "ring-2 ring-emerald-400" : ""}`} style={{ ["--i" as string]: index }} data-testid="phase-card"
      onDragOver={(e) => { const k = kindOf(e.dataTransfer); if (!k) return; if (k === "phase" && Number(e.dataTransfer.getData(PHASE_MIME)) === phase.id) return; e.preventDefault(); e.dataTransfer.dropEffect = "move"; setOver(k); }}
      onDragLeave={(e) => { if (!e.currentTarget.contains(e.relatedTarget as Node | null)) setOver(null); }}
      onDrop={(e) => { const k = kindOf(e.dataTransfer); setOver(null); if (!k) return; e.preventDefault(); if (k === "phase") { const id = Number(e.dataTransfer.getData(PHASE_MIME)); if (id && id !== phase.id) onDropPhase(id); } else { const id = Number(e.dataTransfer.getData(MS_MIME)); if (id && !phase.milestones.some((m) => m.id === id)) onDropMilestone(id); } }}>
      <div className="mb-3 flex items-baseline gap-3">
        {/* #429: the number is the drag handle — drop on another phase card to reorder */}
        <span draggable onDragStart={(e) => { e.dataTransfer.setData(PHASE_MIME, String(phase.id)); e.dataTransfer.effectAllowed = "move"; }} className="font-display cursor-grab select-none text-2xl font-bold leading-none text-stone-300 active:cursor-grabbing dark:text-stone-600" title="Drag to reorder phases" data-testid="phase-handle">{String(phase.order).padStart(2, "0")}</span>
        <h2 className="font-display min-w-0 flex-1 text-lg font-semibold text-stone-900 dark:text-stone-100">{phase.name}</h2>
        <label className="hidden shrink-0 items-center gap-1 text-[11px] text-stone-400 sm:flex" title="Target window">
          <input type="date" value={phase.target_start ?? ""} onChange={(e) => onPatchPhase({ target_start: e.target.value || null })} className="w-[7.5rem] rounded-md border border-transparent bg-transparent px-1 py-0.5 text-[11px] text-stone-400 hover:border-stone-300 focus:border-indigo-400 focus:outline-none dark:hover:border-stone-700" aria-label={`${phase.name} start`} />
          →
          <input type="date" value={phase.target_end ?? ""} onChange={(e) => onPatchPhase({ target_end: e.target.value || null })} className="w-[7.5rem] rounded-md border border-transparent bg-transparent px-1 py-0.5 text-[11px] text-stone-400 hover:border-stone-300 focus:border-indigo-400 focus:outline-none dark:hover:border-stone-700" aria-label={`${phase.name} end`} />
        </label>
        <button type="button" onClick={onCycleStatus} className={`shrink-0 rounded-full px-2.5 py-0.5 text-xs transition-colors hover:ring-2 hover:ring-indigo-400/40 ${statusCls[phase.status] ?? statusCls.not_started}`} title="Click to cycle the status">{STATUS_LABEL[phase.status] ?? phase.status}</button>
        <Kebab label={`Actions for ${phase.name}`} className="self-center" items={[{ label: "Rename…", icon: <Pencil className="h-3.5 w-3.5" />, onSelect: onRename }, "-", { label: "Delete phase…", icon: <Trash2 className="h-3.5 w-3.5" />, danger: true, onSelect: onDelete }]} />
      </div>
      {dates && <p className="-mt-2 mb-2 text-[11px] text-stone-400 sm:hidden">{dates}</p>}
      <div className="mb-3 rounded-xl border border-stone-100 bg-stone-50/60 px-3 py-2 text-sm dark:border-stone-800 dark:bg-stone-950/30" data-testid="phase-context">
        {editingObjective ? (
          <textarea autoFocus value={objective} onChange={(e) => setObjective(e.target.value)} onBlur={() => { setEditingObjective(false); if (objective !== phase.objective) onPatchPhase({ objective }); }} onKeyDown={(e) => { if (e.key === "Escape") { setObjective(phase.objective); setEditingObjective(false); } }} rows={3} className="w-full resize-y bg-transparent text-sm leading-relaxed text-stone-700 focus:outline-none dark:text-stone-200" aria-label={`${phase.name} objective`} placeholder="What must be true when this phase ends?" />
        ) : (
          <button type="button" onClick={() => setEditingObjective(true)} className="block w-full text-left leading-relaxed text-stone-600 hover:text-stone-900 dark:text-stone-300 dark:hover:text-stone-100" title="Click to edit the objective">
            {phase.objective ? phase.objective : <span className="text-stone-400">Add the objective — what must be true when this phase ends?</span>}
          </button>
        )}
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          {phase.questions.map((q) => (
            <span key={q.id} className={`group/q inline-flex max-w-full items-center gap-1 rounded-full px-2 py-0.5 text-[11px] ${q.status === "answered" ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300" : q.status === "abandoned" ? "bg-stone-100 text-stone-400 line-through dark:bg-stone-800" : "bg-indigo-500/10 text-indigo-700 dark:text-indigo-200"}`} title={`Research question · ${q.status.replace("_", " ")}`}>
              <HelpCircle className="h-3 w-3 shrink-0" aria-hidden="true" /><span className="truncate">{q.question}</span>
              <button type="button" onClick={() => onAttachQuestion(q.id, false)} aria-label={`Detach question ${q.question}`} className="opacity-0 group-hover/q:opacity-100"><X className="h-3 w-3" aria-hidden="true" /></button>
            </span>
          ))}
          {unattached.length > 0 && (
            <select value="" onChange={(e) => { if (e.target.value) onAttachQuestion(Number(e.target.value), true); }} className="max-w-[16rem] rounded-full border border-dashed border-stone-300 bg-transparent px-2 py-0.5 text-[11px] text-stone-400 focus:border-indigo-400 focus:outline-none dark:border-stone-700" aria-label={`Attach a research question to ${phase.name}`}>
              <option value="">+ research question</option>
              {unattached.map((q) => <option key={q.id} value={q.id}>{q.question.slice(0, 80)}</option>)}
            </select>
          )}
                  </div>
      </div>
      <div className="mb-1 flex items-center justify-between text-xs text-stone-400"><span>{done}/{phase.milestones.length} milestones</span><span>{phase.progress}%</span></div>
      <div className="mb-4 h-1.5 w-full overflow-hidden rounded-full bg-stone-100 dark:bg-stone-800">
        <div className="h-1.5 rounded-full transition-[width] duration-500" style={{ width: `${phase.progress}%`, background: accent, boxShadow: `0 0 10px ${accent}` }} />
      </div>
      <ul className="divide-y divide-stone-100 dark:divide-stone-800">
        {phase.milestones.map((m) => {
          const isOverdue = m.overdue && !m.completed_at;
          return (
            <li key={m.id} className="group py-2.5" draggable onDragStart={(e) => { e.dataTransfer.setData(MS_MIME, String(m.id)); e.dataTransfer.effectAllowed = "move"; e.stopPropagation(); }} title="Drag onto another phase to move this milestone" data-testid="milestone-row">
              <div className="flex items-center gap-3">
                <button type="button" aria-label="Toggle milestone" onClick={() => onToggleMilestone(m)} className={`relative flex h-5 w-5 shrink-0 items-center justify-center rounded-md border text-xs transition-all after:absolute after:-inset-2.5 after:content-[''] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 ${m.completed_at ? "border-indigo-500 bg-indigo-500 text-white shadow-[0_0_12px_rgb(99_102_241/.6)]" : "border-stone-300 bg-white text-transparent hover:border-indigo-400 dark:border-stone-600 dark:bg-stone-900 dark:hover:border-indigo-400"}`}><Check className="h-3 w-3" aria-hidden="true" /></button>
                <button type="button" onClick={() => onOpen(m.id)} className={`min-w-0 flex-1 truncate text-left text-sm hover:text-indigo-700 dark:hover:text-indigo-300 ${m.completed_at ? "text-stone-400 line-through" : "text-stone-800 dark:text-stone-200"}`} title="Open: notes, due date, tasks">{m.title}{m.notes ? <span className="ml-1.5 align-middle text-[10px] text-stone-400">notes</span> : null}</button>
                {conflictIds?.has(m.id) && !m.completed_at && <span className="shrink-0 rounded-md bg-amber-500/10 px-1.5 py-0.5 text-[11px] text-amber-800 dark:text-amber-200" title="Due on or before a milestone it waits for" data-testid="conflict-chip">due before its blocker</span>}
                {m.moves > 0 && m.slipped != null && m.slipped !== 0 && <span className={`shrink-0 rounded-md px-1.5 py-0.5 text-[11px] ${m.slipped > 0 ? "bg-stone-100 text-stone-500 dark:bg-stone-800 dark:text-stone-400" : "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"}`} title={`First planned for ${m.baseline} · moved ${m.moves} time${m.moves === 1 ? "" : "s"}`} data-testid="slip-chip">{m.slipped > 0 ? `slipped ${m.slipped} d` : `pulled in ${-m.slipped} d`}{m.moves > 1 ? ` · ${m.moves}×` : ""}</span>}
                {m.slack != null && m.slack >= 0 && m.slack <= TIGHT_DAYS && !m.completed_at && <span className="shrink-0 rounded-md bg-amber-500/10 px-1.5 py-0.5 text-[11px] text-amber-800 dark:text-amber-200" title={m.slack === 0 ? "Any slip pushes a milestone that waits for it" : `Can slip ${m.slack} day${m.slack === 1 ? "" : "s"} before it pushes a milestone that waits for it`} data-testid="slack-chip">{m.slack === 0 ? "no slack" : `${m.slack} d slack`}</span>}
                {chainIds?.has(m.id) && !m.completed_at && <Route className="h-3.5 w-3.5 shrink-0 text-indigo-500 dark:text-indigo-300" aria-label="On the critical chain" data-testid="chain-mark" />}
                {m.blocked && !m.completed_at && <span className="inline-flex max-w-[14rem] shrink-0 items-center gap-1 truncate rounded-md bg-amber-500/10 px-1.5 py-0.5 text-[11px] text-amber-800 dark:text-amber-200" title={`Waits for: ${(m.blocked_by ?? []).map((b) => b.title).join(", ")}`} data-testid="blocked-chip"><Lock className="h-3 w-3 shrink-0" aria-hidden="true" />waits for {(m.blocked_by ?? []).map((b) => b.title).join(", ")}</span>}
                {m.due_date && <span className={`shrink-0 rounded-md px-1.5 py-0.5 text-xs ${isOverdue ? "bg-red-500/10 font-medium text-red-600 dark:text-red-300" : "text-stone-400"}`}>{isOverdue ? "overdue · " : "due "}{m.due_date}</span>}
                <button type="button" onClick={() => { setTaskFor(taskFor === m.id ? null : m.id); setTaskDraft(""); }} className="shrink-0 text-[11px] text-stone-400 opacity-0 transition-opacity hover:text-indigo-600 group-hover:opacity-100 focus:opacity-100 dark:hover:text-indigo-300" aria-label={`Add a task to ${m.title}`}>+ task</button>
              </div>
              {(m.tasks.length > 0 || taskFor === m.id) && (
                <ul className="ml-2.5 mt-2 space-y-1.5 border-l border-stone-100 pl-4 dark:border-stone-800">
                  {m.tasks.map((t) => (
                    <li key={t.id} className="flex items-center gap-2.5 text-sm">
                      <button type="button" aria-label="Toggle task" onClick={() => onToggleTask(t)} className={`relative flex h-4 w-4 shrink-0 items-center justify-center rounded border text-[10px] transition-colors after:absolute after:-inset-2.5 after:content-[''] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 ${t.done ? "border-stone-400 bg-stone-400 text-white dark:border-stone-500 dark:bg-stone-500" : "border-stone-300 bg-white text-transparent hover:border-stone-400 dark:border-stone-600 dark:bg-stone-900"}`}><Check className="h-2.5 w-2.5" aria-hidden="true" /></button>
                      <span className={`min-w-0 flex-1 ${t.done ? "text-stone-400 line-through" : "text-stone-700 dark:text-stone-300"}`}>{t.title}</span>
                      {t.due_date && <span className="shrink-0 text-xs text-stone-400">due {t.due_date}</span>}
                    </li>
                  ))}
                  {taskFor === m.id && (
                    <li>
                      <form onSubmit={(e) => { e.preventDefault(); const t = taskDraft.trim(); if (t) { onAddTask(m.id, t); setTaskDraft(""); } }}>
                        <input autoFocus value={taskDraft} onChange={(e) => setTaskDraft(e.target.value)} onKeyDown={(e) => { if (e.key === "Escape") setTaskFor(null); }} placeholder="New task… Enter to add, Esc to close" className="w-full rounded-md border border-dashed border-stone-300 bg-transparent px-2 py-1 text-sm placeholder:text-stone-400 focus:border-indigo-400 focus:outline-none dark:border-stone-700 dark:text-stone-100" aria-label="New task title" />
                      </form>
                    </li>
                  )}
                </ul>
              )}
            </li>
          );
        })}
        <li className="pt-2.5">
          <form onSubmit={(e) => { e.preventDefault(); const t = draft.trim(); if (t) { onAddMilestone(t); setDraft(""); } }} className="flex items-center gap-3">
            <Plus className="h-4 w-4 shrink-0 text-stone-300 dark:text-stone-600" aria-hidden="true" />
            <input value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="New milestone… Enter to add" className="min-w-0 flex-1 bg-transparent py-0.5 text-sm placeholder:text-stone-400 focus:outline-none dark:text-stone-100" aria-label={`New milestone in ${phase.name}`} />
          </form>
        </li>
      </ul>
    </section>
  );
}

function OutlineEditor({ slug, empty, onSaved }: { slug: string; empty: boolean; onSaved: (s: Summary) => void }) {
  const current = useQuery({ queryKey: ["plan-outline", slug], queryFn: () => api<{ markdown: string }>(`/projects/${slug}/outline/`), staleTime: 0 });
  const [text, setText] = useState<string | null>(null);
  const original = current.data?.markdown ?? "";
  const value = text ?? (empty && !original ? STARTER : original);
  const debounced = useDebounced(value, 400);
  const dirty = value !== original;
  const preview = useQuery({
    queryKey: ["plan-outline-preview", slug, debounced],
    queryFn: async () => {
      const res = await fetch(`/api/v1/projects/${slug}/outline/`, { method: "POST", headers: { "Content-Type": "application/json", Accept: "application/json", "X-CSRFToken": (document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/)?.[1] ?? "") }, credentials: "same-origin", body: JSON.stringify({ markdown: debounced, dry_run: true }) });
      const body = (await res.json()) as Summary;
      if (!res.ok && !body.errors) throw new Error("preview failed");
      return body;
    },
    enabled: current.isSuccess && debounced.trim().length > 0,
  });
  const save = useMutation({
    mutationFn: () => api<Summary>(`/projects/${slug}/outline/`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ markdown: value }) }),
    onSuccess: (s) => onSaved(s),
  });
  const errors = preview.data?.errors ?? [];
  const canSave = dirty && errors.length === 0 && !save.isPending && preview.isSuccess;
  const ref = useRef<HTMLTextAreaElement>(null);
  const onKey = useCallback((e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if ((e.metaKey || e.ctrlKey) && e.key === "s") { e.preventDefault(); if (canSave) save.mutate(); }
    if (e.key === "Tab") {
      e.preventDefault();
      const el = e.currentTarget; const { selectionStart: s, selectionEnd: en } = el;
      const next = el.value.slice(0, s) + "  " + el.value.slice(en);
      setText(next); requestAnimationFrame(() => { el.selectionStart = el.selectionEnd = s + 2; });
    }
  }, [canSave, save]);
  const lines = useMemo(() => value.split("\n").length, [value]);
  return (
    <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_20rem]" data-testid="outline-editor">
      <div className={`${panel} hairline-gradient rise overflow-hidden`}>
        <div className="flex items-center gap-2 border-b border-stone-100 px-3 py-2 text-xs text-stone-400 dark:border-stone-800">
          <FileText className="h-3.5 w-3.5" aria-hidden="true" /><span>outline.md</span><span>· {lines} lines</span>
          {dirty && <button type="button" onClick={() => setText(null)} className="ml-auto inline-flex items-center gap-1 hover:text-stone-600 dark:hover:text-stone-200"><X className="h-3 w-3" aria-hidden="true" />reset</button>}
        </div>
        {current.isLoading ? <div className="p-4"><Skeleton className="h-40 w-full" /></div> : (
          <textarea ref={ref} value={value} onChange={(e) => setText(e.target.value)} onKeyDown={onKey} spellCheck={false} rows={Math.max(14, lines + 2)} className="w-full resize-y bg-transparent px-4 py-3 font-mono text-[13px] leading-6 text-stone-800 focus:outline-none dark:text-stone-100" aria-label="Plan outline" />
        )}
      </div>
      <aside className="space-y-3">
        <div className={`${panel} rise p-4`} style={{ ["--i" as string]: 1 }}>
          <p className="mb-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-stone-400">This save would</p>
          {preview.isFetching && <p className="flex items-center gap-1.5 text-xs text-stone-400"><Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" />checking…</p>}
          {!preview.isFetching && errors.length > 0 && (
            <ul className="space-y-1 text-xs text-red-600 dark:text-red-300">
              {errors.map((e, i) => <li key={i} className="flex items-start gap-1.5"><AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" aria-hidden="true" /><span><span className="font-mono">line {e.line}</span> · {e.message}</span></li>)}
            </ul>
          )}
          {!preview.isFetching && preview.data && errors.length === 0 && (
            <div className="text-xs text-stone-600 dark:text-stone-300">
              <p className="mb-2 tabular-nums">{preview.data.phases} phases · {preview.data.milestones} milestones · {preview.data.tasks} tasks</p>
              {!dirty && <p className="text-stone-400">No changes yet — edit the outline on the left.</p>}
              {(["created", "renamed", "deleted"] as const).map((k) => preview.data![k].length > 0 && (
                <div key={k} className="mb-2">
                  <p className={`font-medium ${k === "deleted" ? "text-red-600 dark:text-red-300" : k === "created" ? "text-emerald-600 dark:text-emerald-300" : "text-indigo-600 dark:text-indigo-300"}`}>{k === "created" ? "+ create" : k === "renamed" ? "~ rename" : "− delete"} {preview.data![k].length}</p>
                  <ul className="mt-0.5 space-y-0.5 text-stone-500 dark:text-stone-400">{preview.data![k].slice(0, 8).map((s) => <li key={s} className="truncate" title={s}>{s}</li>)}{preview.data![k].length > 8 && <li>… and {preview.data![k].length - 8} more</li>}</ul>
                </div>
              ))}
            </div>
          )}
          <button type="button" disabled={!canSave} onClick={() => save.mutate()} className="mt-3 inline-flex w-full items-center justify-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-40" title="⌘S / Ctrl+S">
            {save.isPending ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : <Save className="h-4 w-4" aria-hidden="true" />}Save plan
          </button>
          {save.isError && <p className="mt-2 text-xs text-red-600 dark:text-red-300">Could not save — fix the errors above and try again.</p>}
        </div>
        <div className={`${panel} rise p-4 text-xs leading-relaxed text-stone-500 dark:text-stone-400`} style={{ ["--i" as string]: 2 }}>
          <p className="mb-1.5 text-[10px] font-semibold uppercase tracking-[0.14em] text-stone-400">Syntax</p>
          <p><code className="text-stone-700 dark:text-stone-200"># Phase name  [in_progress]  (2026-09-01 → 2026-10-15)</code></p>
          <p><code className="text-stone-700 dark:text-stone-200">&gt; objective, one line or many</code></p>
          <p><code className="text-stone-700 dark:text-stone-200">- [ ] Milestone  (due 2026-09-20)</code></p>
          <p><code className="text-stone-700 dark:text-stone-200">&nbsp;&nbsp;- [x] indented task, done</code></p>
          <p className="mt-2">Statuses: not_started · in_progress · blocked · done. Keep the <code>{"{#id}"}</code> tokens to rename safely; delete a line to delete the item. Tab indents, ⌘S saves.</p>
        </div>
      </aside>
    </div>
  );
}
