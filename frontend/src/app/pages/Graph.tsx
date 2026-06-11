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

  return (
    <div>
      <nav className="mb-6 text-sm text-stone-500">
        <Link to="/projects" className="hover:underline">Projects</Link> /{" "}
        <Link to={`/projects/${slug}`} className="hover:underline">{slug}</Link> / Graph
      </nav>
      <div className="mb-4 flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Knowledge graph</h1>
        <div className="flex items-center gap-2 text-xs">
          <button onClick={() => setMode(mode === "3d" ? "2d" : "3d")}
                  className="rounded border border-stone-300 bg-white px-2.5 py-1 hover:border-stone-400">
            {mode === "3d" ? "2D view" : "3D view"}
          </button>
          <button onClick={syncCitations} disabled={syncing}
                  className="rounded border border-stone-300 bg-white px-2.5 py-1 hover:border-stone-400 disabled:opacity-50">
            {syncing ? "Sync queued…" : "Sync citations"}
          </button>
        </div>
      </div>

      <div className="relative overflow-hidden rounded border border-stone-200 bg-white">
        <div ref={containerRef} style={{ height: 560 }}>
          <p className="p-8 text-sm text-stone-400">Loading graph…</p>
        </div>
        {selected && (
          <aside className="absolute right-3 top-3 w-64 rounded border border-stone-200 bg-white p-4 shadow-lg">
            <p className="mb-1 text-[10px] uppercase tracking-wide text-stone-400">{selected.type}</p>
            <p className="mb-2 text-sm font-medium">{selected.label}</p>
            {selected.url && (
              <a href={selected.url} className="text-xs text-indigo-600 hover:underline">Open ↗</a>
            )}
            <button onClick={() => setSelected(null)}
                    className="absolute right-2 top-2 text-stone-400 hover:text-stone-600" aria-label="Close">✕</button>
          </aside>
        )}
      </div>
      <p className="mt-2 text-xs text-stone-400">
        Node size = citations · color = reading status / type · drag to explore
      </p>
    </div>
  );
}
