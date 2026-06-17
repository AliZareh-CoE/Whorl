/** Research tools: hypothesis ledger, experiment log, datasets (SPA slice 9). */
import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";

type Hypothesis = { id: number; statement: string; status: string; supports: number; contradicts: number };
type Experiment = { id: number; date: string; title: string; body: string; commit_url: string; commit_label: string };
type Dataset = { id: number; name: string; location: string; version: string; description: string };
type Protocol = { id: number; title: string; version: number; is_current: boolean };
type Page<T> = { count: number; results: T[] };

const statusCls: Record<string, string> = {
  supported: "bg-green-50 text-green-700 dark:bg-green-500/10 dark:text-green-300",
  contradicted: "bg-red-50 text-red-700 dark:bg-red-500/10 dark:text-red-300",
  testing: "bg-indigo-50 text-indigo-700 dark:bg-indigo-500/10 dark:text-indigo-300",
  proposed: "bg-stone-100 text-stone-600 dark:bg-stone-800 dark:text-stone-300",
  inconclusive: "bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300",
  abandoned: "bg-stone-100 text-stone-400 dark:bg-stone-800 dark:text-stone-400",
};

function SectionCard({ title, count, children }: {
  title: string; count: number; children: React.ReactNode;
}) {
  return (
    <section className="rounded border border-stone-200 bg-white p-5 dark:border-stone-800 dark:bg-stone-900">
      <h2 className="mb-3 flex items-baseline gap-2 text-sm font-medium uppercase tracking-wide text-stone-400 dark:text-stone-400">
        {title}
        {count > 0 && <span className="text-stone-300 dark:text-stone-400">{count}</span>}
      </h2>
      {children}
    </section>
  );
}

