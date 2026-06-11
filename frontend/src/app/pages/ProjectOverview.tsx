import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";

type Overview = {
  project: { name: string; slug: string; description: string; status: string; color: string };
  current_phase: { name: string; status: string } | null;
  progress: { done: number; total: number; percent: number };
  next_milestones: { id: number; title: string; due_date: string | null; overdue: boolean; phase: string }[];
  counts: Record<string, number>;
  recent_documents: { id: number; title: string; added: string; url: string }[];
  recent_decisions: { id: number; title: string; decided_on: string }[];
};

const section = "rounded border border-stone-200 bg-white p-5";
const h2 = "mb-3 text-sm font-medium uppercase tracking-wide text-stone-400";

export default function ProjectOverview() {
  const { slug } = useParams();
  const { data, isLoading, error } = useQuery({
    queryKey: ["overview", slug],
    queryFn: () => api<Overview>(`/projects/${slug}/overview/`),
  });

  if (isLoading) return <p className="text-sm text-stone-400">Loading project…</p>;
  if (error || !data) return <p className="text-sm text-red-600">Couldn't load this project.</p>;
  const { project, progress } = data;

  return (
    <div>
      <nav className="mb-6 text-sm text-stone-500">
        <Link to="/projects" className="hover:underline">Projects</Link> / {project.name}
      </nav>

      <div className="mb-1 flex items-center gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">{project.name}</h1>
        <span className="rounded bg-stone-100 px-2 py-0.5 text-xs text-stone-500">{project.status}</span>
      </div>
      {project.description && <p className="mb-4 max-w-2xl text-sm text-stone-500">{project.description}</p>}

      <div className="mb-4 rounded border border-stone-200 bg-white p-5">
        <div className="mb-1 flex items-baseline justify-between text-sm">
          <span className="font-medium">
            {data.current_phase ? data.current_phase.name : "No phases yet"}
          </span>
          <span className="text-xs text-stone-400">{progress.done}/{progress.total} milestones</span>
        </div>
        <div className="h-1.5 w-full rounded-full bg-stone-100">
          <div className="h-1.5 rounded-full" style={{ width: `${progress.percent}%`, background: project.color }} />
        </div>
        <div className="mt-3 flex gap-4 text-xs text-stone-400">
          <Link to={`/projects/${project.slug}/plan`} className="hover:text-indigo-700">Open plan</Link>
          <Link to={`/projects/${project.slug}/literature`} className="hover:text-indigo-700">Literature</Link>
          <Link to={`/projects/${project.slug}/documents`} className="hover:text-indigo-700">Documents</Link>
          <Link to={`/projects/${project.slug}/notes`} className="hover:text-indigo-700">Notes</Link>
          <Link to={`/projects/${project.slug}/research`} className="hover:text-indigo-700">Research</Link>
          <Link to={`/projects/${project.slug}/decisions`} className="hover:text-indigo-700">Decisions</Link>
          <Link to={`/projects/${project.slug}/graph`} className="hover:text-indigo-700">Graph</Link>
          <Link to={`/projects/${project.slug}/review`} className="hover:text-indigo-700">Review</Link>
          <Link to={`/projects/${project.slug}/timeline`} className="hover:text-indigo-700">Timeline</Link>
        </div>
      </div>

      <div className="mb-4 grid grid-cols-4 gap-4 lg:grid-cols-7">
        {Object.entries(data.counts).map(([key, value]) => (
          <div key={key} className="rounded border border-stone-200 bg-white px-3 py-2 text-center">
            <p className="text-lg font-semibold">{value}</p>
            <p className="text-[10px] uppercase tracking-wide text-stone-400">{key}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-2 gap-4">
        <section className={section}>
          <h2 className={h2}>Next milestones</h2>
          <ul className="space-y-2 text-sm">
            {data.next_milestones.map((m) => (
              <li key={m.id} className="flex items-baseline gap-2">
                <span aria-hidden="true">◆</span>
                <span className="min-w-0 flex-1 truncate">{m.title}</span>
                {m.due_date && (
                  <span className={`shrink-0 text-xs ${m.overdue ? "font-medium text-red-600" : "text-stone-400"}`}>
                    {m.due_date}{m.overdue ? " · overdue" : ""}
                  </span>
                )}
              </li>
            ))}
            {data.next_milestones.length === 0 && <li className="text-stone-400">All caught up.</li>}
          </ul>
        </section>

        <div className="space-y-4">
          <section className={section}>
            <h2 className={h2}>Recent documents</h2>
            <ul className="space-y-1.5 text-sm">
              {data.recent_documents.map((d) => (
                <li key={d.id} className="flex items-baseline gap-2">
                  <a href={d.url} className="min-w-0 flex-1 truncate hover:text-indigo-700">{d.title}</a>
                  <span className="shrink-0 text-xs text-stone-400">{d.added}</span>
                </li>
              ))}
              {data.recent_documents.length === 0 && <li className="text-stone-400">Nothing uploaded yet.</li>}
            </ul>
          </section>
          <section className={section}>
            <h2 className={h2}>Recent decisions</h2>
            <ul className="space-y-1.5 text-sm">
              {data.recent_decisions.map((d) => (
                <li key={d.id} className="flex items-baseline gap-2">
                  <span className="min-w-0 flex-1 truncate">{d.title}</span>
                  <span className="shrink-0 text-xs text-stone-400">{d.decided_on}</span>
                </li>
              ))}
              {data.recent_decisions.length === 0 && <li className="text-stone-400">No decisions recorded.</li>}
            </ul>
          </section>
        </div>
      </div>
    </div>
  );
}
