/** Global search (SPA slice 8). */
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api";

type Result = { type: string; id: number; label: string; project: string | null; url: string | null };

export default function Search() {
  const [q, setQ] = useState("");
  const [submitted, setSubmitted] = useState("");
  const { data, isFetching } = useQuery({
    queryKey: ["search", submitted],
    queryFn: () => api<{ results: Result[] }>(`/search/?q=${encodeURIComponent(submitted)}`),
    enabled: submitted.length >= 2,
  });

  return (
    <div>
      <h1 className="mb-6 text-2xl font-semibold tracking-tight">Search</h1>
      <form className="mb-6 flex max-w-xl gap-2"
            onSubmit={(e) => { e.preventDefault(); setSubmitted(q); }}>
        <input autoFocus type="search" value={q} onChange={(e) => setQ(e.target.value)}
               placeholder="Search everything — typos welcome…" aria-label="Search query"
               className="flex-1 rounded border border-stone-300 bg-white px-3 py-2 text-sm focus:border-indigo-600 focus:outline-none" />
        <button type="submit" className="rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700">
          Search
        </button>
      </form>
      {isFetching && <p className="text-sm text-stone-400">Searching…</p>}
      {data && (
        <div className="max-w-2xl divide-y divide-stone-100 rounded border border-stone-200 bg-white">
          {data.results.map((r) => (
            <a key={`${r.type}-${r.id}`} href={r.url ?? "#"} className="flex items-center gap-2 px-4 py-2.5 text-sm hover:bg-stone-50">
              <span className="rounded bg-stone-100 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-stone-400">{r.type}</span>
              <span className="min-w-0 flex-1 truncate">{r.label}</span>
              {r.project && <span className="shrink-0 text-xs text-stone-400">{r.project}</span>}
            </a>
          ))}
          {data.results.length === 0 && (
            <p className="px-4 py-8 text-center text-sm text-stone-400">Nothing found for “{submitted}”.</p>
          )}
        </div>
      )}
    </div>
  );
}
