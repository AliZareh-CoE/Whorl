import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, CalendarClock, Check, Command, FileText, FolderPlus, Loader2, Plug, Sparkles, Wand2 } from "lucide-react";
import { api } from "../api";
import { toggleCalm, useCalm } from "../calm";
import { Skeleton, SkeletonCard, SkeletonLines } from "../../components/Skeleton";
import { ErrorState } from "../../components/ErrorState";
import { Constellation } from "../../components/Constellation";

type Attention = {
  empty: boolean;
  overdue: { title: string; due_date: string; project: string; url: string }[];
  deadlines: { title: string; deadline: string; days_to_deadline: number; project: string; url: string }[];
  inbox: { id: number; text: string }[];
};

type WeekItem = { kind: "milestone" | "task"; id: number; title: string; due_date: string; days: number; project: string; project_name: string; color: string; phase: string };
type Dash = {
  stats: Record<string, number>;
  inbox_count: number;
  todos_open: number;
  week: { today: string; week_ends: string; overdue: WeekItem[]; due_this_week: WeekItem[] };
  heatmap: { date: string; count: number; level: number }[][];
  attention: Attention;
  active: {
    name: string; slug: string; url: string; color: string;
    phase: string | null; done: number; total: number; percent: number;
    health: { state: string; label: string; forecast_end: string | null } | null;
  }[];
  milestones: { title: string; project: string; due_date: string | null; overdue: boolean; url: string }[];
  deadlines: { title: string; deadline: string | null; url: string }[];
};

// Observatory (2026-09-06): glass panels, display numerals, orbit-ring progress, a living
// constellation of the active projects behind the greeting. Tokens do the colour work; the
// classes below only shape the panels.
const panel = "rounded-2xl border border-stone-200 bg-white p-5 dark:border-stone-800 dark:bg-stone-900";
const tile = "rounded-2xl border border-stone-200 bg-white px-5 py-4 dark:border-stone-800 dark:bg-stone-900";
const h2 = "mb-3 text-[11px] font-semibold uppercase tracking-[0.14em] text-stone-400 dark:text-stone-500";
const row = "-mx-2 flex items-baseline gap-2 rounded-lg px-2 py-1.5 transition-colors hover:bg-stone-50 hover:text-indigo-700 dark:hover:bg-stone-800 dark:hover:text-indigo-300";

function greeting(): string {
  const h = new Date().getHours();
  if (h < 5) return "Late night";
  if (h < 12) return "Good morning";
  if (h < 18) return "Good afternoon";
  return "Good evening";
}

function openCommandBar() {
  document.dispatchEvent(new KeyboardEvent("keydown", { key: "k", metaKey: true, bubbles: true }));
}

/** Inline triage on an attention inbox row (#157): file to a project or dismiss. */
function TriageControls({ id, projects }: { id: number; projects: { slug: string; name: string }[] }) {
  const queryClient = useQueryClient();
  const [slug, setSlug] = useState(projects[0]?.slug ?? "");
  const triage = useMutation({
    mutationFn: (body: { processed: boolean; project?: string }) =>
      api(`/quick-capture/${id}/`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["dashboard"] }),
  });
  return (
    <span className="flex shrink-0 items-center gap-1">
      <select
        value={slug}
        onChange={(e) => setSlug(e.target.value)}
        className="rounded-md border border-stone-200 px-1 py-0.5 text-xs text-stone-600 dark:border-stone-700 dark:bg-stone-800 dark:text-stone-300"
      >
        {projects.map((p) => (
          <option key={p.slug} value={p.slug}>{p.name.slice(0, 22)}</option>
        ))}
      </select>
      <button
        type="button"
        disabled={triage.isPending || !slug}
        onClick={() => triage.mutate({ processed: true, project: slug })}
        className="rounded-md px-1.5 py-0.5 text-xs text-indigo-600 transition-colors hover:bg-indigo-50 active:opacity-80 disabled:opacity-50 dark:text-indigo-400 dark:hover:bg-indigo-500/10"
      >
        file
      </button>
      <button
        type="button"
        title="Dismiss"
        disabled={triage.isPending}
        onClick={() => triage.mutate({ processed: true })}
        className="rounded-md px-1.5 py-0.5 text-xs text-stone-400 transition-colors hover:bg-stone-100 hover:text-stone-600 active:opacity-80 disabled:opacity-50 dark:text-stone-400 dark:hover:bg-stone-800 dark:hover:text-stone-300"
      >
        ✕
      </button>
    </span>
  );
}