function Empty({ children }: { children: React.ReactNode }) {
  return <p className="text-sm text-stone-400 dark:text-stone-400">{children}</p>;
}

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
  const { data: protocols } = useQuery({
    queryKey: ["protocols", slug],
    queryFn: () => api<Page<Protocol>>(`/protocols/?project=${slug}`),
  });
  const currentProtocols = (protocols?.results ?? []).filter((p) => p.is_current);

  const hyps = hypotheses?.results ?? [];
  const exps = experiments?.results ?? [];
  const dsets = datasets?.results ?? [];
  const classic = `/projects/${slug}/research/`;

  return (
    <div>
      <nav className="mb-6 text-sm text-stone-500 dark:text-stone-400">
        <Link to="/projects" className="transition-colors hover:underline">Projects</Link> /{" "}
        <Link to={`/projects/${slug}`} className="transition-colors hover:underline">{slug}</Link> / Research
      </nav>
      <div className="mb-6 flex items-baseline justify-between gap-4">
        <h1 className="text-2xl font-semibold tracking-tight text-stone-900 dark:text-stone-100">Research</h1>
        <a href={classic} className="shrink-0 text-xs text-stone-400 underline-offset-2 transition-colors hover:text-indigo-700 hover:underline dark:text-stone-400 dark:hover:text-indigo-300">
          add &amp; edit on the classic page ↗
        </a>
      </div>

      <section className="mb-4 rounded border border-stone-200 bg-white p-5 dark:border-stone-800 dark:bg-stone-900">
        <h2 className="mb-3 flex items-baseline gap-2 text-sm font-medium uppercase tracking-wide text-stone-400 dark:text-stone-400">
          Hypothesis ledger
          {hyps.length > 0 && <span className="text-stone-300 dark:text-stone-400">{hyps.length}</span>}
        </h2>
        {hyps.length === 0 ? (
          <Empty>
            No hypotheses yet — <a href={classic} className="text-indigo-600 hover:underline dark:text-indigo-400 dark:hover:text-indigo-300">propose one</a> on the classic page.
          </Empty>
        ) : (
          <ul className="divide-y divide-stone-100 dark:divide-stone-800">
            {hyps.map((h) => (
              <li key={h.id} className="flex items-start gap-3 py-2.5 text-sm first:pt-0 last:pb-0">
                <span className={`mt-px shrink-0 rounded px-2 py-0.5 text-xs ${statusCls[h.status] ?? statusCls.proposed}`}>
                  {h.status}
                </span>
                <span className="min-w-0 flex-1 leading-relaxed text-stone-700 dark:text-stone-300">{h.statement}</span>
                <span className="shrink-0 pt-0.5 text-xs tabular-nums text-stone-400 dark:text-stone-400">
                  <span className="text-green-700 dark:text-green-300">+{h.supports}</span> · <span className="text-red-700 dark:text-red-300">−{h.contradicts}</span>
                </span>
              </li>
            ))}
          </ul>
        )}
      </section>

      <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
        <SectionCard title="Experiment log" count={exps.length}>
          {exps.length === 0 ? (
            <Empty>
              No entries yet — <a href={classic} className="text-indigo-600 hover:underline dark:text-indigo-400 dark:hover:text-indigo-300">log an experiment</a>.
            </Empty>
          ) : (
            <ul className="divide-y divide-stone-100 dark:divide-stone-800">
              {exps.map((e) => (
                <li key={e.id} className="py-2.5 text-sm first:pt-0 last:pb-0">
                  <div className="flex items-baseline gap-2">
                    <span className="min-w-0 flex-1 truncate font-medium text-stone-800 dark:text-stone-200">{e.title}</span>
                    <span className="shrink-0 text-xs tabular-nums text-stone-400 dark:text-stone-400">{e.date}</span>
                  </div>
                  {e.commit_url && (
                    <a href={e.commit_url} target="_blank" rel="noopener"
                       className="mt-1 inline-block font-mono text-xs text-indigo-600 underline-offset-2 hover:underline dark:text-indigo-400 dark:hover:text-indigo-300" title={e.commit_url}>
                      ⎇ {e.commit_label}
                    </a>
                  )}
                  {e.body && <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-stone-500 dark:text-stone-400">{e.body}</p>}
                </li>
              ))}
            </ul>
          )}
        </SectionCard>

        <SectionCard title="Datasets" count={dsets.length}>
          {dsets.length === 0 ? (
            <Empty>
              No datasets registered — <a href={classic} className="text-indigo-600 hover:underline dark:text-indigo-400 dark:hover:text-indigo-300">add one</a>.
            </Empty>
          ) : (
            <ul className="divide-y divide-stone-100 dark:divide-stone-800">
              {dsets.map((d) => (
                <li key={d.id} className="py-2.5 text-sm first:pt-0 last:pb-0">
                  <div className="flex items-baseline gap-2">
                    <span className="min-w-0 flex-1 truncate font-medium text-stone-800 dark:text-stone-200">{d.name}</span>
                    {d.version && <span className="shrink-0 text-xs tabular-nums text-stone-400 dark:text-stone-400">v{d.version}</span>}
                  </div>
                  <p className="mt-1 truncate font-mono text-xs text-stone-500 dark:text-stone-400" title={d.location}>{d.location}</p>
                </li>
              ))}
            </ul>
          )}
        </SectionCard>

        <SectionCard title="Protocols" count={currentProtocols.length}>
          {currentProtocols.length === 0 ? (
            <Empty>
              No protocols yet — <a href={`${classic}protocols/`} className="text-indigo-600 hover:underline dark:text-indigo-400 dark:hover:text-indigo-300">write one</a>.
            </Empty>
          ) : (
            <ul className="divide-y divide-stone-100 dark:divide-stone-800">
              {currentProtocols.map((p) => (
                <li key={p.id} className="flex items-baseline gap-2 py-2.5 text-sm first:pt-0 last:pb-0">
                  <span className="min-w-0 flex-1 truncate font-medium text-stone-800 dark:text-stone-200">{p.title}</span>
                  <span className="shrink-0 rounded bg-stone-100 px-1.5 py-0.5 font-mono text-xs text-stone-500 dark:bg-stone-800 dark:text-stone-300">v{p.version}</span>
                </li>
              ))}
            </ul>
          )}
        </SectionCard>
      </div>
    </div>
  );
}
