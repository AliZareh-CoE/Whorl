/** Global reference library (SPA slice 5). */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";

type Ref = { id: number; bibtex_key: string; title: string; authors: { family?: string }[]; year: number | null; venue: string };
type Page<T> = { count: number; results: T[] };

export default function Library() {
  const queryClient = useQueryClient();
  const [filter, setFilter] = useState("");
  const [doi, setDoi] = useState("");
  const [addError, setAddError] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["library"],
    queryFn: () => api<Page<Ref>>("/references/"),
  });

  const addByDoi = useMutation({
    mutationFn: () =>
      api<Ref>("/references/by-doi/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ doi }),
      }),
    onSuccess: () => {
      setDoi("");
      setAddError("");
      queryClient.invalidateQueries({ queryKey: ["library"] });
    },
    onError: (e) => setAddError(String(e.message ?? e)),
  });

  if (isLoading) return <p className="text-sm text-stone-400">Loading library…</p>;
  const needle = filter.trim().toLowerCase();
  const rows = (data?.results ?? []).filter(
    (r) =>
      !needle ||
      r.title.toLowerCase().includes(needle) ||
      r.bibtex_key.toLowerCase().includes(needle) ||
      (r.venue ?? "").toLowerCase().includes(needle),
  );

  return (
    <div>
      <h1 className="mb-1 text-2xl font-semibold tracking-tight">Library</h1>
      <p className="mb-6 text-sm text-stone-500">{data?.count ?? 0} references, shared across projects.</p>

      <form
        className="mb-5 flex max-w-xl items-start gap-2"
        onSubmit={(e) => { e.preventDefault(); if (doi.trim()) addByDoi.mutate(); }}
      >
        <div className="flex-1">
          <input
            value={doi}
            onChange={(e) => setDoi(e.target.value)}
            placeholder="Add by DOI or arXiv ID…"
            className="w-full rounded border border-stone-300 bg-white px-3 py-2 text-sm placeholder:text-stone-400 focus:border-indigo-600 focus:outline-none focus:ring-1 focus:ring-indigo-600"
          />
          {addError && <p className="mt-1.5 text-xs text-red-600">{addError}</p>}
        </div>
        <button type="submit" disabled={addByDoi.isPending}
                className="rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50">
          {addByDoi.isPending ? "Fetching…" : "Add"}
        </button>
      </form>

      <div className="mb-3 flex items-center justify-between gap-3">
        <input
          type="search"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder={`Filter ${data?.count ?? 0} references…`}
          className="w-72 rounded border border-stone-300 bg-white px-3 py-1.5 text-sm placeholder:text-stone-400 focus:border-indigo-600 focus:outline-none focus:ring-1 focus:ring-indigo-600"
        />
        <span className="text-xs uppercase tracking-wide text-stone-400">{rows.length} shown</span>
      </div>

      <div className="divide-y divide-stone-100 overflow-hidden rounded border border-stone-200 bg-white">
        {rows.map((r) => (
          <Link
            key={r.id}
            to={`/references/${r.id}`}
            className="group block px-4 py-2.5 transition-colors hover:bg-stone-50 focus:bg-stone-50 focus:outline-none"
          >
            <p className="truncate text-sm font-medium text-stone-900 group-hover:text-indigo-700">{r.title}</p>
            <p className="mt-0.5 truncate text-xs text-stone-400">
              {(r.authors ?? []).slice(0, 3).map((a) => a.family).filter(Boolean).join(", ")}
              {r.year ? ` · ${r.year}` : ""} ·{" "}
              <span className="rounded bg-stone-100 px-1 py-0.5 font-mono text-[11px] text-stone-500">{r.bibtex_key}</span>
            </p>
          </Link>
        ))}
        {rows.length === 0 && (
          <div className="px-4 py-12 text-center">
            <p className="text-sm font-medium text-stone-500">
              {filter.trim() ? "No matches" : "Your library is empty"}
            </p>
            <p className="mx-auto mt-1 max-w-sm text-xs text-stone-400">
              {filter.trim()
                ? "Try a different title, author, or venue."
                : "Add a paper by DOI or arXiv ID above to start building your shared reference library."}
            </p>
          </div>
        )}
      </div>
      {(data?.count ?? 0) > (data?.results.length ?? 0) && (
        <p className="mt-2 text-xs text-stone-400">
          Showing the first {data?.results.length} —{" "}
          <a className="text-indigo-600 hover:underline" href="/library/">full search on the classic library ↗</a>
        </p>
      )}
    </div>
  );
}
