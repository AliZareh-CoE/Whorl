/** Project overview v2 (Observatory): where is what, and how is it going — in one glance.
 *  Current phase with health + ring, this week's focus, what changed this week, open questions,
 *  manuscripts at a glance, counts, next milestones, recent documents and decisions.
 *  Data: GET /projects/{slug}/overview/ (also the MCP get_project_overview tool). */
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { Activity, Archive, ArchiveRestore, BookOpen, FileText, FlaskConical, HelpCircle, PenLine, Settings2, Trash2 } from "lucide-react";
import { api } from "../api";
import { Skeleton, SkeletonCard } from "../../components/Skeleton";
import { ErrorState } from "../../components/ErrorState";
import { confirmDialog, errorDialog } from "../../components/Dialog";
import { Kebab } from "../../components/Menu";
import Focus, { type FocusData } from "./plan/Focus";
import Constellation from "./project/Constellation";

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
  themes?: { label: string; weight: number }[];
  week_digest: { since: string; total: number; counts: { kind: string; label: string; count: number }[]; items: { date: string; kind: string; label: string; detail: string; url: string }[] };
  questions: { id: number; question: string; status: string; phases: string[] }[];
  manuscripts: { id: number; title: string; status: string; deadline: string | null; days: number | null; target_venue: string; over: string[] }[];
  hypotheses: { total: number; by_status: Record<string, number> };
};

const panel = "rounded-2xl border border-stone-200 bg-white dark:border-stone-800 dark:bg-stone-900";
const h2 = "mb-2 flex items-baseline gap-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-stone-400 dark:text-stone-500";
const quickLinks = [["plan", "Plan"], ["literature", "Literature"], ["documents", "Documents"], ["figures", "Figures"], ["files", "Files"], ["notes", "Notes"], ["research", "Research"], ["decisions", "Decisions"], ["graph", "Graph"], ["matrix", "Matrix"], ["review", "Review"], ["timeline", "Timeline"]] as const;
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
const PROJECT_STATUSES = [["planning", "Planning"], ["active", "Active"], ["paused", "Paused"], ["complete", "Complete"], ["archived", "Archived"]] as const;
const field = "w-full rounded-lg border border-stone-300 bg-white px-3 py-1.5 text-sm text-stone-900 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 dark:border-stone-700 dark:bg-stone-950 dark:text-stone-100";

/** Project CRUD lives here (owner report 2026-09-06: "I made a project to test, now I can't
 * delete it"). Every field of the project is editable in place; archive is one click and
 * reversible; delete asks for the project's name and takes everything inside it with it. */
export function useProjectActions(slug: string, name: string, status: string) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const refresh = () => { queryClient.invalidateQueries({ queryKey: ["overview", slug] }); queryClient.invalidateQueries({ queryKey: ["projects"] }); queryClient.invalidateQueries({ queryKey: ["dashboard"] }); };
  const patch = useMutation({
    mutationFn: (body: Record<string, unknown>) => api(`/projects/${slug}/`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
    onSuccess: refresh,
    onError: (e) => void errorDialog("Couldn't save the project", e),
  });
  const remove = useMutation({
    mutationFn: () => api(`/projects/${slug}/`, { method: "DELETE" }),
    onSuccess: () => { queryClient.removeQueries({ queryKey: ["overview", slug] }); queryClient.invalidateQueries(); navigate("/projects"); },
    onError: (e) => void errorDialog("Couldn't delete the project", e),
  });
  const archived = status === "archived";
  const toggleArchive = () => patch.mutate({ status: archived ? "active" : "archived" });
  const confirmDelete = async () => {
    const ok = await confirmDialog({ title: `Delete “${name}”?`, danger: true, confirmLabel: "Delete project", verify: name, body: <>This removes the project and <b>everything inside it</b>: its plan, documents, notes, manuscripts, decisions and research. Library references stay in the library. This cannot be undone.</> });
    if (ok) remove.mutate();
  };
  return { patch, remove, archived, toggleArchive, confirmDelete };
}