/** Orbit ring: an SVG progress ring in the project's accent colour with a soft glow. */
function OrbitRing({ percent, color, size = 44 }: { percent: number; color: string; size?: number }) {
  const r = (size - 6) / 2;
  const c = 2 * Math.PI * r;
  const off = c * (1 - Math.max(0, Math.min(100, percent)) / 100);
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="orbit-ring shrink-0" aria-hidden="true">
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="currentColor" strokeWidth="3" className="text-stone-100 dark:text-stone-800" />
      <circle
        cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth="3" strokeLinecap="round"
        strokeDasharray={c} strokeDashoffset={off} transform={`rotate(-90 ${size / 2} ${size / 2})`}
        style={{ transition: "stroke-dashoffset 900ms cubic-bezier(.2,.7,.2,1)" }}
      />
    </svg>
  );
}

function Stat({ value, label, i, to }: { value: number; label: string; i: number; to?: string }) {
  const inner = (
    <>
      <p className="font-display text-gradient text-4xl font-bold tabular-nums leading-none">{value}</p>
      <p className="mt-2 text-xs text-stone-400 dark:text-stone-400">{label}</p>
    </>
  );
  return (
    <div className={`${tile} rise`} style={{ ["--i" as string]: i }}>
      {to ? <Link to={to} className="block hover:opacity-90">{inner}</Link> : inner}
    </div>
  );
}

