import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { AlertTriangle, BookOpen, CalendarClock, Check, ClipboardList, Command, FileText, FolderPlus, ListChecks, Loader2, Plug, Radar, Rss, Sparkles, Trophy, Wand2 } from "lucide-react";
import { confirmDialog, errorDialog, noticeDialog } from "../../components/Dialog";
import { api } from "../api";
import { showUndo } from "../../components/UndoToast";
import { dueState, formatDue } from "../dueTime";
import { toggleCalm, useCalm } from "../calm";
import { Skeleton, SkeletonCard, SkeletonLines } from "../../components/Skeleton";
import { ErrorState } from "../../components/ErrorState";
import { Constellation } from "../../components/Constellation";

type PulseData = { weeks: number[]; total: number; quiet_weeks: number; last_activity: string | null; days_since: number | null };

type Attention = {
  empty: boolean;
  overdue: { title: string; due_date: string; project: string; url: string }[];
  deadlines: { title: string; deadline: string; days_to_deadline: number; project: string; url: string }[];
  inbox: { id: number; text: string }[];
  // #475: papers that have waited on a venue longer than it usually takes
  waiting?: { id: number; title: string; project: string; venue: string; status: string; waited: number; after_days: number; basis: string; url: string }[];
  backup?: { last: { at: string; days_ago: number } | null; stale: boolean; has_data: boolean; stale_after_days: number };
  // #489: active projects whose pulse has been flat for three weeks or more
  quiet?: { name: string; slug: string; url: string; quiet_weeks: number; last_activity: string | null; days_since: number | null }[];
};

