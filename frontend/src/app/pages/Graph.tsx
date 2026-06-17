/** 3D knowledge graph (SPA slice 10) — 3d-force-graph lazy-loaded from the CDN. */
import { useQuery } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, csrfToken } from "../api";

type Node = { id: string; type: string; label: string; group: string; size: number; url?: string };
type GraphData = { nodes: Node[]; links: { source: string; target: string; kind: string }[] };

declare global {
  interface Window { ForceGraph3D?: any; ForceGraph?: any }
}

function loadScript(src: string): Promise<void> {
  return new Promise((resolve, reject) => {
    if (document.querySelector(`script[src="${src}"]`)) return resolve();
    const s = document.createElement("script");
    s.src = src;
    s.onload = () => resolve();
    s.onerror = reject;
    document.head.appendChild(s);
  });
}

const COLORS: Record<string, string> = {
  to_read: "#f59e0b", skimmed: "#818cf8", read: "#4f46e5",
  annotated: "#16a34a", note: "#0d9488", reference: "#6366f1",
};

const LEGEND: { group: string; label: string }[] = [
  { group: "to_read", label: "To read" },
  { group: "skimmed", label: "Skimmed" },
  { group: "read", label: "Read" },
  { group: "annotated", label: "Annotated" },
  { group: "note", label: "Note" },
];

export default function Graph() {
  const { slug } = useParams();
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<any>(null);
  const [mode, setMode] = useState<"3d" | "2d">("3d");
  const [selected, setSelected] = useState<Node | null>(null);
  const [syncing, setSyncing] = useState(false);

  const { data } = useQuery({
    queryKey: ["graph", slug],
    queryFn: () => api<GraphData>(`/projects/${slug}/graph/`),
  });

  useEffect(() => {
    if (!data || !containerRef.current) return;
    let cancelled = false;
    (async () => {
      await loadScript(
        mode === "3d"
          ? "https://unpkg.com/3d-force-graph@1.73.4/dist/3d-force-graph.min.js"
          : "https://unpkg.com/force-graph@1.43.5/dist/force-graph.min.js",
      );
      if (cancelled || !containerRef.current) return;
      containerRef.current.innerHTML = "";
      const factory = mode === "3d" ? window.ForceGraph3D : window.ForceGraph;
      const graph = factory()(containerRef.current)
        .graphData(data)
        .nodeLabel((n: Node) => n.label)
        .nodeVal((n: Node) => n.size)
        .nodeColor((n: Node) => COLORS[n.group] ?? "#a8a29e")
        .width(containerRef.current.clientWidth)
        .height(560)
        .onNodeClick((n: Node) => setSelected(n));
      if (mode === "3d") graph.backgroundColor("#fafaf9");
      graphRef.current = graph;
    })();
    return () => { cancelled = true; graphRef.current?._destructor?.(); };
  }, [data, mode]);

  async function syncCitations() {
    setSyncing(true);
    await fetch(`/projects/${slug}/graph/sync/`, {
      method: "POST",
      headers: { "X-CSRFToken": csrfToken() },
      redirect: "manual",
    });
    setTimeout(() => setSyncing(false), 1500);
  }

  const isEmpty = data != null && data.nodes.length === 0;

  return (
    <div>
      <nav className="mb-6 text-sm text-stone-500">
        <Link to="/projects" className="hover:text-indigo-700">Projects</Link>
        <span className="px-1.5 text-stone-300">/</span>
        <Link to={`/projects/${slug}`} className="hover:text-indigo-700">{slug}</Link>
        <span className="px-1.5 text-stone-300">/</span>
        <span className="text-stone-700">Graph</span>
      </nav>

      <div className="mb-1 flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Knowledge graph</h1>
        <div className="flex items-center gap-3 text-xs">
          <div className="inline-flex overflow-hidden rounded border border-stone-300">
            {(["3d", "2d"] as const).map((m) => (
              <button
                key={m}
                onClick={() => setMode(m)}
                aria-pressed={mode === m}
                className={
                  "px-3 py-1 font-medium transition-colors " +
                  (mode === m
                    ? "bg-indigo-600 text-white"
                    : "bg-white text-stone-600 hover:bg-stone-50") +
                  (m === "3d" ? " border-r border-stone-300" : "")
                }
              >
                {m.toUpperCase()}
              </button>
            ))}
          </div>
          <button
            onClick={syncCitations}
            disabled={syncing}
            className="inline-flex items-center gap-1.5 rounded border border-stone-300 bg-white px-2.5 py-1 font-medium text-stone-600 transition-colors hover:border-stone-400 hover:bg-stone-50 disabled:opacity-50"
          >
            {syncing && (
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-amber-500" aria-hidden="true" />
            )}
            {syncing ? "Sync queued…" : "Sync citations"}
          </button>
        </div>
      </div>
      <p className="mb-4 text-sm text-stone-500">
        Citations and note-links across this project's references and notes.
      </p>

      <div className="relative overflow-hidden rounded border border-stone-200 bg-white">
        <div ref={containerRef} style={{ height: 560 }}>
          {isEmpty ? (
            <div className="flex h-full flex-col items-center justify-center px-8 text-center">
              <p className="mb-2 text-3xl text-stone-300" aria-hidden="true">⬡</p>
              <p className="mb-1 text-sm font-medium text-stone-600">Nothing to graph yet</p>
              <p className="mb-4 max-w-xs text-sm text-stone-400">
                Add references or notes to this project and they'll appear here, wired together by
                citations and links.
              </p>
              <Link
                to={`/projects/${slug}/literature`}
                className="rounded border border-stone-300 bg-white px-3 py-1.5 text-sm font-medium text-stone-700 transition-colors hover:border-stone-400 hover:bg-stone-50"
              >
                Add references
              </Link>
            </div>
          ) : (
            <p className="p-8 text-sm text-stone-400">Loading graph…</p>
          )}
        </div>

        {!isEmpty && (
          <div className="pointer-events-none absolute left-3 top-3 rounded border border-stone-200 bg-white/90 px-3 py-2 text-[11px] shadow-sm backdrop-blur">
            <p className="mb-1.5 text-[10px] font-medium uppercase tracking-wide text-stone-400">
              Legend
            </p>
            <ul className="space-y-1">
              {LEGEND.map((item) => (
                <li key={item.group} className="flex items-center gap-1.5 text-stone-600">
                  <span
                    className="inline-block h-2.5 w-2.5 rounded-full"
                    style={{ backgroundColor: COLORS[item.group] }}
                    aria-hidden="true"
                  />
                  {item.label}
                </li>
              ))}
            </ul>
          </div>
        )}

        {selected && (
          <aside className="absolute right-3 top-3 w-64 rounded border border-stone-200 bg-white p-5 shadow-lg">
            <button
              onClick={() => setSelected(null)}
              className="absolute right-2.5 top-2.5 text-stone-300 transition-colors hover:text-stone-600"
              aria-label="Close"
            >
              ✕
            </button>
            <p className="mb-1.5 pr-5 text-[10px] font-medium uppercase tracking-wide text-stone-400">
              {selected.type}
            </p>
            <p className="mb-3 text-sm font-medium leading-snug text-stone-800">{selected.label}</p>
            {selected.url && (
              <a
                href={selected.url}
                className="inline-flex items-center gap-1 text-xs font-medium text-indigo-600 hover:text-indigo-700 hover:underline"
              >
                Open <span aria-hidden="true">↗</span>
              </a>
            )}
          </aside>
        )}
      </div>

      <p className="mt-2 text-xs text-stone-400">
        Node size = citations · color = reading status / type · drag to explore
      </p>
    </div>
  );
}