export default function Dashboard() {
  // Calm mode (#274) lives in ../calm so the ⌘K palette verb (#277) can flip it and this
  // page updates live (#278) — no remount, no settings page.
  const calm = useCalm();

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => api<Dash>("/dashboard/"),
  });
  const demo = useQuery({ queryKey: ["demo-status"], queryFn: () => api<{ projects: number }>("/demo/") });
  const qcAll = useQueryClient();
  const loadDemo = useMutation({ mutationFn: () => api<{ project: string }>("/demo/", { method: "POST" }), onSuccess: () => { void qcAll.invalidateQueries(); } });

  if (isLoading)
    return (
      <div role="status" aria-label="Loading" className="space-y-6">
        <Skeleton className="h-56 w-full rounded-2xl" />
        <SkeletonLines lines={3} />
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
        <div className="grid gap-4 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      </div>
    );
  if (error || !data) return <ErrorState message="Couldn't load the dashboard." onRetry={() => refetch()} />;

  const attention = data.attention;
  const firstRun = demo.data?.projects === 0;
  // first run on the desktop: offer to fetch the TeX bundle now rather than behind the first compile (#372)
  type Warm = { state: string; warm: boolean; size_mb: number };
  const warmState = useQuery({ queryKey: ["latex-warm"], queryFn: () => api<Warm>("/diagnostics/warm-latex/"), enabled: firstRun, refetchInterval: (q) => (q.state.data?.state === "running" ? 3000 : false) });
  const warmUp = useMutation({ mutationFn: () => api<Warm>("/diagnostics/warm-latex/", { method: "POST" }), onSuccess: () => qcAll.invalidateQueries({ queryKey: ["latex-warm"] }) });
  const needs = attention.overdue.length + attention.deadlines.length + attention.inbox.length;
  const anchors = data.active.map((p) => ({ label: p.name, color: p.color, weight: 0.35 + p.percent / 150 }));

  return (
    <div>
      {/* Hero: the constellation of your active projects, the greeting, and the spotlight. */}
      <section
        className="hairline-gradient rise relative mb-5 overflow-hidden rounded-3xl border border-stone-200 bg-white dark:border-transparent dark:bg-stone-900"
        style={{ ["--i" as string]: 0 }}
      >
        <div className="absolute inset-0 hidden dark:block">
          <Constellation anchors={anchors} density={0.9} />
        </div>
        <div className="pointer-events-none absolute inset-0 hidden bg-gradient-to-r from-stone-950/70 via-stone-950/20 to-transparent dark:block" />
        <div className="relative flex min-h-[15rem] flex-col justify-between p-7">
          <div className="flex items-start justify-between gap-4">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-stone-400 dark:text-stone-400">
              {new Date().toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" })}
            </p>
            <button
              type="button"
              onClick={toggleCalm}
              aria-pressed={calm}
              title={calm ? "Show the monthly stats" : "Hide the monthly stats — show only what needs you"}
              className="shrink-0 rounded-full border border-stone-200 px-3 py-1 text-xs text-stone-500 transition-colors hover:border-stone-300 hover:text-stone-700 dark:border-stone-700 dark:bg-stone-950/40 dark:text-stone-300 dark:hover:text-stone-100"
            >
              {calm ? "Full view" : "Calm mode"}
            </button>
          </div>
          <div className="max-w-2xl">
            <h1 className="font-display text-4xl font-bold leading-[1.05] tracking-tight text-stone-900 dark:text-stone-100 sm:text-5xl">
              {greeting()}.
              <br />
              <span className="text-gradient">
                {needs === 0 ? "All clear, everywhere." : `${needs} thing${needs === 1 ? "" : "s"} need${needs === 1 ? "s" : ""} you.`}
              </span>
            </h1>
            <p className="mt-3 text-sm text-stone-500 dark:text-stone-300">
              {data.active.length} active project{data.active.length === 1 ? "" : "s"} · {data.milestones.length} upcoming milestone{data.milestones.length === 1 ? "" : "s"} · {data.inbox_count} in the inbox
            </p>
            <button
              type="button"
              onClick={openCommandBar}
              className="glow-accent mt-5 inline-flex items-center gap-3 rounded-full border border-indigo-200 bg-white/80 py-2 pl-4 pr-2 text-sm text-stone-600 transition-all hover:-translate-y-0.5 dark:border-indigo-500/40 dark:bg-stone-950/60 dark:text-stone-200"
            >
              <Sparkles className="h-4 w-4 text-indigo-500" aria-hidden="true" />
              <span>Jump anywhere, capture an idea, complete a milestone…</span>
              <kbd className="ml-2 inline-flex items-center gap-1 rounded-full border border-stone-200 bg-stone-50 px-2 py-0.5 font-sans text-[11px] text-stone-500 dark:border-stone-700 dark:bg-stone-900 dark:text-stone-300">
                <Command className="h-3 w-3" aria-hidden="true" />K
              </kbd>
            </button>
          </div>
        </div>
      </section>

      {firstRun && (
        <section className={`${panel} rise mb-5 border-indigo-200 dark:border-indigo-500/40`} style={{ ["--i" as string]: 1 }} data-testid="welcome">
          <h2 className={h2}>Welcome — Atlas is empty</h2>
          <p className="mb-4 max-w-2xl text-sm text-stone-600 dark:text-stone-300">Everything here lives inside a project: its plan, papers, notes, manuscripts and decisions. Start with one of these.</p>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
            <Link to="/projects/new" className="group rounded-xl border border-stone-200 p-4 transition-colors hover:border-indigo-400 dark:border-stone-700"><FolderPlus className="mb-2 h-5 w-5 text-indigo-500" aria-hidden="true" /><p className="font-medium">Create your first project</p><p className="mt-1 text-xs text-stone-500">Pick a scaffold — empirical study, review paper, software — or start blank.</p></Link>
            <button type="button" onClick={() => loadDemo.mutate()} disabled={loadDemo.isPending} className="rounded-xl border border-stone-200 p-4 text-left transition-colors hover:border-indigo-400 disabled:opacity-60 dark:border-stone-700" data-testid="load-demo">{loadDemo.isPending ? <Loader2 className="mb-2 h-5 w-5 animate-spin text-indigo-500" aria-hidden="true" /> : <Wand2 className="mb-2 h-5 w-5 text-indigo-500" aria-hidden="true" />}<p className="font-medium">{loadDemo.isPending ? "Loading the demo…" : "Load the demo project"}</p><p className="mt-1 text-xs text-stone-500">A realistic attention-and-memory study with a plan, 20+ papers, notes, a manuscript and a hypothesis ledger — explore every page, delete it later.</p></button>
            <Link to="/connect" className="group rounded-xl border border-stone-200 p-4 transition-colors hover:border-indigo-400 dark:border-stone-700"><Plug className="mb-2 h-5 w-5 text-indigo-500" aria-hidden="true" /><p className="font-medium">Connect Claude Code</p><p className="mt-1 text-xs text-stone-500">One command registers Atlas as an MCP server; four skills teach Claude the workflows.</p></Link>
            {warmState.data && !warmState.data.warm && (
              <button type="button" onClick={() => warmUp.mutate()} disabled={warmUp.isPending || warmState.data.state === "running"} className="rounded-xl border border-stone-200 p-4 text-left transition-colors hover:border-indigo-400 disabled:opacity-60 dark:border-stone-700" data-testid="warm-latex-card">
                {warmState.data.state === "running" ? <Loader2 className="mb-2 h-5 w-5 animate-spin text-indigo-500" aria-hidden="true" /> : <FileText className="mb-2 h-5 w-5 text-indigo-500" aria-hidden="true" />}
                <p className="font-medium">{warmState.data.state === "running" ? "Preparing the LaTeX engine…" : "Prepare the LaTeX engine"}</p>
                <p className="mt-1 text-xs text-stone-500">{warmState.data.state === "running" ? "Downloading the TeX packages a paper needs. Keep working; this runs in the background." : "Downloads the TeX packages once (a few hundred MB) so your first compile takes seconds, not minutes."}</p>
              </button>
            )}
          </div>
        </section>
      )}

      {/* the answer first ([REV] cycle 145 → SPA #156): what needs me today */}
      {attention.empty ? (
        <div className="rise mb-5 rounded-2xl border border-dashed border-stone-300 bg-white px-5 py-4 text-sm text-stone-500 dark:border-stone-700 dark:bg-stone-900 dark:text-stone-300" style={{ ["--i" as string]: 1 }}>
          All clear — nothing overdue, no deadlines inside two weeks, inbox triaged.
        </div>
      ) : (
        <section className={`${panel} rise mb-5 border-l-2 border-l-red-400 dark:border-l-red-400/80 dark:shadow-[inset_12px_0_28px_-24px_rgba(248,113,113,0.9)]`} style={{ ["--i" as string]: 1 }}>
          <h2 className={`${h2} mb-2.5`}>Needs attention</h2>
          <ul className="space-y-1.5 text-sm">
            {attention.overdue.map((m) => (
              <li key={`o${m.url}${m.title}`} className="flex items-baseline gap-2">
                <span className="shrink-0 rounded-full bg-red-500/10 px-2 py-0.5 text-[11px] font-medium text-red-600 dark:text-red-300">overdue</span>
                <a href={m.url} className="min-w-0 flex-1 truncate hover:underline dark:text-stone-100">{m.title}</a>
                <span className="shrink-0 text-xs text-stone-400 dark:text-stone-400">{m.project} · due {m.due_date}</span>
              </li>
            ))}
            {attention.deadlines.map((d) => (
              <li key={`d${d.url}${d.title}`} className="flex items-baseline gap-2">
                <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium ${d.days_to_deadline < 7 ? "bg-red-500/10 text-red-600 dark:text-red-300" : "bg-amber-500/10 text-amber-600 dark:text-amber-300"}`}>deadline</span>
                <a href={d.url} className="min-w-0 flex-1 truncate hover:underline dark:text-stone-100">{d.title}</a>
                <span className="shrink-0 text-xs text-stone-400 dark:text-stone-400">
                  {d.project} · {d.days_to_deadline < 0 ? "passed" : `${d.days_to_deadline} day${d.days_to_deadline === 1 ? "" : "s"}`} ({d.deadline})
                </span>
              </li>
            ))}
            {attention.inbox.map((q) => (
              <li key={`q${q.id}`} className="flex items-baseline gap-2">
                <span className="shrink-0 rounded-full bg-indigo-500/10 px-2 py-0.5 text-[11px] font-medium text-indigo-600 dark:text-indigo-300">inbox</span>
                <span className="min-w-0 flex-1 truncate text-stone-600 dark:text-stone-300">{q.text}</span>
                <TriageControls id={q.id} projects={data.active} />
                <Link to="/inbox" className="shrink-0 text-xs text-stone-400 hover:underline dark:text-stone-400" title="Open the full inbox">all →</Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      <WeekEverywhere week={data.week} />

      {!calm && (
        <div className="mb-5 grid grid-cols-2 gap-4 sm:grid-cols-5">
          <Stat value={data.todos_open} label="on today's list" i={2} to="/today" />
          <Stat value={data.stats.papers_read} label="papers read this month" i={3} />
          <Stat value={data.stats.notes_written} label="notes written this month" i={4} />
          <Stat value={data.stats.milestones_done} label="milestones completed" i={5} />
          <Stat value={data.inbox_count} label="inbox items to triage" i={6} to="/inbox" />
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-3">
        <section className={`${panel} rise`} style={{ ["--i" as string]: 6 }}>
          <h2 className={h2}>Active projects</h2>
          <div className="space-y-3">
            {data.active.map((p) => (
              <Link key={p.slug} to={`/projects/${p.slug}`} className="group -mx-2 flex items-center gap-3 rounded-xl px-2 py-1.5 transition-colors hover:bg-stone-50 dark:hover:bg-stone-800">
                <OrbitRing percent={p.percent} color={p.color} />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium group-hover:text-indigo-700 dark:text-stone-100 dark:group-hover:text-indigo-300">{p.name}</span>
                  <span className="block truncate text-xs text-stone-400 dark:text-stone-400">
                    {p.phase ? `${p.phase} · ` : ""}{p.done}/{p.total} milestones
                  </span>
                  {p.health && p.health.state !== "empty" && (
                    <span className={`mt-0.5 inline-block truncate rounded-full px-1.5 py-px text-[10px] ${HEALTH[p.health.state] ?? HEALTH.upcoming}`} title={p.health.forecast_end ? `Forecast finish ${p.health.forecast_end}` : undefined} data-testid="project-health">{p.health.label}</span>
                  )}
                </span>
                <span className="font-display shrink-0 text-sm font-semibold tabular-nums text-stone-500 dark:text-stone-300">{p.percent}%</span>
              </Link>
            ))}
            {data.active.length === 0 && (
              <p className="text-sm text-stone-400 dark:text-stone-400">
                No active projects. <Link to="/projects" className="text-indigo-600 hover:text-indigo-700 dark:text-indigo-400 dark:hover:text-indigo-300">Start one →</Link>
              </p>
            )}
          </div>
        </section>

        <section className={`${panel} rise`} style={{ ["--i" as string]: 7 }}>
          <div className="flex items-baseline justify-between"><h2 className={h2}>Deadlines</h2><CalendarSubscribe /></div>
          <ul className="space-y-0.5 text-sm">
            {data.deadlines.map((d) => (
              <li key={d.url + d.title}>
                <a href={d.url} className={row}>
                  <span aria-hidden="true" className="text-stone-300 dark:text-stone-500">✍</span>
                  <span className="min-w-0 flex-1 truncate font-medium dark:text-stone-100">{d.title}</span>
                  <span className="shrink-0 text-xs tabular-nums text-stone-400 dark:text-stone-400">{d.deadline}</span>
                </a>
              </li>
            ))}
            {data.deadlines.length === 0 && (
              <li className="text-sm text-stone-400 dark:text-stone-400">
                Manuscript deadlines show up here. <Link to="/writing" className="text-indigo-600 hover:text-indigo-700 dark:text-indigo-400 dark:hover:text-indigo-300">Open Writing →</Link>
              </li>
            )}
          </ul>
        </section>

        <section className={`${panel} rise`} style={{ ["--i" as string]: 8 }}>
          <h2 className={h2}>Upcoming milestones</h2>
          <ul className="space-y-0.5 text-sm">
            {data.milestones.map((m) => (
              <li key={m.url + m.title}>
                <a href={m.url} className={row}>
                  <span aria-hidden="true" className={`h-1.5 w-1.5 shrink-0 self-center rounded-full ${m.overdue ? "bg-red-400 shadow-[0_0_8px_rgba(248,113,113,0.8)]" : "bg-indigo-400 shadow-[0_0_8px_rgba(139,124,255,0.7)]"}`} />
                  <span className="min-w-0 flex-1 truncate dark:text-stone-100">{m.title}</span>
                  <span className={`shrink-0 text-xs tabular-nums ${m.overdue ? "font-medium text-red-600 dark:text-red-300" : "text-stone-400 dark:text-stone-400"}`}>
                    {m.due_date}{m.overdue ? " · overdue" : ""}
                  </span>
                </a>
              </li>
            ))}
            {data.milestones.length === 0 && (
              <li className="text-sm text-stone-400 dark:text-stone-400">Nothing scheduled — add milestones inside a project plan.</li>
            )}
          </ul>
        </section>
      </div>

      {!calm && <Heatmap weeks={data.heatmap} />}
    </div>
  );
}

const HEALTH: Record<string, string> = { behind: "bg-amber-500/15 text-amber-700 dark:text-amber-300", overdue: "bg-red-500/15 text-red-700 dark:text-red-300", blocked: "bg-red-500/15 text-red-700 dark:text-red-300", ahead: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300", done: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300", on_track: "bg-indigo-500/15 text-indigo-700 dark:text-indigo-200", upcoming: "bg-stone-100 text-stone-500 dark:bg-stone-800 dark:text-stone-300" };

function when(days: number): string { if (days < 0) return `${-days} d late`; if (days === 0) return "today"; if (days === 1) return "tomorrow"; return `in ${days} d`; }

/** Dashboard v2: this week across every active project, completable in place. */
function WeekEverywhere({ week }: { week: Dash["week"] }) {
  const queryClient = useQueryClient();
  const complete = useMutation({
    mutationFn: (i: WeekItem) => i.kind === "milestone"
      ? api(`/milestones/${i.id}/`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ completed_at: new Date().toISOString() }) })
      : api(`/tasks/${i.id}/`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ done: true }) }),
    onMutate: (i) => { queryClient.setQueryData<Dash>(["dashboard"], (old) => old ? { ...old, week: { ...old.week, overdue: old.week.overdue.filter((x) => !(x.kind === i.kind && x.id === i.id)), due_this_week: old.week.due_this_week.filter((x) => !(x.kind === i.kind && x.id === i.id)) } } : old); },
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["dashboard"] }),
  });
  const total = week.overdue.length + week.due_this_week.length;
  const groups = [
    { key: "overdue", label: "Overdue", icon: AlertTriangle, items: week.overdue, tone: "text-red-600 dark:text-red-300" },
    { key: "week", label: `Due by ${new Date(`${week.week_ends}T00:00:00`).toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" })}`, icon: CalendarClock, items: week.due_this_week, tone: "text-indigo-600 dark:text-indigo-300" },
  ].filter((g) => g.items.length > 0);
  return (
    <section className={`${panel} rise mb-5`} style={{ ["--i" as string]: 1.5 }} data-testid="week-everywhere">
      <div className="mb-2 flex items-baseline justify-between"><h2 className={`${h2} mb-0`}>This week, everywhere</h2><span className="text-[11px] text-stone-400">{total === 0 ? "nothing due in the next seven days" : `${week.overdue.length ? `${week.overdue.length} overdue · ` : ""}${week.due_this_week.length} due`}</span></div>
      {total === 0 ? <p className="text-sm text-stone-400">Clear week across every project — plan the next milestones or read.</p> : (
        <div className={`grid gap-4 ${groups.length > 1 ? "md:grid-cols-2" : ""}`}>
          {groups.map((g) => (
            <div key={g.key}>
              <p className={`mb-1 flex items-center gap-1 text-[11px] font-medium ${g.tone}`}><g.icon className="h-3 w-3" aria-hidden="true" />{g.label}</p>
              <ul className="space-y-1">
                {g.items.slice(0, 8).map((i) => (
                  <li key={`${i.kind}-${i.id}`} className="flex items-center gap-2 text-sm">
                    <button type="button" onClick={() => complete.mutate(i)} aria-label={`Complete ${i.title}`} className={`flex h-4 w-4 shrink-0 items-center justify-center rounded border text-transparent transition-colors hover:border-indigo-400 hover:text-indigo-500 ${i.kind === "milestone" ? "rounded-md border-stone-300 dark:border-stone-600" : "border-stone-200 dark:border-stone-700"}`}><Check className="h-2.5 w-2.5" aria-hidden="true" /></button>
                    <span className="inline-block h-2 w-2 shrink-0 rounded-full" style={{ background: i.color }} aria-hidden="true" />
                    <Link to={`/projects/${i.project}/plan`} className="min-w-0 flex-1 truncate text-stone-800 hover:text-indigo-700 dark:text-stone-100 dark:hover:text-indigo-300" title={`${i.project_name} · ${i.phase}`}>{i.title}{i.kind === "task" && <span className="ml-1 text-[10px] text-stone-400">task</span>}</Link>
                    <span className="hidden shrink-0 truncate text-[11px] text-stone-400 sm:inline">{i.project_name}</span>
                    <span className={`shrink-0 text-[11px] tabular-nums ${i.days < 0 ? "font-medium text-red-600 dark:text-red-300" : "text-stone-400"}`}>{when(i.days)}</span>
                  </li>
                ))}
                {g.items.length > 8 && <li className="text-[11px] text-stone-400">… {g.items.length - 8} more</li>}
              </ul>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}

/** GitHub-style activity heatmap over the last 26 weeks (created/updated rows across models). */
function Heatmap({ weeks }: { weeks: Dash["heatmap"] }) {
  const LEVEL = ["bg-stone-100 dark:bg-stone-800", "bg-indigo-500/25", "bg-indigo-500/45", "bg-indigo-500/70", "bg-indigo-400"];
  const total = weeks.flat().reduce((n, c) => n + c.count, 0);
  const months: { label: string; col: number }[] = [];
  weeks.forEach((w, i) => { const d = new Date(`${w[0].date}T00:00:00`); if (d.getDate() <= 7) months.push({ label: d.toLocaleDateString(undefined, { month: "short" }), col: i }); });
  return (
    <section className={`${panel} rise mt-5`} style={{ ["--i" as string]: 9 }} data-testid="heatmap">
      <div className="mb-2 flex items-baseline justify-between"><h2 className={`${h2} mb-0`}>Activity · 26 weeks</h2><span className="text-[11px] text-stone-400">{total} changes across every project</span></div>
      <div className="overflow-x-auto">
        <div className="relative" style={{ width: weeks.length * 14, minWidth: "100%" }}>
          <div className="mb-1 h-3 text-[9px] uppercase tracking-wider text-stone-400">{months.map((m) => <span key={`${m.label}${m.col}`} className="absolute" style={{ left: m.col * 14 }}>{m.label}</span>)}</div>
          <div className="mt-3 flex gap-[3px]">
            {weeks.map((w, i) => (
              <div key={i} className="flex flex-col gap-[3px]">
                {w.map((c) => <span key={c.date} className={`block h-[11px] w-[11px] rounded-[2px] ${LEVEL[c.level] ?? LEVEL[0]}`} title={`${c.date} · ${c.count} change${c.count === 1 ? "" : "s"}`} />)}
              </div>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

/** Backlog #9: one click copies the .ics subscription URL (it carries the API key). */
function CalendarSubscribe() {
  const [state, setState] = useState<"idle" | "copied" | "error">("idle");
  const copy = async () => {
    try {
      const c = await api<{ api_url: string; api_key: string; api_key_configured: boolean }>("/connect/");
      if (!c.api_key_configured) { setState("error"); return; }
      await navigator.clipboard.writeText(`${c.api_url}/api/v1/calendar.ics?key=${encodeURIComponent(c.api_key)}`);
      setState("copied"); window.setTimeout(() => setState("idle"), 3000);
    } catch { setState("error"); }
  };
  return (
    <button type="button" onClick={() => void copy()} className="mb-3 inline-flex items-center gap-1 text-[11px] text-stone-400 hover:text-indigo-600 dark:hover:text-indigo-300" title="Copy a calendar subscription URL (milestones + manuscript deadlines). Paste it into Google Calendar / Outlook / Apple Calendar under 'subscribe by URL'. The URL contains your API key." data-testid="calendar-subscribe">
      <CalendarClock className="h-3 w-3" aria-hidden="true" />{state === "copied" ? "URL copied — subscribe in your calendar" : state === "error" ? "no API key configured" : "subscribe (.ics)"}
    </button>
  );
}
