/** Research tools: hypothesis ledger, experiment log, datasets (SPA slice 9). */
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";

type Hypothesis = { id: number; statement: string; status: string; supports: number; contradicts: number };
type Experiment = { id: number; date: string; title: string; body: string; commit_url: string; commit_label: string };
type Dataset = { id: number; name: string; location: string; version: string; description: string };
type Page<T> = { count: number; results: T[] };

const statusCls: Record<string, string> = {
  supported: "bg-green-50 text-green-700",
  contradicted: "bg-red-50 text-red-700",
  testing: "bg-indigo-50 text-indigo-700",
  proposed: "bg-stone-100 text-stone-600",
  inconclusive: "bg-amber-50 text-amber-700",
  abandoned: "bg-stone-100 text-stone-400",
};

export default function Research() {
  const { slug } = useParams();
  const { data: hypotheses } = useQuery({
    queryKey: ["hypotheses", slug],
    queryFn: () => api<Page<Hypothesis>>(`/hypotheses/?project=${slug}`),
  });
  const { data: experiments } = useQuery({
    queryKey: ["experiments", slug],
    queryFn: () => api<Page<Experiment>>(`/experiments/?project=${slug}`),
  });
  const { data: datasets } = useQuery({
    queryKey: ["datasets", slug],
    queryFn: () => api<Page<Dataset>>(`/datasets/?project=${slug}`),
  });

  return (
    <div>
      <nav className="mb-6 text-sm text-stone-500">
        <Link to="/projects" className="hover:underline">Projects</Link> /{" "}
        <Link to={`/projects/${slug}`} className="hover:underline">{slug}</Link> / Research
      </nav>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Research</h1>
        <a href={`/projects/${slug}/research/`} className="text-xs text-stone-400 underline hover:text-indigo-700">
          add & edit on the classic page ↗
        </a>
      </div>

      <section className="mb-6 rounded border border-stone-200 bg-white p-5">
        <h2 className="mb-3 text-sm font-medium uppercase tracking-wide text-stone-400">Hypothesis ledger</h2>
        <ul className="space-y-3">
          {(hypotheses?.results ?? []).map((h) => (
            <li key={h.id} className="flex items-start gap-3 text-sm">
              <span className={`mt-0.5 shrink-0 rounded px-2 py-0.5 text-xs ${statusCls[h.status] ?? statusCls.proposed}`}>
                {h.status}
              </span>
              <span className="min-w-0 flex-1">{h.statement}</span>
              <span className="shrink-0 text-xs text-stone-400">
                {h.supports} supports · {h.contradicts} contradicts
              </span>
            </li>
          ))}
          {hypotheses?.results.length === 0 && <li className="text-sm text-stone-400">No hypotheses yet.</li>}
        </ul>
      </section>

      <div className="grid grid-cols-2 gap-4">
        <section className="rounded border border-stone-200 bg-white p-5">
          <h2 className="mb-3 text-sm font-medium uppercase tracking-wide text-stone-400">Experiment log</h2>
          <ul className="space-y-2">
            {(experiments?.results ?? []).map((e) => (
              <li key={e.id} className="text-sm">
                <span className="font-medium">{e.title}</span>
                <span className="ml-2 text-xs text-stone-400">{e.date}</span>
                {e.commit_url && (
                  <a href={e.commit_url} target="_blank" rel="noopener"
                     className="ml-2 font-mono text-xs text-indigo-600 hover:underline" title={e.commit_url}>
                    ⎇ {e.commit_label}
                  </a>
                )}
                {e.body && <p className="mt-0.5 line-clamp-2 text-xs text-stone-500">{e.body}</p>}
              </li>
            ))}
            {experiments?.results.length === 0 && <li className="text-sm text-stone-400">No entries yet.</li>}
          </ul>
        </section>
        <section className="rounded border border-stone-200 bg-white p-5">
          <h2 className="mb-3 text-sm font-medium uppercase tracking-wide text-stone-400">Datasets</h2>
          <ul className="space-y-2">
            {(datasets?.results ?? []).map((d) => (
              <li key={d.id} className="text-sm">
                <span className="font-medium">{d.name}</span>
                {d.version && <span className="ml-2 text-xs text-stone-400">v{d.version}</span>}
                <p className="mt-0.5 font-mono text-xs text-stone-500">{d.location}</p>
              </li>
            ))}
            {datasets?.results.length === 0 && <li className="text-sm text-stone-400">No datasets registered.</li>}
          </ul>
        </section>
      </div>
    </div>
  );
}
