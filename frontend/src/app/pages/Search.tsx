/** Global search (SPA slice 8). */
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api";
import { ErrorState } from "../../components/ErrorState";

type Result = { type: string; id: number; label: string; project: string | null; url: string | null };

/** Quiet per-type chip styling so mixed results stay scannable. */
const TYPE_STYLES: Record<string, string> = {
  reference: "bg-indigo-50 text-indigo-700 dark:bg-indigo-500/10 dark:text-indigo-300",
  note: "bg-amber-50 text-amber-700 dark:bg-amber-500/10 dark:text-amber-300",
  document: "bg-sky-50 text-sky-700 dark:bg-sky-500/10 dark:text-sky-300",
  decision: "bg-emerald-50 text-emerald-700 dark:bg-emerald-500/10 dark:text-emerald-300",
  plan: "bg-violet-50 text-violet-700 dark:bg-violet-500/10 dark:text-violet-300",
  phase: "bg-violet-50 text-violet-700 dark:bg-violet-500/10 dark:text-violet-300",
  milestone: "bg-violet-50 text-violet-700 dark:bg-violet-500/10 dark:text-violet-300",
  manuscript: "bg-rose-50 text-rose-700 dark:bg-rose-500/10 dark:text-rose-300",
  hypothesis: "bg-teal-50 text-teal-700 dark:bg-teal-500/10 dark:text-teal-300",
  experiment: "bg-orange-50 text-orange-700 dark:bg-orange-500/10 dark:text-orange-300",
  dataset: "bg-cyan-50 text-cyan-700 dark:bg-cyan-500/10 dark:text-cyan-300",
  project: "bg-stone-100 text-stone-600 dark:bg-stone-800 dark:text-stone-300",
};

function typeChipClass(type: string): string {
  return TYPE_STYLES[type.toLowerCase()] ?? "bg-stone-100 text-stone-500 dark:bg-stone-800 dark:text-stone-400";
}

export default function Search() {
  const [q, setQ] = useState("");
  const [submitted, setSubmitted] = useState("");
  const { data, isFetching, error, refetch } = useQuery({
    queryKey: ["search", submitted],
    queryFn: () => api<{ results: Result[] }>(`/search/?q=${encodeURIComponent(submitted)}`),
    enabled: submitted.length >= 2,
  });

  return (
    <div>
      <h1 className="mb-1 text-2xl font-semibold tracking-tight">Search</h1>
      <p className="mb-6 text-sm text-stone-500 dark:text-stone-300">
        One box across references, notes, documents, decisions, plans, and manuscripts.
      </p>

      <form
        className="mb-6 flex max-w-xl items-stretch gap-2"
        onSubmit={(e) => {
          e.preventDefault();
          setSubmitted(q);
        }}
      >
        <input
          autoFocus
          type="search"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          placeholder="Search everything — typos welcome…"
          aria-label="Search query"
          className="flex-1 rounded border border-stone-300 bg-white px-3 py-2 text-sm placeholder:text-stone-400 focus:border-indigo-600 focus:outline-none focus:ring-1 focus:ring-indigo-600 dark:border-stone-700 dark:bg-stone-800 dark:text-stone-100"
        />
        <button
          type="submit"
          className="rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700"
        >
          Search
        </button>
      </form>

      {isFetching && <p className="text-sm text-stone-400">Searching…</p>}

      {error && !isFetching && (
        <div className="max-w-xl">
          <ErrorState message="Search failed." onRetry={() => refetch()} />
        </div>
      )}

      {data && !isFetching && (
        <>
          {data.results.length > 0 && (
            <div className="mb-3 flex items-baseline justify-between gap-3">
              <h2 className="text-sm font-medium uppercase tracking-wide text-stone-400">Results</h2>
              <span className="text-xs uppercase tracking-wide text-stone-400">
                {data.results.length} {data.results.length === 1 ? "match" : "matches"}
              </span>
            </div>
          )}

          {data.results.length > 0 ? (
            <div className="max-w-2xl divide-y divide-stone-100 overflow-hidden rounded border border-stone-200 bg-white dark:divide-stone-800 dark:border-stone-800 dark:bg-stone-900">
              {data.results.map((r) => (
                <a
                  key={`${r.type}-${r.id}`}
                  href={r.url ?? "#"}
                  className="group flex items-center gap-3 px-4 py-3 text-sm transition-colors hover:bg-stone-50 focus:bg-stone-50 focus:outline-none dark:hover:bg-stone-800 dark:focus:bg-stone-800"
                >
                  <span
                    className={`w-20 shrink-0 rounded px-1.5 py-0.5 text-center text-[10px] font-medium uppercase tracking-wide ${typeChipClass(r.type)}`}
                  >
                    {r.type}
                  </span>
                  <span className="min-w-0 flex-1 truncate text-stone-900 group-hover:text-indigo-700 dark:text-stone-100 dark:group-hover:text-indigo-300">
                    {r.label}
                  </span>
                  {r.project && (
                    <span className="shrink-0 text-xs text-stone-400">{r.project}</span>
                  )}
                </a>
              ))}
            </div>
          ) : (
            <div className="max-w-2xl rounded border border-dashed border-stone-300 bg-white px-4 py-12 text-center dark:border-stone-700 dark:bg-stone-900">
              <p className="text-sm font-medium text-stone-500 dark:text-stone-300">Nothing found for “{submitted}”.</p>
              <p className="mx-auto mt-1 max-w-sm text-xs text-stone-400">
                Try fewer or different words — search covers references, notes, documents, decisions,
                plans, and manuscripts.
              </p>
            </div>
          )}
        </>
      )}
    </div>
  );
}
