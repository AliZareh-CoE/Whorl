/** Project overview v2 (Observatory): where is what, and how is it going — in one glance.
 *  Current phase with health + ring, this week's focus, what changed this week, open questions,
 *  manuscripts at a glance, counts, next milestones, recent documents and decisions.
 *  Data: GET /projects/{slug}/overview/ (also the MCP get_project_overview tool). */
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { Activity, BookOpen, FileText, FlaskConical, HelpCircle, PenLine } from "lucide-react";
import { api } from "../api";
import { Skeleton, SkeletonCard } from "../../components/Skeleton";
import { ErrorState } from "../../components/ErrorState";
import Focus, { type FocusData } from "./plan/Focus";

type Overview = {
  health: { state: string; label: string; forecast_end: string | null; start: string; end: string } | null;
  focus: FocusData;
  project: { name: string; slug: string; description: string; status: string; color: string };
  current_phase: { id: number; name: string; status: string; objective: string; progress: number } | null;
  progress: { done: number; total: number; percent: number };
  next_milestones: { id: number; title: string; due_date: string | null; overdue: boolean; phase: string }[];
  counts: Record<string, number>;
  recent_documents: { id: number; title: string; added: string; url: string }[];
  recent_decisions: { id: number; title: string; decided_on: string }[];
  week_digest: { since: string; total: number; counts: { kind: string; label: string; count: number }[]; items: { date: string; kind: string; label: string; detail: string; url: string }[] };
  questions: { id: number; question: string; status: string; phases: string[] }[];
  manuscripts: { id: number; title: string; status: string; deadline: string | null; days: number | null; target_venue: string; over: string[] }[];
  hypotheses: { total: number; by_status: Record<string, number> };
};

const panel = "rounded-2xl border border-stone-200 bg-white dark:border-stone-800 dark:bg-stone-900";
const h2 = "mb-2 flex items-baseline gap-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-stone-400 dark:text-stone-500";
const quickLinks = [["plan", "Plan"], ["literature", "Literature"], ["documents", "Documents"], ["figures", "Figures"], ["files", "Files"], ["notes", "Notes"], ["research", "Research"], ["decisions", "Decisions"], ["graph", "Graph"], ["review", "Review"], ["timeline", "Timeline"]] as const;
const HEALTH: Record<string, string> = { behind: "bg-amber-500/15 text-amber-700 dark:text-amber-300", overdue: "bg-red-500/15 text-red-700 dark:text-red-300", blocked: "bg-red-500/15 text-red-700 dark:text-red-300", ahead: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300", done: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300", on_track: "bg-indigo-500/15 text-indigo-700 dark:text-indigo-200", upcoming: "bg-stone-100 text-stone-500 dark:bg-stone-800 dark:text-stone-300" };
const Q_STATUS: Record<string, string> = { open: "bg-indigo-500/15 text-indigo-700 dark:text-indigo-200", partially_answered: "bg-amber-500/15 text-amber-700 dark:text-amber-300", answered: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300", abandoned: "bg-stone-100 text-stone-400 line-through dark:bg-stone-800" };
const KIND_DOT: Record<string, string> = { milestone: "#7c6cff", paper_added: "#38bdf8", paper_read: "#22c55e", note: "#fbbf24", decision: "#f43f5e", experiment: "#a78bfa", hypothesis: "#e879f9", document: "#a8a29e", manuscript: "#10b981", manuscript_compiled: "#14b8a6" };

function Ring({ percent, color, size = 56 }: { percent: number; color: string; size?: number }) {
  const r = (size - 5) / 2; const c = 2 * Math.PI * r; const off = c * (1 - Math.max(0, Math.min(100, percent)) / 100);
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="orbit-ring shrink-0" aria-hidden="true">
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="currentColor" strokeWidth="4" className="text-stone-100 dark:text-stone-800" />
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth="4" strokeLinecap="round" strokeDasharray={c} strokeDashoffset={off} transform={`rotate(-90 ${size / 2} ${size / 2})`} style={{ transition: "stroke-dashoffset 900ms cubic-bezier(.2,.7,.2,1)" }} />
    </svg>
  );
}
/** Markdown → plain text for one-line descriptions (bold/italic/code/link markers dropped). */
function plain(md: string): string { return md.replace(/\*\*(.+?)\*\*/g, "$1").replace(/\*(.+?)\*/g, "$1").replace(/`(.+?)`/g, "$1").replace(/\[(.+?)\]\([^)]*\)/g, "$1"); }
function when(days: number | null): string { if (days == null) return "no deadline"; if (days < 0) return `${-days} d overdue`; if (days === 0) return "due today"; return `${days} d left`; }

