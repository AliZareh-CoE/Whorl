/** Global reference library (SPA slice 5). */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
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
      <h1 className="mb-2 text-2xl font-semibold tracking-tight">Library</h1>
      <p className="mb-6 text-sm text-stone-500">{data?.count ?? 0} references, shared across projects.</p>

      <form
        className="mb-4 flex max-w-xl items-start gap-2"
        onSubmit={(e) => { e.preventDefault(); if (doi.trim()) addByDoi.mutate(); }}
      >
        <div className="flex-1">
          <input
            value={doi}
            onChange={(e) => setDoi(e.target.value)}
            placeholder="Add by DOI or arXiv ID…"
            className="w-full rounded border border-stone-300 bg-white px-3 py-2 text-sm focus:border-indigo-600 focus:outline-none"
          />
          {addError && <p className="mt-1 text-xs text-red-600">{addError}</p>}
        </div>
        <button type="submit" disabled={addByDoi.isPending}
                className="rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700">
          {addByDoi.isPending ? "Fetching…" : "Add"}
        </button>
      </form>

      <input
        type="search"
        value={filter}
        onChange={(e) => setFilter(e.target.value)}
        placeholder={`Filter ${data?.count ?? 0} references…`}
        className="mb-4 w-64 rounded border border-stone-300 bg-white px-3 py-1.5 text-sm focus:border-indigo-600 focus:outline-none"
      />

      <div className="divide-y divide-stone-100 rounded border border-stone-200 bg-white">
        {rows.map((r) => (
          <a key={r.id} href={`/library/${r.id}/`} className="block px-4 py-3 text-sm hover:bg-stone-50">
            <span className="font-medium">{r.title}</span>
            <p className="text-xs text-stone-400">
              {(r.authors ?? []).slice(0, 3).map((a) => a.family).filter(Boolean).join(", ")}
              {r.year ? ` · ${r.year}` : ""} · <span className="font-mono">{r.bibtex_key}</span>
            </p>
          </a>
        ))}
        {rows.length === 0 && <p className="px-4 py-8 text-center text-sm text-stone-400">No matches.</p>}
      </div>
      {(data?.count ?? 0) > (data?.results.length ?? 0) && (
        <p className="mt-2 text-xs text-stone-400">
          Showing the first {data?.results.length} — full search on the <a className="underline" href="/library/">classic library ↗</a>
        </p>
      )}
    </div>
  );
}
