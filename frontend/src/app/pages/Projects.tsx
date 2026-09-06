/* Projects index (UI audit 2026-09-06): every card answers "where is what, and how is it
 * going?" — accent, status, current phase with its progress bar, health, counts — grouped so
 * active work sits first and archived projects fold away. Descriptions render as plain text
 * (they are Markdown) instead of leaking asterisks. */
import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { BookOpen, ChevronDown, FileText, FolderKanban, PenLine, Plus, StickyNote } from "lucide-react";
import { ErrorState } from "../../components/ErrorState";
import { api } from "../api";

type Summary = { current_phase: string | null; phase_progress: number | null; milestones_done: number; milestones_total: number; percent: number; health: { state: string; label: string } | null; counts: { papers: number; notes: number; manuscripts: number; documents: number } };
type Project = { name: string; slug: string; status: string; description: string; color: string; updated_at: string; summary: Summary };
type Page<T> = { count: number; results: T[] };

const ORDER = ["active", "planning", "paused", "complete", "archived"];
const STATUS: Record<string, { label: string; cls: string }> = {
  active: { label: "active", cls: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300" },
  planning: { label: "planning", cls: "bg-indigo-500/15 text-indigo-700 dark:text-indigo-300" },
  paused: { label: "paused", cls: "bg-amber-500/15 text-amber-700 dark:text-amber-300" },
  complete: { label: "complete", cls: "bg-stone-500/15 text-stone-600 dark:text-stone-300" },
  archived: { label: "archived", cls: "bg-stone-500/10 text-stone-500" },
};
const HEALTH: Record<string, string> = {
  behind: "bg-amber-500/15 text-amber-700 dark:text-amber-300",
  overdue: "bg-red-500/15 text-red-700 dark:text-red-300",
  blocked: "bg-red-500/15 text-red-700 dark:text-red-300",
  on_track: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300",
  ahead: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300",
  upcoming: "bg-indigo-500/15 text-indigo-700 dark:text-indigo-300",
  done: "bg-stone-500/15 text-stone-600 dark:text-stone-300",
};
const stripMd = (s: string) => s.replace(/[*_`#>]+/g, "").replace(/\[([^\]]+)\]\([^)]*\)/g, "$1").replace(/\s+/g, " ").trim();
const panel = "rounded-2xl border border-stone-200 bg-white/70 backdrop-blur dark:border-stone-800 dark:bg-stone-900/60";

export default function Projects() {
  const { data, isLoading, error, refetch } = useQuery({ queryKey: ["projects"], queryFn: () => api<Page<Project>>("/projects/?page_size=100") });
  const [showArchived, setShowArchived] = useState(false);
  const groups = useMemo(() => {
    const by = new Map<string, Project[]>();
    for (const p of data?.results ?? []) { const k = p.status.toLowerCase(); by.set(k, [...(by.get(k) ?? []), p]); }
    return ORDER.filter((k) => by.has(k)).map((k) => ({ status: k, rows: by.get(k)! }));
  }, [data]);

  if (isLoading) return <p className="text-sm text-stone-400">Loading projects…</p>;
  if (error || !data) return <ErrorState message="Couldn't load projects." onRetry={() => refetch()} />;
  const projects = data.results;
  const active = projects.filter((p) => p.status.toLowerCase() === "active").length;

  return (
    <div>
      <div className="mb-6 flex items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">Projects{projects.length > 0 && <> · <span className="text-gradient">{active} active</span></>}</h1>
          <p className="mt-1 text-sm text-stone-500">{projects.length === 0 ? "Every object in Atlas lives inside a project." : `${projects.length} ${projects.length === 1 ? "project" : "projects"} · each one holds its plan, library, notes, writing and decisions`}</p>
        </div>
        <Link to="/projects/new" className="inline-flex shrink-0 items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-indigo-700"><Plus className="h-4 w-4" aria-hidden="true" />New project</Link>
      </div>

      {projects.length === 0 && (
        <div className={`${panel} p-12 text-center`}>
          <FolderKanban className="mx-auto mb-3 h-8 w-8 text-stone-300" aria-hidden="true" />
          <p className="mb-1 font-medium">No projects yet</p>
          <p className="mx-auto mb-5 max-w-md text-sm text-stone-500">A project is the home for a plan, its literature, notes, manuscripts and decisions. Start with a scaffold or a blank one.</p>
          <Link to="/projects/new" className="inline-block rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700">Create your first project</Link>
        </div>
      )}

      {groups.map((g, gi) => {
        const folded = g.status === "archived" && !showArchived;
        return (
          <section key={g.status} className="mb-7" data-testid={`projects-${g.status}`}>
            <div className="mb-2 flex items-center gap-2">
              <h2 className="text-[11px] font-semibold uppercase tracking-wider text-stone-400">{STATUS[g.status]?.label ?? g.status} <span className="normal-case tracking-normal">{g.rows.length}</span></h2>
              {g.status === "archived" && <button type="button" onClick={() => setShowArchived((v) => !v)} className="inline-flex items-center gap-0.5 text-[11px] text-stone-400 hover:text-stone-600 dark:hover:text-stone-200"><ChevronDown className={`h-3 w-3 transition-transform ${folded ? "-rotate-90" : ""}`} aria-hidden="true" />{folded ? "show" : "hide"}</button>}
            </div>
            {!folded && (
              <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-3">
                {g.rows.map((p, i) => <ProjectCard key={p.slug} p={p} i={gi * 6 + i} />)}
              </div>
            )}
          </section>
        );
      })}
    </div>
  );
}

function ProjectCard({ p, i }: { p: Project; i: number }) {
  const s = p.summary;
  const desc = stripMd(p.description || "");
  const pct = s.milestones_total ? Math.round((s.milestones_done / s.milestones_total) * 100) : 0;
  return (
    <Link to={`/projects/${p.slug}`} className={`${panel} rise group relative flex flex-col overflow-hidden p-5 pl-6 transition-colors hover:border-indigo-300 dark:hover:border-indigo-500/50`} style={{ ["--i" as string]: i + 1 }} data-testid="project-card">
      <span aria-hidden="true" className="absolute inset-y-0 left-0 w-1" style={{ background: p.color }} />
      <div className="mb-1.5 flex items-start justify-between gap-3">
        <h3 className="min-w-0 truncate text-base font-semibold tracking-tight group-hover:text-indigo-600 dark:group-hover:text-indigo-300">{p.name}</h3>
        <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${STATUS[p.status.toLowerCase()]?.cls ?? "bg-stone-500/10 text-stone-500"}`}>{STATUS[p.status.toLowerCase()]?.label ?? p.status.toLowerCase()}</span>
      </div>
      {desc ? <p className="line-clamp-2 text-sm leading-relaxed text-stone-500">{desc}</p> : <p className="text-sm italic text-stone-400">No description yet.</p>}
      <div className="mt-4">
        {s.current_phase ? (
          <>
            <div className="mb-1 flex items-center justify-between gap-2 text-xs">
              <span className="min-w-0 truncate text-stone-600 dark:text-stone-300"><span className="text-stone-400">now · </span>{s.current_phase}</span>
              {s.health && <span className={`shrink-0 rounded-full px-1.5 py-0.5 text-[10px] font-medium ${HEALTH[s.health.state] ?? "bg-stone-500/10 text-stone-500"}`} title={s.health.label}>{s.health.state.replace("_", " ")}</span>}
            </div>
            <div className="h-1.5 overflow-hidden rounded-full bg-stone-200 dark:bg-stone-800"><div className="h-full rounded-full transition-all" style={{ width: `${pct}%`, background: p.color }} /></div>
            <p className="mt-1 text-[11px] text-stone-400">{s.milestones_done}/{s.milestones_total} milestones across the plan</p>
          </>
        ) : (
          <p className="text-[11px] text-stone-400">{s.milestones_total ? `${s.milestones_done}/${s.milestones_total} milestones · every phase done` : "No plan yet — open the project to write one."}</p>
        )}
      </div>
      <div className="mt-3 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-stone-400">
        <span className="inline-flex items-center gap-1" title="papers"><BookOpen className="h-3 w-3" aria-hidden="true" />{s.counts.papers}</span>
        <span className="inline-flex items-center gap-1" title="notes"><StickyNote className="h-3 w-3" aria-hidden="true" />{s.counts.notes}</span>
        <span className="inline-flex items-center gap-1" title="manuscripts"><PenLine className="h-3 w-3" aria-hidden="true" />{s.counts.manuscripts}</span>
        <span className="inline-flex items-center gap-1" title="documents"><FileText className="h-3 w-3" aria-hidden="true" />{s.counts.documents}</span>
        <span className="ml-auto">updated {new Date(p.updated_at).toLocaleDateString([], { month: "short", day: "numeric" })}</span>
      </div>
    </Link>
  );
}