export default function ProjectOverview() {
  const { slug } = useParams();
  const { data, isLoading, error, refetch } = useQuery({ queryKey: ["overview", slug], queryFn: () => api<Overview>(`/projects/${slug}/overview/`) });
  if (isLoading) return <div role="status" aria-label="Loading" className="space-y-4"><Skeleton className="h-4 w-40" /><Skeleton className="h-8 w-72" /><SkeletonCard /><div className="grid gap-4 lg:grid-cols-2"><SkeletonCard /><SkeletonCard /></div></div>;
  if (error || !data) return <ErrorState message="Couldn't load this project." onRetry={() => refetch()} />;
  const { project, progress } = data;
  const accent = project.color || "var(--color-indigo-500)";
  const digest = data.week_digest;
  return (
    <div>
      <nav className="mb-4 text-sm text-stone-500 dark:text-stone-400"><Link to="/projects" className="hover:underline">Projects</Link> <span className="px-1 text-stone-300">/</span> <span className="text-stone-700 dark:text-stone-300">{project.name}</span></nav>
      <header className="mb-5 flex flex-wrap items-start gap-4">
        <Ring percent={progress.percent} color={accent} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-3">
            <h1 className="font-display text-3xl font-bold tracking-tight text-stone-900 dark:text-stone-100">{project.name}</h1>
            <span className="rounded-full bg-stone-100 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.14em] text-stone-500 dark:bg-stone-800 dark:text-stone-300">{project.status}</span>
            <span className="text-sm text-stone-400"><span className="text-gradient font-display text-base font-bold">{progress.done}/{progress.total}</span> milestones</span>
          </div>
          {project.description && <p className="mt-1 max-w-2xl text-sm leading-relaxed text-stone-500 dark:text-stone-400">{plain(project.description)}</p>}
          <nav className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs text-stone-400">
            {quickLinks.map(([to, label]) => <Link key={to} to={`/projects/${project.slug}/${to}`} className="transition-colors hover:text-indigo-700 dark:hover:text-indigo-300">{label}</Link>)}
          </nav>
        </div>
      </header>

      <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <section className={`${panel} rise p-4`} style={{ ["--i" as string]: 0 }} data-testid="phase-card">
          <p className={h2}>Current phase</p>
          {data.current_phase ? (
            <>
              <div className="flex flex-wrap items-center gap-2">
                <Link to={`/projects/${project.slug}/plan`} className="font-display text-lg font-semibold text-stone-900 hover:text-indigo-700 dark:text-stone-100 dark:hover:text-indigo-300">{data.current_phase.name}</Link>
                {data.health && data.health.state !== "empty" && <span className={`rounded-full px-2 py-0.5 text-[11px] ${HEALTH[data.health.state] ?? HEALTH.upcoming}`} title={data.health.forecast_end ? `Forecast finish ${data.health.forecast_end}` : `${data.health.start} → ${data.health.end}`} data-testid="phase-health">{data.health.label}</span>}
              </div>
              {data.current_phase.objective && <p className="mt-1 text-sm leading-relaxed text-stone-500 dark:text-stone-400">{data.current_phase.objective}</p>}
              <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-stone-100 dark:bg-stone-800"><div className="h-1.5 rounded-full transition-[width] duration-500" style={{ width: `${data.current_phase.progress}%`, background: accent, boxShadow: `0 0 10px ${accent}` }} /></div>
              <p className="mt-1 flex justify-between text-[11px] text-stone-400"><span>{data.health ? `${data.health.start} → ${data.health.end}` : ""}</span><span>{data.current_phase.progress}% of the phase</span></p>
            </>
          ) : <p className="text-sm text-stone-400">No phases yet — <Link to={`/projects/${project.slug}/plan`} className="text-indigo-600 hover:underline dark:text-indigo-300">write the plan</Link> as an outline.</p>}
        </section>
        <Focus slug={project.slug} initial={data.focus} compact />
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        <section className={`${panel} rise p-4`} style={{ ["--i" as string]: 2 }} data-testid="digest">
          <p className={h2}><Activity className="h-3 w-3" aria-hidden="true" />This week in the project</p>
          {digest.total === 0 ? <p className="text-xs text-stone-400">Quiet week so far — nothing logged since {digest.since}.</p> : (
            <>
              <p className="mb-2 flex flex-wrap gap-x-3 gap-y-1 text-xs text-stone-600 dark:text-stone-300">{digest.counts.map((c) => <span key={c.kind} className="inline-flex items-center gap-1"><span className="inline-block h-1.5 w-1.5 rounded-full" style={{ background: KIND_DOT[c.kind] ?? "#a8a29e" }} /><b className="tabular-nums">{c.count}</b> {c.label}</span>)}</p>
              <ul className="space-y-1 text-xs">{digest.items.map((i, n) => <li key={n} className="flex items-baseline gap-2"><span className="shrink-0 tabular-nums text-stone-400">{i.date.slice(5)}</span><Link to={i.url} className="min-w-0 flex-1 truncate text-stone-700 hover:text-indigo-700 dark:text-stone-200 dark:hover:text-indigo-300" title={i.detail || i.label}>{i.label}</Link></li>)}</ul>
            </>
          )}
        </section>
        <section className={`${panel} rise p-4`} style={{ ["--i" as string]: 3 }} data-testid="questions">
          <p className={h2}><HelpCircle className="h-3 w-3" aria-hidden="true" />Research questions <span className="normal-case tracking-normal">{data.counts.questions}</span></p>
          {data.questions.length === 0 ? <p className="text-xs text-stone-400">None yet — <Link to={`/projects/${project.slug}/research`} className="text-indigo-600 hover:underline dark:text-indigo-300">ask the first one</Link>.</p> : (
            <ul className="space-y-1.5 text-sm">{data.questions.map((q) => <li key={q.id} className="flex items-start gap-2"><span className={`mt-0.5 shrink-0 rounded-full px-1.5 py-px text-[10px] ${Q_STATUS[q.status] ?? Q_STATUS.open}`}>{q.status.replace("_", " ")}</span><span className="min-w-0 flex-1 leading-snug text-stone-700 dark:text-stone-200" title={q.phases.length ? `Phases: ${q.phases.join(", ")}` : undefined}>{q.question}</span></li>)}</ul>
          )}
          {data.hypotheses.total > 0 && <p className="mt-2 flex items-center gap-1 text-[11px] text-stone-400"><FlaskConical className="h-3 w-3" aria-hidden="true" />{data.hypotheses.total} hypotheses · {Object.entries(data.hypotheses.by_status).map(([k, v]) => `${v} ${k}`).join(" · ")}</p>}
        </section>
        <section className={`${panel} rise p-4`} style={{ ["--i" as string]: 4 }} data-testid="manuscripts">
          <p className={h2}><PenLine className="h-3 w-3" aria-hidden="true" />Manuscripts <span className="normal-case tracking-normal">{data.counts.manuscripts}</span></p>
          {data.manuscripts.length === 0 ? <p className="text-xs text-stone-400">Nothing in the pipeline — <Link to="/writing" className="text-indigo-600 hover:underline dark:text-indigo-300">start a manuscript</Link>.</p> : (
            <ul className="space-y-2 text-sm">{data.manuscripts.map((m) => <li key={m.id}><Link to={`/manuscripts/${m.id}`} className="block truncate text-stone-800 hover:text-indigo-700 dark:text-stone-100 dark:hover:text-indigo-300">{m.title}</Link><p className="flex flex-wrap items-center gap-x-2 text-[11px] text-stone-400"><span className="capitalize">{m.status.replace("_", " ")}</span>{m.target_venue && <span>· {m.target_venue}</span>}<span className={m.days != null && m.days <= 7 ? "font-medium text-red-600 dark:text-red-300" : ""}>· {when(m.days)}</span>{m.over.length > 0 && <span className="rounded-full bg-red-500/10 px-1.5 text-red-600 dark:text-red-300">over on {m.over.join(", ")}</span>}</p></li>)}</ul>
          )}
        </section>
      </div>

      <div className="mt-4 grid grid-cols-3 gap-3 sm:grid-cols-4 lg:grid-cols-8">
        {Object.entries(data.counts).map(([key, value], i) => (
          <Link key={key} to={`/projects/${project.slug}/${key === "references" ? "literature" : key === "hypotheses" ? "research" : key === "manuscripts" ? "../../writing" : key === "questions" ? "research" : key}`} className={`${panel} rise px-3 py-2.5 text-center transition-colors hover:border-indigo-300 dark:hover:border-indigo-500/50`} style={{ ["--i" as string]: 5 + i * 0.3 }}>
            <p className="font-display text-xl font-bold leading-none tabular-nums text-stone-900 dark:text-stone-100">{value}</p>
            <p className="mt-1 text-[10px] uppercase tracking-wider text-stone-400">{key}</p>
          </Link>
        ))}
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-2">
        <section className={`${panel} rise p-4`} style={{ ["--i" as string]: 8 }}>
          <p className={h2}>Next milestones {data.next_milestones.length > 0 && <span className="normal-case tracking-normal">{data.next_milestones.length}</span>}</p>
          {data.next_milestones.length === 0 ? <p className="text-sm text-stone-400">No upcoming milestones. <Link to={`/projects/${project.slug}/plan`} className="text-indigo-600 hover:underline dark:text-indigo-300">Open the plan</Link> to add some.</p> : (
            <ul className="space-y-2 text-sm">{data.next_milestones.map((m) => <li key={m.id} className="flex items-baseline gap-2.5"><span aria-hidden="true" className="text-[10px] text-indigo-400">◆</span><span className="min-w-0 flex-1 truncate text-stone-700 dark:text-stone-200">{m.title}<span className="ml-1.5 text-[11px] text-stone-400">{m.phase}</span></span>{m.due_date && <span className={`shrink-0 text-xs ${m.overdue ? "font-medium text-red-600 dark:text-red-300" : "text-stone-400"}`}>{m.due_date}{m.overdue ? " · overdue" : ""}</span>}</li>)}</ul>
          )}
        </section>
        <div className="space-y-4">
          <section className={`${panel} rise p-4`} style={{ ["--i" as string]: 9 }}>
            <p className={h2}><FileText className="h-3 w-3" aria-hidden="true" />Recent documents {data.recent_documents.length > 0 && <span className="normal-case tracking-normal">{data.recent_documents.length}</span>}</p>
            {data.recent_documents.length === 0 ? <p className="text-sm text-stone-400">Nothing uploaded yet. <Link to={`/projects/${project.slug}/documents`} className="text-indigo-600 hover:underline dark:text-indigo-300">Add a document</Link>.</p> : (
              <ul className="space-y-1.5 text-sm">{data.recent_documents.map((d) => <li key={d.id} className="flex items-baseline gap-2.5"><a href={d.url} className="min-w-0 flex-1 truncate text-stone-700 hover:text-indigo-700 dark:text-stone-200 dark:hover:text-indigo-300">{d.title}</a><span className="shrink-0 text-xs text-stone-400">{d.added}</span></li>)}</ul>
            )}
          </section>
          <section className={`${panel} rise p-4`} style={{ ["--i" as string]: 10 }}>
            <p className={h2}><BookOpen className="h-3 w-3" aria-hidden="true" />Recent decisions {data.recent_decisions.length > 0 && <span className="normal-case tracking-normal">{data.recent_decisions.length}</span>}</p>
            {data.recent_decisions.length === 0 ? <p className="text-sm text-stone-400">No decisions recorded. <Link to={`/projects/${project.slug}/decisions`} className="text-indigo-600 hover:underline dark:text-indigo-300">Record one</Link>.</p> : (
              <ul className="space-y-1.5 text-sm">{data.recent_decisions.map((d) => <li key={d.id} className="flex items-baseline gap-2.5"><Link to={`/projects/${project.slug}/decisions`} className="min-w-0 flex-1 truncate text-stone-700 hover:text-indigo-700 dark:text-stone-200 dark:hover:text-indigo-300">{d.title}</Link><span className="shrink-0 text-xs text-stone-400">{d.decided_on}</span></li>)}</ul>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