type WeekItem = { kind: "milestone" | "task"; id: number; title: string; due_date: string; days: number; project: string; project_name: string; color: string; phase: string };
type Dash = {
  stats: Record<string, number>;
  inbox_count: number;
  todos_open: number;
  todos: { id: number; text: string; due_at?: string | null; all_day?: boolean; project: string | null }[];
  week: { today: string; week_ends: string; overdue: WeekItem[]; due_this_week: WeekItem[] };
  heatmap: { date: string; count: number; level: number }[][];
  attention: Attention;
  active: {
    name: string; slug: string; url: string; color: string;
    phase: string | null; done: number; total: number; percent: number;
    health: { state: string; label: string; forecast_end: string | null } | null;
    pulse?: PulseData | null;
  }[];
  milestones: { title: string; project: string; due_date: string | null; overdue: boolean; url: string }[];
  deadlines: { title: string; deadline: string | null; url: string }[];
  writing?: { live: number; rows: { id: number; title: string; status: string; deadline: string | null; days: number | null; target_venue: string; project: string; project_slug: string; over: string[]; clock: { days: number; label: string; nudge?: { due: boolean; waited: number; after_days: number; basis: string } } | null; readiness: { ready: boolean; fails: number; warns: number; summary: string } | null }[] };
  trends?: { months: string[]; series: Record<string, number[]>; previous: Record<string, number> };
  // #533: the Library's watches at a glance — feeds and the citation watch, from the stored rows
  watches?: {
    feeds: { new: number; followed: number; errors: number; url: string; rows: { id: number; title: string; feed: string; feed_id: number; published_on: string | null; link: string }[] };
    citations: { new: number; url: string; rows: { id: number; title: string; first_author: string; year: number | null; published_on: string | null; venue: string; cites: { id: number; bibtex_key: string }[] }[] };
  };
  reading?: { to_read: number; high_priority: number; projects: number; next: { id: number; title: string; first_author: string; year: number | null; priority: string; project: string; project_slug: string; waiting_days: number }[] };
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
function TriageControls({ id, text, projects }: { id: number; text?: string; projects: { slug: string; name: string }[] }) {
  const queryClient = useQueryClient();
  const [slug, setSlug] = useState(projects[0]?.slug ?? "");
  const refresh = () => { queryClient.invalidateQueries({ queryKey: ["dashboard"] }); queryClient.invalidateQueries({ queryKey: ["inbox"] }); };
  const triage = useMutation({
    mutationFn: (body: { processed: boolean; project?: string }) =>
      api(`/quick-capture/${id}/`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    onSuccess: (_out, body) => {
      refresh();
      // #440: undo puts the capture back in the inbox
      const label = body.project ? `Filed under ${projects.find((p) => p.slug === body.project)?.name ?? body.project}` : "Dismissed";
      showUndo(`${label}${text ? ` — “${text.slice(0, 50)}”` : ""}`, async () => {
        await api(`/quick-capture/${id}/`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ processed: false, project: null }) });
        refresh();
      });
    },
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
/** #489: the project's twelve-week pulse (#483) at card size — hollow silent weeks, the peak
 *  glows, a "quiet n wk" chip when the strip has gone flat. */
function MiniPulse({ pulse, color }: { pulse: PulseData; color: string }) {
  const max = Math.max(1, ...pulse.weeks);
  const scale = (n: number) => Math.sqrt(n / max);
  return (
    <span className="mt-1.5 flex items-center gap-2" data-testid="project-pulse" title={pulse.total ? `${pulse.total} events in 12 weeks${pulse.last_activity ? ` · last activity ${pulse.last_activity}` : ""}` : "No activity in the last 12 weeks"}>
      <span className="flex h-3.5 w-24 items-end gap-px">
        {pulse.weeks.map((n, i) => (
          <span key={i} className={`flex-1 rounded-[1px] ${n ? "" : "border border-stone-300/70 dark:border-stone-700"}`}
                style={{ height: n ? Math.max(3, Math.round(scale(n) * 14)) : 2, background: n ? color : "transparent", opacity: n ? 0.5 + 0.5 * scale(n) : 1, boxShadow: n && n === max ? `0 0 6px ${color}` : undefined }} />
        ))}
      </span>
      {pulse.quiet_weeks >= 3 ? <span className="text-[10px] text-stone-400">quiet {pulse.quiet_weeks} wk</span> : pulse.total > 0 ? <span className="text-[10px] text-stone-400">{pulse.total} in 12 wk</span> : null}
    </span>
  );
}

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

/** #491: the dashboard as a paste-ready morning note — copied to the clipboard and shown so it
 *  can be read before it goes into a journal or a message; the preview is the fallback when
 *  the clipboard refuses (a locked-down webview, no user gesture). */
async function copyDailyBrief(): Promise<void> {
  let brief: { markdown: string; date: string; needs: number; todos: number; reading: number; writing: number };
  try { brief = await api("/dashboard/brief/"); } catch (e) { await errorDialog("Could not build today's brief", e); return; }
  let copied = false;
  try { await navigator.clipboard.writeText(brief.markdown); copied = true; } catch { copied = false; }
  await noticeDialog({
    title: copied ? "Today's brief copied" : "Today's brief",
    wide: true,
    okLabel: "Done",
    body: (
      <div data-testid="daily-brief">
        <p className="mb-2 text-xs text-stone-500 dark:text-stone-400">{brief.date} · {brief.needs} need{brief.needs === 1 ? "s" : ""} you · {brief.todos} on the list · {brief.reading} to read · {brief.writing} papers{copied ? " · on your clipboard as markdown" : " · select the text to copy it"}</p>
        <pre style={{ maxHeight: "60vh" }} className="overflow-auto whitespace-pre-wrap rounded-xl border border-stone-200 bg-stone-50 p-3 font-mono text-xs leading-relaxed text-stone-800 dark:border-stone-700 dark:bg-stone-950/60 dark:text-stone-200">{brief.markdown}</pre>
      </div>
    ),
  });
}

/** #490: a stat tile carries its six-month trend (bars, the current month last and brighter)
 *  and how this month compares with the last — calm, no colour judgement: research months
 *  are not sales quarters. */
function Stat({ value, label, i, to, series, previous, months }: { value: number; label: string; i: number; to?: string; series?: number[]; previous?: number; months?: string[] }) {
  const max = series ? Math.max(1, ...series) : 1;
  const delta = previous == null ? null : value - previous;
  const lastMonth = months && months.length >= 2 ? new Date(`${months[months.length - 2]}-01T00:00:00`).toLocaleDateString(undefined, { month: "short" }) : "last month";
  const inner = (
    <>
      <div className="flex items-end justify-between gap-2">
        <p className="font-display text-gradient text-4xl font-bold tabular-nums leading-none">{value}</p>
        {series && series.length > 0 && (
          <span className="flex h-6 items-end gap-[3px]" data-testid="stat-trend" aria-hidden="true" title={series.map((n, k) => `${months?.[k] ?? k}: ${n}`).join(" · ")}>
            {series.map((n, k) => <span key={k} className={`w-1.5 rounded-sm ${k === series.length - 1 ? "bg-indigo-500 dark:bg-indigo-400" : "bg-stone-300 dark:bg-stone-700"}`} style={{ height: n ? Math.max(3, Math.round((n / max) * 24)) : 2 }} />)}
          </span>
        )}
      </div>
      <p className="mt-2 text-xs text-stone-400 dark:text-stone-400">{label}</p>
      {delta != null && <p className="mt-0.5 text-[11px] tabular-nums text-stone-400 dark:text-stone-500" data-testid="stat-delta">{delta > 0 ? `▲ ${delta}` : delta < 0 ? `▼ ${-delta}` : "="} vs {lastMonth}</p>}
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
  const firstRun = demo.data?.projects === 0;
  // backlog #300: tick a to-do from the hero; the rank chip reads the (cached) pet state
  const tick = useMutation({
    mutationFn: (id: number) => api(`/todos/${id}/`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ done: true }) }),
    onSuccess: () => { qcAll.invalidateQueries({ queryKey: ["dashboard"] }); qcAll.invalidateQueries({ queryKey: ["todos"] }); },
  });
  const petQ = useQuery({ queryKey: ["pet"], queryFn: () => api<{ rank?: { name: string }; achievement_score?: number; souls_mode?: boolean }>("/pet/"), staleTime: 300_000 });
  // first run on the desktop: offer to fetch the TeX bundle now rather than behind the first compile (#372).
  // These hooks live ABOVE the loading/error returns on purpose — a hook below an early return
  // changes the hook count between renders and blanks the whole page (React #310, 2026-09-07).
  type Warm = { state: string; warm: boolean; size_mb: number };
  const warmState = useQuery({ queryKey: ["latex-warm"], queryFn: () => api<Warm>("/diagnostics/warm-latex/"), enabled: firstRun, refetchInterval: (q) => (q.state.data?.state === "running" ? 3000 : false) });
  const warmUp = useMutation({ mutationFn: () => api<Warm>("/diagnostics/warm-latex/", { method: "POST" }), onSuccess: () => qcAll.invalidateQueries({ queryKey: ["latex-warm"] }) });

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
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      </div>
    );
  if (error || !data) return <ErrorState message="Couldn't load the dashboard." onRetry={() => refetch()} />;

  const attention = data.attention;
  const backupStale = !!attention.backup?.stale;
  const waiting = attention.waiting ?? [];
  const quiet = attention.quiet ?? [];
  const needs = attention.overdue.length + attention.deadlines.length + attention.inbox.length + waiting.length + (backupStale ? 1 : 0);
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
              {petQ.data?.rank && <Link to="/achievements" className={`ml-2 inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-[11px] font-medium transition-colors ${petQ.data.souls_mode ? "border-red-500/50 text-red-600 hover:bg-red-500/10 dark:text-red-300" : "border-amber-300/60 text-amber-700 hover:bg-amber-500/10 dark:border-amber-500/40 dark:text-amber-300"}`} title="Your achievements" data-testid="rank-chip"><Trophy className="h-3 w-3" aria-hidden="true" />{petQ.data.rank.name} · {petQ.data.achievement_score ?? 0} pts</Link>}
            </p>
            {data.todos.length > 0 && (
              <ul className="mt-4 space-y-1" data-testid="hero-todos" aria-label="On your list">
                {data.todos.map((t) => (
                  <li key={t.id} className="group flex items-center gap-2 text-sm text-stone-700 dark:text-stone-200">
                    <button type="button" onClick={() => tick.mutate(t.id)} className="flex h-4 w-4 shrink-0 items-center justify-center rounded border border-stone-300 text-transparent transition-colors hover:border-indigo-400 hover:text-indigo-500 dark:border-stone-600" aria-label={`Done: ${t.text}`} title="Tick it off"><Check className="h-3 w-3" aria-hidden="true" /></button>
                    <span className="min-w-0 truncate">{t.text}</span>
                    {t.due_at && <span className={`shrink-0 text-[11px] tabular-nums ${dueState(t.due_at) === "overdue" ? "text-red-500" : dueState(t.due_at) === "soon" ? "text-amber-600 dark:text-amber-300" : "text-stone-400"}`} data-testid="hero-due">· {formatDue(t.due_at, t.all_day)}</span>}
                    {t.project && <span className="min-w-0 max-w-[9rem] truncate text-[11px] text-stone-400">· {t.project}</span>}
                  </li>
                ))}
                {data.todos_open > data.todos.length && <li className="text-xs text-stone-400"><Link to="/today" className="inline-flex items-center gap-1 hover:text-indigo-600 dark:hover:text-indigo-300"><ListChecks className="h-3 w-3" aria-hidden="true" />{data.todos_open - data.todos.length} more on today's list</Link></li>}
              </ul>
            )}
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
            <button type="button" onClick={() => void copyDailyBrief()} className="ml-3 mt-5 inline-flex items-center gap-1.5 rounded-full border border-stone-200 px-3 py-2 text-xs text-stone-500 transition-colors hover:border-stone-300 hover:text-stone-800 dark:border-stone-700 dark:bg-stone-950/40 dark:text-stone-300 dark:hover:text-stone-100" title="The dashboard as a paste-ready markdown note" data-testid="copy-brief">
              <ClipboardList className="h-3.5 w-3.5" aria-hidden="true" />Copy today's brief
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
      {attention.empty && !backupStale && waiting.length === 0 && quiet.length === 0 ? (
        <div className="rise mb-5 rounded-2xl border border-dashed border-stone-300 bg-white px-5 py-4 text-sm text-stone-500 dark:border-stone-700 dark:bg-stone-900 dark:text-stone-300" style={{ ["--i" as string]: 1 }}>
          All clear — nothing overdue, no deadlines inside two weeks, inbox triaged.
        </div>
      ) : (
        <section className={`${panel} rise mb-5 border-l-2 border-l-red-400 dark:border-l-red-400/80 dark:shadow-[inset_12px_0_28px_-24px_rgba(248,113,113,0.9)]`} style={{ ["--i" as string]: 1 }}>
          <h2 className={`${h2} mb-2.5`}>Needs attention</h2>
          <ul className="space-y-1.5 text-sm">
            {attention.overdue.map((m) => (
              <li key={`o${m.url}${m.title}`} className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                <span className="shrink-0 rounded-full bg-red-500/10 px-2 py-0.5 text-[11px] font-medium text-red-600 dark:text-red-300">overdue</span>
                <a href={m.url} className="min-w-0 flex-1 truncate hover:underline dark:text-stone-100">{m.title}</a>
                <span className="shrink-0 text-xs text-stone-400 dark:text-stone-400">{m.project} · due {m.due_date}</span>
              </li>
            ))}
            {attention.deadlines.map((d) => (
              <li key={`d${d.url}${d.title}`} className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
                <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium ${d.days_to_deadline < 7 ? "bg-red-500/10 text-red-600 dark:text-red-300" : "bg-amber-500/10 text-amber-600 dark:text-amber-300"}`}>deadline</span>
                <a href={d.url} className="min-w-0 flex-1 truncate hover:underline dark:text-stone-100">{d.title}</a>
                <span className="shrink-0 text-xs text-stone-400 dark:text-stone-400">
                  {d.project} · {d.days_to_deadline < 0 ? "passed" : `${d.days_to_deadline} day${d.days_to_deadline === 1 ? "" : "s"}`} ({d.deadline})
                </span>
              </li>
            ))}
            {waiting.map((w) => (
              <li key={`w${w.id}`} className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5" data-testid="attention-waiting">
                <span className="shrink-0 rounded-full bg-amber-500/10 px-2 py-0.5 text-[11px] font-medium text-amber-600 dark:text-amber-300">waiting</span>
                <a href={w.url} className="min-w-0 flex-1 truncate hover:underline dark:text-stone-100">{w.title}</a>
                <span className="shrink-0 text-xs text-stone-400 dark:text-stone-400" title={w.basis}>{w.venue || w.project} · {w.waited} d, usually {w.after_days} — a nudge is fair</span>
              </li>
            ))}
            {/* #489: a project that has gone flat — before a deadline says so */}
            {quiet.map((q) => (
              <li key={`q${q.slug}`} className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5" data-testid="attention-quiet">
                <span className="shrink-0 rounded-full bg-stone-500/10 px-2 py-0.5 text-[11px] font-medium text-stone-500 dark:text-stone-300">quiet</span>
                <Link to={q.url} className="min-w-0 flex-1 truncate hover:underline dark:text-stone-100">{q.name}</Link>
                <span className="shrink-0 text-xs text-stone-400 dark:text-stone-400">nothing logged for {q.quiet_weeks} weeks{q.days_since != null ? ` · last activity ${q.days_since} d ago` : ""}</span>
              </li>
            ))}
            {/* #424: a calm nudge when the last backup is old or there has never been one */}
            {backupStale && attention.backup && (
              <li className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5" data-testid="attention-backup">
                <span className="shrink-0 rounded-full bg-amber-500/10 px-2 py-0.5 text-[11px] font-medium text-amber-600 dark:text-amber-300">backup</span>
                <span className="min-w-0 flex-1 truncate text-stone-600 dark:text-stone-300">
                  {attention.backup.last ? `Last backup ${attention.backup.last.days_ago} days ago.` : "No backup yet."} Everything lives in one file — worth keeping a copy somewhere else.
                </span>
                <a href="/api/v1/backup.zip" className="shrink-0 text-xs font-medium text-indigo-600 hover:underline dark:text-indigo-300">Download a backup →</a>
              </li>
            )}
            {attention.inbox.map((q) => (
              <li key={`q${q.id}`} className="flex items-baseline gap-2">
                <span className="shrink-0 rounded-full bg-indigo-500/10 px-2 py-0.5 text-[11px] font-medium text-indigo-600 dark:text-indigo-300">inbox</span>
                <span className="min-w-0 flex-1 truncate text-stone-600 dark:text-stone-300">{q.text}</span>
                <TriageControls id={q.id} text={q.text} projects={data.active} />
                <Link to="/inbox" className="shrink-0 text-xs text-stone-400 hover:underline dark:text-stone-400" title="Open the full inbox">all →</Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      <WeekEverywhere week={data.week} />

      {!calm && (
        <div className="mb-5 grid grid-cols-1 gap-4 min-[480px]:grid-cols-2 sm:grid-cols-3 lg:grid-cols-6">
          <Stat value={data.todos_open} label="on today's list" i={2} to="/today" />
          <Stat value={data.stats.papers_read} label="papers read this month" i={3} series={data.trends?.series.papers_read} previous={data.trends?.previous.papers_read} months={data.trends?.months} />
          <Stat value={data.stats.notes_written} label="notes written this month" i={4} series={data.trends?.series.notes_written} previous={data.trends?.previous.notes_written} months={data.trends?.months} />
          <Stat value={data.stats.words_written} label="words written this month" i={5} to="/writing" series={data.trends?.series.words_written} previous={data.trends?.previous.words_written} months={data.trends?.months} />
          <Stat value={data.stats.milestones_done} label="milestones completed" i={6} series={data.trends?.series.milestones_done} previous={data.trends?.previous.milestones_done} months={data.trends?.months} />
          <Stat value={data.inbox_count} label="inbox items to triage" i={7} to="/inbox" />
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <section className={`${panel} rise min-w-0`} style={{ ["--i" as string]: 6 }}>
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
                  {p.pulse && <MiniPulse pulse={p.pulse} color={p.color} />}
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

        <div className="min-w-0 space-y-4">
        {/* #487: every live paper across the active projects, the way the overview shows them */}
        <section className={`${panel} rise min-w-0`} style={{ ["--i" as string]: 7 }} data-testid="writing-everywhere">
          <div className="flex items-baseline justify-between"><h2 className={h2}>Writing{data.writing && data.writing.live > 0 && <span className="ml-1 normal-case tracking-normal">{data.writing.live}</span>}</h2><CalendarSubscribe /></div>
          <ul className="space-y-1.5 text-sm">
            {(data.writing?.rows ?? []).map((m) => (
              <li key={m.id} data-testid="writing-row">
                <Link to={`/manuscripts/${m.id}`} className="-mx-2 block rounded-lg px-2 py-1.5 transition-colors hover:bg-stone-50 dark:hover:bg-stone-800">
                  <span className="block truncate font-medium text-stone-800 hover:text-indigo-700 dark:text-stone-100 dark:hover:text-indigo-300">{m.title}</span>
                  <span className="mt-0.5 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-[11px] text-stone-400">
                    <span className="capitalize">{m.status.replace("_", " ")}</span>
                    <span>· {m.project}</span>
                    {m.days != null && <span className={m.days <= 7 ? "font-medium text-red-600 dark:text-red-300" : ""}>· {m.days < 0 ? `${-m.days} d overdue` : m.days === 0 ? "due today" : `${m.days} d left`}</span>}
                    {m.clock && m.clock.days >= 1 && <span className={m.clock.nudge?.due ? "rounded-full bg-amber-500/10 px-1.5 font-medium text-amber-600 dark:text-amber-300" : ""} title={m.clock.nudge?.due ? `${m.clock.nudge.waited} d with no word, usually ${m.clock.nudge.after_days} — a polite note to the editor is fair` : undefined}>· {m.clock.label}{m.clock.nudge?.due ? " · nudge?" : ""}</span>}
                    {m.readiness && <span className={`rounded-full px-1.5 ${m.readiness.ready ? (m.readiness.warns ? "bg-amber-500/10 text-amber-600 dark:text-amber-300" : "bg-emerald-500/10 text-emerald-600 dark:text-emerald-300") : "bg-red-500/10 text-red-600 dark:text-red-300"}`} title={m.readiness.summary}>{m.readiness.ready ? (m.readiness.warns ? `ready · ${m.readiness.warns} to look at` : "ready to submit") : `${m.readiness.fails} blocking`}</span>}
                  </span>
                </Link>
              </li>
            ))}
            {(!data.writing || data.writing.rows.length === 0) && (
              <li className="text-sm text-stone-400 dark:text-stone-400">
                Nothing in the pipeline. <Link to="/writing" className="text-indigo-600 hover:text-indigo-700 dark:text-indigo-400 dark:hover:text-indigo-300">Open Writing →</Link>
              </li>
            )}
          </ul>
        </section>
        {/* #486: what to read today — the queue head across every active project */}
        <section className={`${panel} rise min-w-0`} style={{ ["--i" as string]: 7.5 }} data-testid="reading-next">
          <div className="flex items-baseline justify-between"><h2 className={h2}><BookOpen className="mr-1 inline h-3 w-3 align-[-1px]" aria-hidden="true" />Next to read</h2>
            {data.reading && data.reading.to_read > 0 && <span className="text-[11px] text-stone-400">{data.reading.to_read} unread{data.reading.high_priority > 0 ? ` · ${data.reading.high_priority} high priority` : ""}{data.reading.projects > 1 ? ` · ${data.reading.projects} projects` : ""}</span>}
          </div>
          <ul className="space-y-0.5 text-sm">
            {(data.reading?.next ?? []).map((r) => (
              <li key={r.id} data-testid="reading-row">
                <Link to={`/library/${r.id}`} className={row} title={`${r.title}${r.first_author ? ` — ${r.first_author}` : ""}${r.year ? ` ${r.year}` : ""} · ${r.project}${r.waiting_days >= 1 ? ` · waiting ${r.waiting_days} d` : ""}`}>
                  {r.priority === "high" ? <span className="shrink-0 rounded-full bg-amber-500/10 px-1.5 text-[10px] font-medium text-amber-600 dark:text-amber-300">high</span> : <span aria-hidden="true" className="text-stone-300 dark:text-stone-500">·</span>}
                  <span className="min-w-0 flex-1 truncate font-medium dark:text-stone-100">{r.title}</span>
                  <span className="shrink-0 truncate text-xs text-stone-400 dark:text-stone-400" style={{ maxWidth: "9rem" }}>{[r.first_author, r.year].filter(Boolean).join(" ") || r.project}</span>
                </Link>
              </li>
            ))}
            {(!data.reading || data.reading.next.length === 0) && (
              <li className="text-sm text-stone-400 dark:text-stone-400">
                Nothing waiting to be read. <Link to="/library" className="text-indigo-600 hover:text-indigo-700 dark:text-indigo-400 dark:hover:text-indigo-300">Open the Library →</Link>
              </li>
            )}
          </ul>
          {data.reading && data.reading.next.length > 0 && <p className="mt-2 text-[11px] text-stone-400"><Link to={`/projects/${data.reading.next[0].project_slug}/queue`} className="hover:text-indigo-600 dark:hover:text-indigo-300">Open the reading queue →</Link></p>}
        </section>
        {/* #533: what the feeds announced and who cited the library's papers — the Library's watches, linking into their modes (#532) */}
        <section className={`${panel} rise min-w-0`} style={{ ["--i" as string]: 7.75 }} data-testid="watches">
          <div className="flex items-baseline justify-between"><h2 className={h2}><Radar className="mr-1 inline h-3 w-3 align-[-1px]" aria-hidden="true" />Watches</h2>
            {data.watches && (data.watches.feeds.new > 0 || data.watches.citations.new > 0) && <span className="text-[11px] text-stone-400">{[data.watches.feeds.new > 0 ? `${data.watches.feeds.new} from feeds` : "", data.watches.citations.new > 0 ? `${data.watches.citations.new} new citation${data.watches.citations.new === 1 ? "" : "s"}` : ""].filter(Boolean).join(" · ")}</span>}
          </div>
          <ul className="space-y-0.5 text-sm">
            {(data.watches?.feeds.rows ?? []).map((r) => (
              <li key={`f${r.id}`} data-testid="watch-feed-row">
                <Link to={`/library?feeds=1&feed=${r.feed_id}`} className={row} title={`${r.title} — ${r.feed}${r.published_on ? ` · ${r.published_on}` : ""}`}>
                  <Rss className="h-3 w-3 shrink-0 self-center text-emerald-500" aria-hidden="true" />
                  <span className="min-w-0 flex-1 truncate font-medium dark:text-stone-100">{r.title}</span>
                  <span className="shrink-0 truncate text-xs text-stone-400 dark:text-stone-400" style={{ maxWidth: "9rem" }}>{r.feed}</span>
                </Link>
              </li>
            ))}
            {(data.watches?.citations.rows ?? []).map((r) => (
              <li key={`c${r.id}`} data-testid="watch-citation-row">
                <Link to={r.cites[0] ? `/library?citing=1&reference=${r.cites[0].id}` : "/library?citing=1"} className={row} title={`${r.title}${r.first_author ? ` — ${r.first_author}` : ""}${r.year ? ` ${r.year}` : ""}${r.venue ? ` · ${r.venue}` : ""}${r.cites.length ? ` · cites ${r.cites.map((c) => c.bibtex_key).join(", ")}` : ""}`}>
                  <Radar className="h-3 w-3 shrink-0 self-center text-sky-500" aria-hidden="true" />
                  <span className="min-w-0 flex-1 truncate font-medium dark:text-stone-100">{r.title}</span>
                  <span className="shrink-0 truncate font-mono text-[11px] text-sky-600 dark:text-sky-300" style={{ maxWidth: "9rem" }}>{r.cites[0] ? `cites ${r.cites[0].bibtex_key}${r.cites.length > 1 ? ` +${r.cites.length - 1}` : ""}` : r.venue}</span>
                </Link>
              </li>
            ))}
            {data.watches && data.watches.feeds.rows.length === 0 && data.watches.citations.rows.length === 0 && (
              <li className="text-sm text-stone-400 dark:text-stone-400">
                {data.watches.feeds.followed === 0 ? <>No feeds followed yet. <Link to="/library?feeds=1" className="text-indigo-600 hover:text-indigo-700 dark:text-indigo-400 dark:hover:text-indigo-300">Follow an arXiv category or a journal →</Link></> : <>Nothing new from your feeds, no new citations. <Link to="/library?feeds=1" className="text-indigo-600 hover:text-indigo-700 dark:text-indigo-400 dark:hover:text-indigo-300">Open the feeds →</Link></>}
              </li>
            )}
          </ul>
          {data.watches && (data.watches.feeds.rows.length > 0 || data.watches.citations.rows.length > 0) && (
            <p className="mt-2 flex flex-wrap gap-x-3 text-[11px] text-stone-400">
              {data.watches.feeds.new > 0 && <Link to={data.watches.feeds.url} className="hover:text-indigo-600 dark:hover:text-indigo-300">All feeds →</Link>}
              {data.watches.citations.new > 0 && <Link to={data.watches.citations.url} className="hover:text-indigo-600 dark:hover:text-indigo-300">All new citations →</Link>}
              {data.watches.feeds.errors > 0 && <span className="text-amber-500">{data.watches.feeds.errors} feed{data.watches.feeds.errors === 1 ? "" : "s"} failed to fetch</span>}
            </p>
          )}
        </section>
        </div>

        <section className={`${panel} rise min-w-0`} style={{ ["--i" as string]: 8 }}>
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
                    <span className="hidden min-w-0 max-w-[10rem] truncate text-[11px] text-stone-400 sm:inline-block">{i.project_name}</span>
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
type DayEvent = { kind: string; label: string; detail: string; url: string; project: string; project_slug: string };

function Heatmap({ weeks }: { weeks: Dash["heatmap"] }) {
  const LEVEL = ["bg-stone-100 dark:bg-stone-800", "bg-indigo-500/25", "bg-indigo-500/45", "bg-indigo-500/70", "bg-indigo-400"];
  // #492: a cell is a button; the chosen day's events come from /dashboard/day/ on demand
  const [selectedDay, setSelectedDay] = useState<string | null>(null);
  const dayQ = useQuery({ queryKey: ["day-activity", selectedDay], queryFn: () => api<{ date: string; count: number; events: DayEvent[] }>(`/dashboard/day/?date=${selectedDay}`), enabled: !!selectedDay, staleTime: 60_000 });
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
                {w.map((c) => <button key={c.date} type="button" onClick={() => setSelectedDay((d) => (d === c.date ? null : c.date))} aria-label={`${c.date}: ${c.count} change${c.count === 1 ? "" : "s"}`} aria-pressed={selectedDay === c.date} className={`block h-[11px] w-[11px] rounded-[2px] transition-shadow hover:ring-1 hover:ring-indigo-400 ${selectedDay === c.date ? "ring-1 ring-indigo-500 ring-offset-1 ring-offset-white dark:ring-offset-stone-900" : ""} ${LEVEL[c.level] ?? LEVEL[0]}`} title={`${c.date} · ${c.count} change${c.count === 1 ? "" : "s"} — click for the day`} data-testid="heatmap-day" />)}
              </div>
            ))}
          </div>
        </div>
      </div>
      {selectedDay && (
        <div className="mt-3 rounded-xl border border-stone-200 bg-stone-50/60 p-3 text-sm dark:border-stone-800 dark:bg-stone-950/30" data-testid="day-panel">
          <div className="mb-1.5 flex items-baseline justify-between gap-3">
            <p className="text-xs font-medium text-stone-700 dark:text-stone-200">{new Date(`${selectedDay}T00:00:00`).toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" })}{dayQ.data ? ` · ${dayQ.data.count} event${dayQ.data.count === 1 ? "" : "s"}` : ""}</p>
            <button type="button" onClick={() => setSelectedDay(null)} className="text-[11px] text-stone-400 hover:text-stone-700 dark:hover:text-stone-200">close</button>
          </div>
          {dayQ.isLoading && <p className="text-xs text-stone-400">Looking…</p>}
          {dayQ.error && <p className="text-xs text-red-500">Couldn't load that day.</p>}
          {dayQ.data && dayQ.data.count === 0 && <p className="text-xs text-stone-400">Nothing logged that day — the heatmap counts every change, including edits; the timeline lists the events.</p>}
          {dayQ.data && dayQ.data.count > 0 && (
            <ul className="space-y-0.5">
              {dayQ.data.events.map((e, i) => (
                <li key={i} className="flex items-baseline gap-2 text-xs">
                  <span className="shrink-0 rounded-full bg-stone-200/70 px-1.5 text-[10px] text-stone-600 dark:bg-stone-800 dark:text-stone-300">{e.kind.replace("_", " ")}</span>
                  <Link to={e.url} className="min-w-0 flex-1 truncate text-stone-800 hover:text-indigo-700 dark:text-stone-100 dark:hover:text-indigo-300" title={e.detail || e.label}>{e.label}</Link>
                  <span className="shrink-0 text-stone-400">{e.project}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
    </section>
  );
}

/** Backlog #9: one click copies the .ics subscription URL. Since #401 the URL carries a
 *  read-only feed token (not the API key); "rotate" invalidates every URL copied so far. */
function CalendarSubscribe() {
  const [state, setState] = useState<"idle" | "copied" | "error" | "rotated">("idle");
  const copy = async () => {
    try {
      const t = await api<{ token: string; url: string }>("/feed-token/");
      await navigator.clipboard.writeText(t.url);
      setState("copied"); window.setTimeout(() => setState("idle"), 3000);
    } catch { setState("error"); }
  };
  const rotate = async () => {
    if (!(await confirmDialog({ title: "Rotate the calendar token?", body: "Every calendar subscription copied so far stops updating; copy the new URL afterwards.", confirmLabel: "Rotate" }))) return;
    try { await api("/feed-token/", { method: "POST" }); setState("rotated"); window.setTimeout(() => setState("idle"), 3000); } catch { setState("error"); }
  };
  return (
    <span className="mb-3 inline-flex items-center gap-2 text-[11px] text-stone-400">
    <button type="button" onClick={() => void rotate()} className="hover:text-indigo-600 dark:hover:text-indigo-300" title="Rotate the feed token — old subscription URLs stop working" data-testid="feed-rotate">rotate</button>
    <button type="button" onClick={() => void copy()} className="inline-flex items-center gap-1 hover:text-indigo-600 dark:hover:text-indigo-300" title="Copy a calendar subscription URL (milestones + manuscript deadlines). Paste it into Google Calendar / Outlook / Apple Calendar under 'subscribe by URL'. The URL contains your API key." data-testid="calendar-subscribe">
      <CalendarClock className="h-3 w-3" aria-hidden="true" />{state === "copied" ? "URL copied — subscribe in your calendar" : state === "rotated" ? "token rotated — copy the new URL" : state === "error" ? "couldn't get the feed URL" : "subscribe (.ics)"}
    </button>
    </span>
  );
}
