/** Project literature + reading queue, sharing one list (SPA slice 5). */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate, useParams, useSearchParams } from "react-router-dom";
import { api, csrfToken, petReact } from "../api";

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

const STATUS_DOT: Record<string, string> = {
  to_read: "bg-stone-300",
  skimmed: "bg-amber-400",
  read: "bg-emerald-500",
  annotated: "bg-indigo-500",
};

function authorLine(ref: Ref): string {
  const names = (ref.authors ?? []).map((a) => a.family ?? a.given ?? "").filter(Boolean);
  const head = names.slice(0, 3).join(", ");
  return names.length > 3 ? `${head} et al.` : head;
}

export default function Literature({ queue = false }: { queue?: boolean }) {
  const { slug } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [searchParams] = useSearchParams();
  const theme = queue ? (searchParams.get("theme") ?? "") : "";
  const listKey = ["literature", slug, theme];
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
    queryKey: listKey,
    queryFn: () =>
      api<Page<LinkRow>>(
        `/project-references/?project=${slug}${theme ? `&theme=${encodeURIComponent(theme)}` : ""}`,
      ),
  });

  const setStatus = useMutation({
    mutationFn: ({ id, status }: { id: number; status: string }) =>
      api(`/project-references/${id}/`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ reading_status: status }),
      }),
    onMutate: ({ id, status }) => {
      if (status === "read" || status === "annotated") petReact("paper");
      queryClient.setQueryData<Page<LinkRow>>(listKey, (old) =>
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

  if (isLoading) return <p className="text-sm text-stone-400 dark:text-stone-400">Loading papers…</p>;
  let rows = data?.results ?? [];
  if (queue) {
    rows = rows
      .filter((r) => r.reading_status === "to_read" || r.reading_status === "skimmed")
      .sort((a, b) => PRIORITY_ORDER[a.priority] - PRIORITY_ORDER[b.priority]);
  }

  return (
    <div>
      <nav className="mb-6 text-sm text-stone-500 dark:text-stone-400">
        <Link to="/projects" className="hover:text-stone-700 dark:hover:text-stone-300 hover:underline">Projects</Link>
        <span className="px-1.5 text-stone-300 dark:text-stone-400">/</span>
        <Link to={`/projects/${slug}`} className="hover:text-stone-700 dark:hover:text-stone-300 hover:underline">{slug}</Link>
        <span className="px-1.5 text-stone-300 dark:text-stone-400">/</span>
        <span className="text-stone-700 dark:text-stone-300">{queue ? "Queue" : "Literature"}</span>
      </nav>
      <div className="mb-6 flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-stone-900 dark:text-stone-100">{queue ? "Reading queue" : "Literature"}</h1>
          <p className="mt-1 text-sm text-stone-500 dark:text-stone-400">
            {queue
              ? `${rows.length} ${rows.length === 1 ? "paper" : "papers"} to read, ordered by priority`
              : `${rows.length} ${rows.length === 1 ? "paper" : "papers"} linked to this project`}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-3 text-xs">
          <Link to={queue ? `/projects/${slug}/literature` : `/projects/${slug}/queue`}
                className="text-indigo-600 dark:text-indigo-400 hover:text-indigo-700 dark:hover:text-indigo-300 hover:underline">
            {queue ? "All papers" : "Reading queue"}
          </Link>
          {queue && (
            <Link to={`/projects/${slug}/read`}
                  className="rounded bg-indigo-600 px-2.5 py-1.5 font-medium text-white transition-colors hover:bg-indigo-700">
              ▶ Read flow
            </Link>
          )}
          {!queue && (
            <button onClick={draftSynthesis} disabled={drafting}
                    className="rounded border border-stone-300 dark:border-stone-700 bg-white dark:bg-stone-800 px-2.5 py-1.5 font-medium text-stone-700 dark:text-stone-300 transition-colors hover:border-stone-400 hover:bg-stone-50 dark:hover:bg-stone-800 disabled:opacity-50">
              {drafting ? "Drafting…" : "Draft synthesis"}
            </button>
          )}
          <a href={`/projects/${slug}/literature/`} className="text-stone-400 dark:text-stone-400 transition-colors hover:text-indigo-600 dark:hover:text-indigo-400">
            matrix & reports ↗
          </a>
        </div>
      </div>

      {!queue && matrix && matrix.coverage.length > 0 && matrix.coverage[0].count <= 1 && (
        <div className="mb-4 rounded border border-amber-200 dark:border-amber-500/30 bg-amber-50 dark:bg-amber-500/10 px-3 py-2 text-xs text-amber-800 dark:text-amber-300">
          <span className="font-medium">Coverage gap:</span>{" "}
          {matrix.coverage.filter((c) => c.count <= 1).map((c) => (
            <Link key={c.name} to={`/projects/${slug}/queue?theme=${encodeURIComponent(c.name)}`}
                  className="mr-1 inline-block rounded-full border border-amber-300 dark:border-amber-500/40 bg-white dark:bg-stone-800 px-2 py-0.5 font-medium hover:border-amber-500 hover:text-amber-950 dark:hover:text-amber-200"
                  title={`Show unread candidates for “${c.name}”`}>
              {c.name} · {c.count}
            </Link>
          ))}
          {matrix.coverage.filter((c) => c.count <= 1).length === 1 ? "has" : "have"} ≤1 paper —
          click a theme to see unread candidates for it.
        </div>
      )}

      {theme && (
        <div className="mb-4 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm">
          <span className="rounded-full bg-indigo-50 dark:bg-indigo-500/10 px-3 py-1 text-xs font-medium text-indigo-700 dark:text-indigo-300">
            Candidates for “{theme}”
          </span>
          <span className="text-xs text-stone-400 dark:text-stone-400">unread papers that look relevant and aren’t marked under it yet</span>
          <Link to={`/projects/${slug}/queue`} className="text-xs text-stone-500 dark:text-stone-400 underline hover:text-indigo-600 dark:hover:text-indigo-400">
            Clear
          </Link>
        </div>
      )}

      {selected.size > 0 && (
        <div className="mb-3 flex flex-wrap items-center gap-2 rounded border border-indigo-200 dark:border-indigo-500/30 bg-indigo-50 dark:bg-indigo-500/10 px-3 py-2 text-sm">
          <span className="font-medium text-indigo-800 dark:text-indigo-300">{selected.size} selected</span>
          <span className="text-indigo-200 dark:text-indigo-400">·</span>
          <span className="text-stone-500 dark:text-stone-400">Mark as</span>
          <select value={bulkStatus} onChange={(e) => setBulkStatus(e.target.value)}
                  className="rounded border border-stone-300 dark:border-stone-700 bg-white dark:bg-stone-800 px-2 py-1 text-xs focus:border-indigo-600 focus:outline-none">
            {STATUSES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
          </select>
          <button onClick={applyBulk}
                  className="rounded border border-stone-300 dark:border-stone-700 bg-white dark:bg-stone-800 px-2.5 py-1 text-xs font-medium text-stone-700 dark:text-stone-300 transition-colors hover:border-stone-400 hover:bg-white dark:hover:bg-stone-800">
            Apply
          </button>
          <button onClick={() => setSelected(new Set())}
                  className="ml-auto text-xs text-stone-500 dark:text-stone-400 hover:text-indigo-600 dark:hover:text-indigo-400">
            Clear selection
          </button>
        </div>
      )}

      <div className="overflow-hidden rounded border border-stone-200 dark:border-stone-800 bg-white dark:bg-stone-900">
        {rows.length > 0 && (
          <div className="flex items-center justify-between border-b border-stone-100 dark:border-stone-800 px-4 py-2.5">
            <h2 className="text-xs font-medium uppercase tracking-wide text-stone-400 dark:text-stone-400">
              {queue ? "Queue" : "Papers"}
            </h2>
            <span className="text-xs text-stone-400 dark:text-stone-400">{rows.length}</span>
          </div>
        )}
        <div className="divide-y divide-stone-100 dark:divide-stone-800">
          {rows.map((row) => (
            <div key={row.id} className="flex items-center gap-3 px-4 py-3 text-sm transition-colors hover:bg-stone-50 dark:hover:bg-stone-800">
              <input
                type="checkbox"
                aria-label={`Select ${row.reference_summary.title.slice(0, 40)}`}
                checked={selected.has(row.id)}
                onChange={() => {
                  const next = new Set(selected);
                  next.has(row.id) ? next.delete(row.id) : next.add(row.id);
                  setSelected(next);
                }}
                className="size-4 shrink-0 rounded border-stone-300 dark:border-stone-700 accent-indigo-600"
              />
              <span
                aria-hidden="true"
                title={row.reading_status.replace("_", " ")}
                className={`size-1.5 shrink-0 rounded-full ${STATUS_DOT[row.reading_status] ?? "bg-stone-300"}`}
              />
              <div className="min-w-0 flex-1">
                <Link to={`/references/${row.reference_summary.id}`} className="font-medium text-stone-900 dark:text-stone-100 hover:text-indigo-700 dark:hover:text-indigo-300 hover:underline">
                  {row.reference_summary.title}
                </Link>
                <p className="truncate text-xs text-stone-400 dark:text-stone-400">
                  {authorLine(row.reference_summary)}
                  {row.reference_summary.year ? ` · ${row.reference_summary.year}` : ""} ·{" "}
                  <span className="font-mono">{row.reference_summary.bibtex_key}</span>
                </p>
              </div>
              {row.priority !== "normal" && (
                <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium ${
                  row.priority === "high"
                    ? "bg-rose-50 dark:bg-rose-500/10 text-rose-700 dark:text-rose-300"
                    : "bg-stone-100 dark:bg-stone-800 text-stone-500 dark:text-stone-300"
                }`}>{row.priority}</span>
              )}
              <select
                value={row.reading_status}
                onChange={(e) => setStatus.mutate({ id: row.id, status: e.target.value })}
                className="shrink-0 rounded border border-stone-300 dark:border-stone-700 bg-white dark:bg-stone-800 px-2 py-1 text-xs text-stone-700 dark:text-stone-300 transition-colors hover:border-stone-400 focus:border-indigo-600 focus:outline-none"
                aria-label="Reading status"
              >
                {STATUSES.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
              </select>
            </div>
          ))}
          {rows.length === 0 && (
            <div className="px-6 py-14 text-center">
              <p className="text-sm text-stone-500 dark:text-stone-400">
                {theme ? (
                  <>
                    No unread candidates for “{theme}.”
                  </>
                ) : queue ? (
                  "Queue is clear — everything has been read."
                ) : (
                  "No papers linked to this project yet."
                )}
              </p>
              <p className="mt-1.5 text-xs text-stone-400 dark:text-stone-400">
                {theme ? (
                  <>
                    <Link to={`/projects/${slug}/queue`} className="text-indigo-600 dark:text-indigo-400 hover:underline">
                      Show the whole queue
                    </Link>{" "}
                    or add papers to the library.
                  </>
                ) : queue ? (
                  <>Nice work — nothing left in the reading queue.</>
                ) : (
                  <>
                    Add references from the{" "}
                    <Link to="/library" className="text-indigo-600 dark:text-indigo-400 hover:underline">library</Link>{" "}
                    and link them here.
                  </>
                )}
              </p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
