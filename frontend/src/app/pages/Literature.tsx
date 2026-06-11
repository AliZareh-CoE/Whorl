/** Project literature + reading queue, sharing one list (SPA slice 5). */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, csrfToken } from "../api";

type Ref = { id: number; bibtex_key: string; title: string; authors: { family?: string; given?: string }[]; year: number | null; venue: string };
type LinkRow = {
  id: number;
  reference: number;
  reference_summary: Ref;
  reading_status: string;
  priority: string;
};
type Page<T> = { count: number; results: T[] };

const STATUSES = [
  ["to_read", "To read"],
  ["skimmed", "Skimmed"],
  ["read", "Read"],
  ["annotated", "Annotated"],
];
const PRIORITY_ORDER: Record<string, number> = { high: 0, normal: 1, low: 2 };

function authorLine(ref: Ref): string {
  const names = (ref.authors ?? []).map((a) => a.family ?? a.given ?? "").filter(Boolean);
  const head = names.slice(0, 3).join(", ");
  return names.length > 3 ? `${head} et al.` : head;
}

export default function Literature({ queue = false }: { queue?: boolean }) {
  const { slug } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [bulkStatus, setBulkStatus] = useState("read");
  const [drafting, setDrafting] = useState(false);

  const { data: matrix } = useQuery({
    queryKey: ["review-matrix", slug],
    queryFn: () => api<{ coverage: { name: string; count: number }[] }>(`/projects/${slug}/review-matrix/`),
    enabled: !queue,
  });

  async function draftSynthesis() {
    setDrafting(true);
    const res = await fetch(`/projects/${slug}/literature/synthesis/`, {
      method: "POST",
      headers: { "X-CSRFToken": csrfToken(), "X-SPA": "1" },
    });
    const data = await res.json();
    navigate(`/projects/${slug}/notes/${data.note_id}`);
  }

  const { data, isLoading } = useQuery({
    queryKey: ["literature", slug],
    queryFn: () => api<Page<LinkRow>>(`/project-references/?project=${slug}`),
  });

  const setStatus = useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) =>
      api(`/project-references/${id}/`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reading_status: status }),
      }),
    onMutate: ({ id, status }) => {
      queryClient.setQueryData<Page<LinkRow>>(["literature", slug], (old) =>
        old
          ? { ...old, results: old.results.map((r) => (r.id === id ? { ...r, reading_status: status } : r)) }
          : old,
      );
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["literature", slug] }),
  });

  async function applyBulk() {
    const body = new URLSearchParams({ reading_status: bulkStatus });
    selected.forEach((id) => body.append("ids", String(id)));
    await fetch(`/projects/${slug}/literature/bulk-status/`, {
      method: "POST",
      headers: { "X-CSRFToken": csrfToken(), "X-SPA": "1" },
      body,
    });
    setSelected(new Set());
    queryClient.invalidateQueries({ queryKey: ["literature", slug] });
  }

  if (isLoading) return <p className="text-sm text-stone-400">Loading papers…</p>;
  let rows = data?.results ?? [];
  if (queue) {
    rows = rows
      .filter((r) => r.reading_status === "to_read" || r.reading_status === "skimmed")
      .sort((a, b) => PRIORITY_ORDER[a.priority] - PRIORITY_ORDER[b.priority]);
  }

  return (
    <div>
      <nav className="mb-6 text-sm text-stone-500">
        <Link to="/projects" className="hover:underline">Projects</Link> /{" "}
        <Link to={`/projects/${slug}`} className="hover:underline">{slug}</Link> /{" "}
        {queue ? "Queue" : "Literature"}
      </nav>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">{queue ? "Reading queue" : "Literature"}</h1>
        <div className="flex items-center gap-3 text-xs">
          <Link to={queue ? `/projects/${slug}/literature` : `/projects/${slug}/queue`}
                className="text-indigo-600 hover:underline">
            {queue ? "All papers" : "Reading queue"}
          </Link>
          {queue && (
            <Link to={`/projects/${slug}/read`}
                  className="rounded bg-indigo-600 px-2.5 py-1 font-medium text-white hover:bg-indigo-700">
              ▶ Read flow
            </Link>
          )}
          {!queue && (
            <button onClick={draftSynthesis} disabled={drafting}
                    className="rounded border border-stone-300 bg-white px-2.5 py-1 hover:border-stone-400 disabled:opacity-50">
              {drafting ? "Drafting…" : "Draft synthesis"}
            </button>
          )}
          <a href={`/projects/${slug}/literature/`} className="text-stone-400 underline hover:text-indigo-700">
            matrix & reports ↗
          </a>
        </div>
      </div>

      {!queue && matrix && matrix.coverage.length > 0 && matrix.coverage[0].count <= 1 && (
        <div className="mb-4 rounded border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
          <span className="font-medium">Coverage gap:</span>{" "}
          {matrix.coverage.filter((c) => c.count <= 1).map((c) => c.name).join(", ")}{" "}
          {matrix.coverage.filter((c) => c.count <= 1).length === 1 ? "has" : "have"} ≤1 paper.
          Use <Link to={`/projects/${slug}/queue`} className="underline">the queue</Link> to fill the thinnest themes first.
        </div>
      )}

      {selected.size > 0 && (
        <div className="mb-3 flex items-center gap-2 rounded border border-indigo-200 bg-indigo-50 px-3 py-2 text-sm">
          <span className="font-medium text-indigo-800">{selected.size} selected</span>
          <span className="mx-1 text-indigo-200">|</span>
          <span className="text-stone-500">Mark as</span>
          <select value={bulkStatus} onChange={(e) => setBulkStatus(e.target.value)}
                  className="rounded border border-stone-300 bg-white px-2 py-1 text-xs">
            {STATUSES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
          <button onClick={applyBulk}
                  className="rounded border border-stone-300 bg-white px-2 py-1 text-xs hover:border-stone-400">
            Apply
          </button>
        </div>
      )}

      <div className="divide-y divide-stone-100 rounded border border-stone-200 bg-white">
        {rows.map((row) => (
          <div key={row.id} className="flex items-center gap-3 px-4 py-3 text-sm">
            <input
              type="checkbox"
              aria-label={`Select ${row.reference_summary.title.slice(0, 40)}`}
              checked={selected.has(row.id)}
              onChange={() => {
                const next = new Set(selected);
                next.has(row.id) ? next.delete(row.id) : next.add(row.id);
                setSelected(next);
              }}
              className="size-4 shrink-0 rounded border-stone-300 accent-indigo-600"
            />
            <div className="min-w-0 flex-1">
              <Link to={`/references/${row.reference_summary.id}`} className="font-medium hover:underline">
                {row.reference_summary.title}
              </Link>
              <p className="text-xs text-stone-400">
                {authorLine(row.reference_summary)}
                {row.reference_summary.year ? ` · ${row.reference_summary.year}` : ""} ·{" "}
                <span className="font-mono">{row.reference_summary.bibtex_key}</span>
              </p>
            </div>
            <span className={`shrink-0 rounded px-2 py-0.5 text-xs ${
              row.priority === "high" ? "bg-red-50 text-red-700" : "bg-stone-100 text-stone-500"
            }`}>{row.priority}</span>
            <select
              value={row.reading_status}
              onChange={(e) => setStatus.mutate({ id: row.id, status: e.target.value })}
              className="shrink-0 rounded border border-stone-300 bg-white px-2 py-1 text-xs"
              aria-label="Reading status"
            >
              {STATUSES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
            </select>
          </div>
        ))}
        {rows.length === 0 && (
          <p className="px-4 py-8 text-center text-sm text-stone-400">
            {queue ? "Queue is clear — everything has been read." : "No papers linked yet."}
          </p>
        )}
      </div>
    </div>
  );
}