function ProjectSettings({ project, onClose }: { project: Overview["project"]; onClose: () => void }) {
  const { patch, archived, toggleArchive, confirmDelete } = useProjectActions(project.slug, project.name, project.status);
  const [name, setName] = useState(project.name);
  const [description, setDescription] = useState(project.description);
  const [status, setStatus] = useState(project.status);
  const [color, setColor] = useState(project.color);
  useEffect(() => { setName(project.name); setDescription(project.description); setStatus(project.status); setColor(project.color); }, [project]);
  const dirty = name !== project.name || description !== project.description || status !== project.status || color !== project.color;
  return (
    <form onSubmit={(e) => { e.preventDefault(); if (name.trim()) patch.mutate({ name: name.trim(), description, status, color }, { onSuccess: onClose }); }} className={`${panel} rise mb-5 p-4`} style={{ ["--i" as string]: 0 }} data-testid="project-settings">
      <p className={h2}><Settings2 className="h-3 w-3" aria-hidden="true" />Project settings</p>
      <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_10rem_5rem]">
        <label className="block text-xs text-stone-500"><span className="mb-1 block">Name</span><input value={name} onChange={(e) => setName(e.target.value)} className={field} required aria-label="Project name" /></label>
        <label className="block text-xs text-stone-500"><span className="mb-1 block">Status</span><select value={status} onChange={(e) => setStatus(e.target.value)} className={field} aria-label="Project status">{PROJECT_STATUSES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}</select></label>
        <label className="block text-xs text-stone-500"><span className="mb-1 block">Accent</span><input type="color" value={color} onChange={(e) => setColor(e.target.value)} className="h-8 w-full cursor-pointer rounded-lg border border-stone-300 bg-white p-0.5 dark:border-stone-700 dark:bg-stone-950" aria-label="Accent color" /></label>
      </div>
      <label className="mt-3 block text-xs text-stone-500"><span className="mb-1 block">Description <span className="text-stone-400">· Markdown</span></span><textarea value={description} onChange={(e) => setDescription(e.target.value)} rows={3} className={field} aria-label="Project description" /></label>
      <div className="mt-3 flex flex-wrap items-center gap-2">
        <button type="submit" disabled={!dirty || !name.trim() || patch.isPending} className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-40">{patch.isPending ? "Saving…" : "Save changes"}</button>
        <button type="button" onClick={onClose} className="rounded-lg border border-stone-300 px-3 py-1.5 text-sm text-stone-600 hover:border-stone-400 dark:border-stone-700 dark:text-stone-300">Close</button>
        <span className="ml-auto flex flex-wrap items-center gap-2 text-xs">
          <button type="button" onClick={toggleArchive} className="inline-flex items-center gap-1 rounded-lg border border-stone-300 px-2.5 py-1.5 text-stone-600 hover:border-stone-400 dark:border-stone-700 dark:text-stone-300" data-testid="archive-project">{archived ? <ArchiveRestore className="h-3.5 w-3.5" aria-hidden="true" /> : <Archive className="h-3.5 w-3.5" aria-hidden="true" />}{archived ? "Unarchive" : "Archive"}</button>
          <button type="button" onClick={() => void confirmDelete()} className="inline-flex items-center gap-1 rounded-lg border border-red-300/70 px-2.5 py-1.5 text-red-600 hover:bg-red-500/10 dark:border-red-500/40 dark:text-red-300" data-testid="delete-project"><Trash2 className="h-3.5 w-3.5" aria-hidden="true" />Delete project…</button>
        </span>
      </div>
    </form>
  );
}

function when(days: number | null): string { if (days == null) return "no deadline"; if (days < 0) return `${-days} d overdue`; if (days === 0) return "due today"; return `${days} d left`; }

export default function ProjectOverview() {
  const { slug } = useParams();
  const { data, isLoading, error, refetch } = useQuery({ queryKey: ["overview", slug], queryFn: () => api<Overview>(`/projects/${slug}/overview/`) });
  const [searchParams] = useSearchParams();
  const [settingsOpen, setSettingsOpen] = useState(searchParams.get("settings") === "1");
  const actions = useProjectActions(slug ?? "", data?.project.name ?? "", data?.project.status ?? "");
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
            <span className="ml-auto flex items-center gap-1">
              <button type="button" onClick={() => setSettingsOpen((v) => !v)} className={`inline-flex items-center gap-1 rounded-lg border px-2 py-1 text-xs transition-colors ${settingsOpen ? "border-indigo-300 text-indigo-700 dark:border-indigo-500/50 dark:text-indigo-200" : "border-stone-200 text-stone-500 hover:border-stone-300 hover:text-stone-800 dark:border-stone-700 dark:text-stone-400 dark:hover:text-stone-100"}`} data-testid="project-settings-toggle" aria-expanded={settingsOpen}><Settings2 className="h-3.5 w-3.5" aria-hidden="true" />Settings</button>
              <Kebab label="Project actions" items={[
                { label: settingsOpen ? "Close settings" : "Edit project…", icon: <Settings2 className="h-3.5 w-3.5" />, onSelect: () => setSettingsOpen((v) => !v) },
                { label: "Export as Markdown vault", icon: <FileText className="h-3.5 w-3.5" />, onSelect: () => { window.location.assign(`/api/v1/projects/${project.slug}/vault/`); } },
                { label: actions.archived ? "Unarchive" : "Archive project", icon: actions.archived ? <ArchiveRestore className="h-3.5 w-3.5" /> : <Archive className="h-3.5 w-3.5" />, onSelect: actions.toggleArchive },
                "-",
                { label: "Delete project…", icon: <Trash2 className="h-3.5 w-3.5" />, danger: true, onSelect: () => void actions.confirmDelete() },
              ]} />
            </span>
          </div>
          {project.description && <p className="mt-1 max-w-2xl text-sm leading-relaxed text-stone-500 dark:text-stone-400">{plain(project.description)}</p>}
          <nav className="mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs text-stone-400">
            {quickLinks.map(([to, label]) => <Link key={to} to={`/projects/${project.slug}/${to}`} className="transition-colors hover:text-indigo-700 dark:hover:text-indigo-300">{label}</Link>)}
          </nav>
        </div>
      </header>
      <Constellation slug={project.slug} accent={accent} />
      {settingsOpen && <ProjectSettings project={project} onClose={() => setSettingsOpen(false)} />}

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

      {data.themes && data.themes.length > 0 && (
        <p className="mt-3 flex flex-wrap items-center gap-1.5" data-testid="themes" aria-label="Themes across this project">
          <span className="mr-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-stone-400">Themes</span>
          {data.themes.map((t) => (
            <Link key={t.label} to={`/search?q=${encodeURIComponent(t.label)}`} title={`${t.weight} source${t.weight === 1 ? "" : "s"} mention this — search for it`}
                  className="rounded-full border border-stone-200 bg-white px-2 py-0.5 text-xs text-stone-600 transition-colors hover:border-indigo-300 hover:text-indigo-700 dark:border-stone-700 dark:bg-stone-900 dark:text-stone-300 dark:hover:text-indigo-300"
                  style={{ fontSize: `${Math.min(15, 11 + t.weight)}px`, opacity: 0.7 + Math.min(0.3, t.weight * 0.06) }}>
              {t.label}
            </Link>
          ))}
        </p>
      )}

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
