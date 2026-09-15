/* Projects index (UI audit 2026-09-06): every card answers "where is what, and how is it
 * going?" — accent, status, current phase with its progress bar, health, counts — grouped so
 * active work sits first and archived projects fold away. Descriptions render as plain text
 * (they are Markdown) instead of leaking asterisks. */
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "react-router-dom";
import { Archive, ArchiveRestore, BookOpen, ChevronDown, FileText, FolderInput, FolderKanban, ListTodo, PenLine, Plus, Settings2, StickyNote, Trash2 } from "lucide-react";
import { ErrorState } from "../../components/ErrorState";
import { confirmDialog, errorDialog } from "../../components/Dialog";
import { Kebab, useMenu, type MenuItem } from "../../components/Menu";
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
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const menu = useMenu();
  const patch = useMutation({
    mutationFn: ({ slug, ...body }: { slug: string; status?: string }) => api(`/projects/${slug}/`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["projects"] }),
    onError: (e) => void errorDialog("Couldn't update the project", e),
  });
  const remove = useMutation({
    mutationFn: (slug: string) => api(`/projects/${slug}/`, { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries(),
    onError: (e) => void errorDialog("Couldn't delete the project", e),
  });
  // right-click or ⋯ on a card: the same actions the project overview offers (CRUD everywhere)
  const itemsFor = (p: Project): MenuItem[] => {
    const archived = p.status.toLowerCase() === "archived";
    return [
      { label: "Open", icon: <FolderKanban className="h-3.5 w-3.5" />, onSelect: () => navigate(`/projects/${p.slug}`) },
      { label: "Open the plan", icon: <ListTodo className="h-3.5 w-3.5" />, onSelect: () => navigate(`/projects/${p.slug}/plan`) },
      { label: "Edit project…", icon: <Settings2 className="h-3.5 w-3.5" />, onSelect: () => navigate(`/projects/${p.slug}?settings=1`) },
      "-",
      { label: archived ? "Unarchive" : "Archive", icon: archived ? <ArchiveRestore className="h-3.5 w-3.5" /> : <Archive className="h-3.5 w-3.5" />, onSelect: () => patch.mutate({ slug: p.slug, status: archived ? "active" : "archived" }) },
      { label: "Delete project…", icon: <Trash2 className="h-3.5 w-3.5" />, danger: true, onSelect: async () => { if (await confirmDialog({ title: `Delete “${p.name}”?`, danger: true, confirmLabel: "Delete project", verify: p.name, body: <>Everything inside it goes too: plan, documents, notes, manuscripts, decisions, research. Library references stay. This cannot be undone.</> })) remove.mutate(p.slug); } },
    ];
  };
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
        <div className="flex shrink-0 items-center gap-2">
          <Link to="/projects/import" className="inline-flex items-center gap-1.5 rounded-lg border border-stone-300 px-3 py-1.5 text-sm text-stone-700 transition-colors hover:border-stone-400 dark:border-stone-700 dark:text-stone-200 dark:hover:border-stone-500" data-testid="import-folder-link"><FolderInput className="h-4 w-4" aria-hidden="true" />Import a folder…</Link>
          <Link to="/projects/new" className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-indigo-700"><Plus className="h-4 w-4" aria-hidden="true" />New project</Link>
        </div>
      </div>

      {projects.length === 0 && (
        <div className={`${panel} p-12 text-center`}>
          <FolderKanban className="mx-auto mb-3 h-8 w-8 text-stone-300" aria-hidden="true" />
          <p className="mb-1 font-medium">No projects yet</p>
          <p className="mx-auto mb-5 max-w-md text-sm text-stone-500">A project is the home for a plan, its literature, notes, manuscripts and decisions. Start with a scaffold or a blank one.</p>
          <Link to="/projects/new" className="inline-block rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700">Create your first project</Link>
          <p className="mt-3 text-xs text-stone-400">Already have projects as folders on disk? <Link to="/projects/import" className="text-indigo-600 hover:underline dark:text-indigo-300">Import the whole folder</Link> — every subfolder becomes a project.</p>
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
                {g.rows.map((p, i) => <ProjectCard key={p.slug} p={p} i={gi * 6 + i} items={itemsFor(p)} onContextMenu={(e) => menu.open(e, itemsFor(p))} />)}
              </div>
            )}
          </section>
        );
      })}
      {menu.element}
    </div>
  );
}

function ProjectCard({ p, i, items, onContextMenu }: { p: Project; i: number; items: MenuItem[]; onContextMenu: (e: React.MouseEvent) => void }) {
  const qc = useQueryClient(); // #448: prefetch the overview on hover
  const s = p.summary;
  const desc = stripMd(p.description || "");
  const pct = s.milestones_total ? Math.round((s.milestones_done / s.milestones_total) * 100) : 0;
  return (
    <Link to={`/projects/${p.slug}`} onContextMenu={onContextMenu} onMouseEnter={() => void qc.prefetchQuery({ queryKey: ["overview", p.slug], queryFn: () => api(`/projects/${p.slug}/overview/`), staleTime: 30_000 })} className={`${panel} rise group relative flex flex-col overflow-hidden p-5 pl-6 transition-colors hover:border-indigo-300 dark:hover:border-indigo-500/50`} style={{ ["--i" as string]: i + 1 }} data-testid="project-card">
      <span aria-hidden="true" className="absolute inset-y-0 left-0 w-1" style={{ background: p.color }} />
      <div className="mb-1.5 flex items-start justify-between gap-2">
        <h3 className="min-w-0 truncate text-base font-semibold tracking-tight group-hover:text-indigo-600 dark:group-hover:text-indigo-300">{p.name}</h3>
        <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] font-semibold uppercase tracking-wide ${STATUS[p.status.toLowerCase()]?.cls ?? "bg-stone-500/10 text-stone-500"}`}>{STATUS[p.status.toLowerCase()]?.label ?? p.status.toLowerCase()}</span>
        <Kebab items={items} label={`Actions for ${p.name}`} className="-mr-1 -mt-0.5 opacity-0 group-hover:opacity-100 focus:opacity-100" />
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
