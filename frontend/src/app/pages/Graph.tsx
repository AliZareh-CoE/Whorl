/** Knowledge graph v2 (Observatory) — 3d-force-graph / force-graph from the vendored build (works
 *  offline in the desktop app). Search-to-focus, kind and link filters, neighbourhood focus mode,
 *  hover highlighting, a side panel with the node's facts and neighbours, hubs and orphans stats,
 *  a time-lapse from the first filing day to today and a #tag filter (#506).
 *  Data: GET /projects/{slug}/graph/ (nodes, links, stats). */
import { useQuery } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Crosshair, ExternalLink, Pause, Play, RefreshCw, Search, X } from "lucide-react";
import { api, csrfToken } from "../api";
import { queryGate } from "../../components/QueryBoundary";

type Node = { id: string; type: "reference" | "note"; label: string; title: string; group: string; size: number; url?: string; app_url?: string; year?: number | null; venue?: string; citations?: number | null; authors?: string; has_pdf?: boolean; highlights?: number; words?: number; updated_at?: string; created_at?: string | null; tags?: string[]; degree: number };
type Edge = { source: string | { id: string }; target: string | { id: string }; kind: string };
type Stats = { references: number; notes: number; links: number; first?: string | null; last?: string | null; by_kind: Record<string, number>; orphans: number; hubs: { id: string; label: string; degree: number }[] };
type GraphData = { nodes: Node[]; links: Edge[]; stats: Stats };

declare global { interface Window { ForceGraph3D?: any; ForceGraph?: any } }

const LIB = { "3d": "/static/vendor/forcegraph/3d-force-graph.min.js", "2d": "/static/vendor/forcegraph/force-graph.min.js" } as const;
function loadScript(src: string): Promise<void> {
  return new Promise((resolve, reject) => {
    if (document.querySelector(`script[src="${src}"]`)) return resolve();
    const s = document.createElement("script"); s.src = src; s.onload = () => resolve(); s.onerror = reject; document.head.appendChild(s);
  });
}
const COLORS: Record<string, string> = { to_read: "#f59e0b", skimmed: "#a5b4fc", read: "#7c6cff", annotated: "#34d399", note: "#2dd4bf" };
const LINK_COLORS: Record<string, string> = { citation: "#7c6cff", "note-link": "#2dd4bf", "note-citation": "#c084fc" };
const LEGEND: [string, string][] = [["to_read", "To read"], ["skimmed", "Skimmed"], ["read", "Read"], ["annotated", "Annotated"], ["note", "Note"]];
const LINK_LEGEND: [string, string][] = [["citation", "cites"], ["note-link", "note → note"], ["note-citation", "note → paper"]];
const endId = (e: string | { id: string }) => (typeof e === "string" ? e : e.id);
// #506: the time-lapse works in whole days from the first filing day to today
const DAY = 86_400_000;
const isoDay = (d: Date) => d.toISOString().slice(0, 10);
const todayIso = () => isoDay(new Date());
const daysBetween = (a: string, b: string) => Math.max(0, Math.round((Date.parse(b) - Date.parse(a)) / DAY));
const addDays = (a: string, n: number) => isoDay(new Date(Date.parse(a) + n * DAY));
const monthLabel = (iso: string) => new Date(Date.parse(iso)).toLocaleDateString(undefined, { month: "short", year: "numeric", timeZone: "UTC" });
const PLAY_STEPS = 90; // a full replay takes ~6 s whatever the span
const panel = "rounded-2xl border border-stone-200 bg-white dark:border-stone-800 dark:bg-stone-900";

export default function Graph() {
  const { slug } = useParams();
  const containerRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<any>(null);
  const [mode, setMode] = useState<"3d" | "2d">(() => { try { return (localStorage.getItem("atlas-graph-mode") as "3d" | "2d") || "3d"; } catch { return "3d"; } });
  const [selected, setSelected] = useState<Node | null>(null);
  const [hovered, setHovered] = useState<string | null>(null);
  const [focus, setFocus] = useState<{ id: string; depth: number } | null>(null);
  const [q, setQ] = useState("");
  const [kinds, setKinds] = useState<Set<string>>(new Set(["reference", "note"]));
  const [linkKinds, setLinkKinds] = useState<Set<string>>(new Set(["citation", "note-link", "note-citation"]));
  const [hideOrphans, setHideOrphans] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [ready, setReady] = useState(false);
  // #506: time-lapse cursor (days after the first filing day; null = today, no time filter) + tag filter
  const [cursor, setCursor] = useState<number | null>(null);
  const [playing, setPlaying] = useState(false);
  const [tag, setTag] = useState<string | null>(null);
  const nodeCache = useRef(new Map<string, Node>()); // same node objects across data changes → positions persist
  useEffect(() => { try { localStorage.setItem("atlas-graph-mode", mode); } catch { /* private mode */ } }, [mode]);

  const graph = useQuery({ queryKey: ["graph", slug], queryFn: () => api<GraphData>(`/projects/${slug}/graph/`) });
  const data = graph.data;
  const cachedFor = useRef<GraphData | undefined>(undefined);
  const first = data?.stats.first ?? null;
  const today = todayIso();
  const span = first ? daysBetween(first, today) : 0;
  const cursorIso = first && cursor != null && cursor < span ? addDays(first, cursor) : null; // null = no time filter
  const noteTags = useMemo(() => {
    const m = new Map<string, number>();
    for (const n of data?.nodes ?? []) if (n.type === "note") for (const t of n.tags ?? []) m.set(t, (m.get(t) ?? 0) + 1);
    return [...m.entries()].sort((a, b) => b[1] - a[1] || a[0].localeCompare(b[0]));
  }, [data]);

  // neighbours index
  const neighbours = useMemo(() => {
    const m = new Map<string, Set<string>>();
    for (const l of data?.links ?? []) { const s = endId(l.source), t = endId(l.target); (m.get(s) ?? m.set(s, new Set()).get(s)!).add(t); (m.get(t) ?? m.set(t, new Set()).get(t)!).add(s); }
    return m;
  }, [data]);
  const matches = useMemo(() => {
    const needle = q.trim().toLowerCase(); if (!needle) return new Set<string>();
    return new Set((data?.nodes ?? []).filter((n) => n.label.toLowerCase().includes(needle) || n.title.toLowerCase().includes(needle) || (n.authors ?? "").toLowerCase().includes(needle)).map((n) => n.id));
  }, [q, data]);
  // #506: with a tag chosen, notes carrying it and the papers they cite stay lit; the rest dims
  const tagged = useMemo(() => {
    if (!tag || !data) return null;
    const lit = new Set<string>();
    for (const n of data.nodes) if (n.type === "note" && (n.tags ?? []).includes(tag)) { lit.add(n.id); for (const nb of neighbours.get(n.id) ?? []) if (nb.startsWith("ref-")) lit.add(nb); }
    return lit;
  }, [tag, data, neighbours]);
  const visible = useMemo(() => {
    if (!data) return null;
    let ids = new Set(data.nodes.filter((n) => kinds.has(n.type) && (!cursorIso || !n.created_at || n.created_at <= cursorIso)).map((n) => n.id));
    if (focus) {
      const keep = new Set<string>([focus.id]); let frontier = [focus.id];
      for (let d = 0; d < focus.depth; d++) { const next: string[] = []; for (const id of frontier) for (const nb of neighbours.get(id) ?? []) if (!keep.has(nb)) { keep.add(nb); next.push(nb); } frontier = next; }
      ids = new Set([...ids].filter((id) => keep.has(id)));
    }
    const links = data.links.filter((l) => linkKinds.has(l.kind) && ids.has(endId(l.source)) && ids.has(endId(l.target)));
    if (hideOrphans) { const linked = new Set<string>(); for (const l of links) { linked.add(endId(l.source)); linked.add(endId(l.target)); } ids = new Set([...ids].filter((id) => linked.has(id) || id === focus?.id)); }
    // copies (force-graph mutates nodes in place), cached by id so a time-lapse tick or a filter keeps every node where it was
    const cache = nodeCache.current;
    if (cachedFor.current !== data) { cache.clear(); cachedFor.current = data; } // fresh facts after a refetch
    const nodes = data.nodes.filter((n) => ids.has(n.id)).map((n) => cache.get(n.id) ?? (cache.set(n.id, { ...n }), cache.get(n.id)!));
    return { nodes, links: links.map((l) => ({ source: endId(l.source), target: endId(l.target), kind: l.kind })) };
  }, [data, kinds, linkKinds, hideOrphans, focus, neighbours, cursorIso]);
  const visibleRef = useRef(visible); visibleRef.current = visible;
  const shown = useMemo(() => ({ papers: visible?.nodes.filter((n) => n.type === "reference").length ?? 0, notes: visible?.nodes.filter((n) => n.type === "note").length ?? 0 }), [visible]);

  // #506: play advances the cursor from the first day to today in ~PLAY_STEPS ticks
  useEffect(() => {
    if (!playing) return;
    const step = Math.max(1, Math.ceil(span / PLAY_STEPS));
    const id = window.setInterval(() => setCursor((c) => { const next = (c ?? 0) + step; if (next >= span) { setPlaying(false); return null; } return next; }), 70);
    return () => window.clearInterval(id);
  }, [playing, span]);
  const play = () => { if (playing) { setPlaying(false); return; } if (cursor == null || cursor >= span) setCursor(0); setPlaying(true); };

  const isDark = () => document.documentElement.classList.contains("dark");
  const nodeColor = useCallback((n: Node) => {
    const base = COLORS[n.group] ?? "#a8a29e";
    const active = hovered ?? selected?.id ?? null;
    const dim = (active && n.id !== active && !(neighbours.get(active)?.has(n.id))) || (matches.size > 0 && !matches.has(n.id)) || (tagged && !tagged.has(n.id));
    return dim ? base + "33" : base;
  }, [hovered, selected, neighbours, matches, tagged]);

  // build / rebuild the graph when the library or mode change; data changes flow through graphData() below
  useEffect(() => {
    if (!visibleRef.current || !containerRef.current) return;
    let cancelled = false;
    (async () => {
      await loadScript(LIB[mode]);
      if (cancelled || !containerRef.current) return;
      const factory = mode === "3d" ? window.ForceGraph3D : window.ForceGraph;
      if (!factory) return;
      graphRef.current?._destructor?.();
      containerRef.current.innerHTML = "";
      const g = factory()(containerRef.current)
        .graphData(visibleRef.current)
        .nodeLabel((n: Node) => `<div style="font:12px system-ui;max-width:260px"><b>${n.label}</b><br/>${n.title}</div>`)
        .nodeVal((n: Node) => n.size)
        .nodeColor(nodeColor)
        .linkColor((l: Edge) => (LINK_COLORS[l.kind] ?? "#94a3b8") + (isDark() ? "99" : "77"))
        .linkWidth((l: Edge) => (l.kind === "note-citation" ? 1.5 : 1))
        .width(containerRef.current.clientWidth)
        .height(600)
        .onNodeClick((n: Node) => { setSelected(n); if (mode === "3d" && n && typeof (n as any).x === "number") { const d = 120; const { x, y, z } = n as any; const r = 1 + d / Math.hypot(x, y, z || 1); g.cameraPosition({ x: x * r, y: y * r, z: (z || 0) * r }, n, 900); } })
        .onNodeHover((n: Node | null) => setHovered(n?.id ?? null))
        .onBackgroundClick(() => setSelected(null));
      if (mode === "3d") { g.backgroundColor(isDark() ? "#05070f" : "#fafaf9").linkOpacity(0.55).linkDirectionalParticles((l: Edge) => (l.kind === "citation" ? 1 : 0)).linkDirectionalParticleWidth(1.2).linkDirectionalParticleSpeed(0.004); }
      else { g.backgroundColor(isDark() ? "#05070f" : "#fafaf9").linkDirectionalArrowLength(3).linkDirectionalArrowRelPos(1); }
      graphRef.current = g; setReady(true);
    })();
    return () => { cancelled = true; };
  }, [mode, visible == null]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => { if (ready && visible) graphRef.current?.graphData(visible); }, [visible, ready]);
  useEffect(() => { graphRef.current?.nodeColor(nodeColor); }, [nodeColor]);
  useEffect(() => () => { graphRef.current?._destructor?.(); }, []);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") { if (focus) setFocus(null); else setSelected(null); } };
    window.addEventListener("keydown", onKey); return () => window.removeEventListener("keydown", onKey);
  }, [focus]);

  const focusOn = (id: string, depth = 1) => { setFocus({ id, depth }); const n = data?.nodes.find((x) => x.id === id) ?? null; setSelected(n); };
  const onSearchEnter = () => { const first = [...matches][0]; if (first) focusOn(first); };
  async function syncCitations() {
    setSyncing(true);
    await fetch(`/projects/${slug}/graph/sync/`, { method: "POST", headers: { "X-CSRFToken": csrfToken() }, redirect: "manual" });
    setTimeout(() => setSyncing(false), 1500);
  }
  const toggle = (set: Set<string>, setter: (s: Set<string>) => void, key: string) => { const n = new Set(set); if (n.has(key)) n.delete(key); else n.add(key); setter(n); };
  const isEmpty = data != null && data.nodes.length === 0;
  const stats = data?.stats;
  const selNeighbours = selected ? [...(neighbours.get(selected.id) ?? [])].map((id) => data?.nodes.find((n) => n.id === id)).filter(Boolean) as Node[] : [];

  // #409: a failed graph fetch shows an error with retry instead of an empty canvas
  const gate = queryGate(graph, { message: "Couldn't load the graph." });
  if (gate) return gate;
  return (
    <div>
      <nav className="mb-4 text-sm text-stone-500 dark:text-stone-400"><Link to="/projects" className="hover:underline">Projects</Link> / <Link to={`/projects/${slug}`} className="hover:underline">{slug}</Link> / Graph</nav>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <h1 className="font-display text-3xl font-bold tracking-tight dark:text-stone-100">Knowledge graph {stats && <span className="text-gradient">· {stats.references + stats.notes} nodes</span>}</h1>
        {stats && <p className="text-sm text-stone-400">{stats.references} papers · {stats.notes} notes · {stats.links} links{stats.orphans ? ` · ${stats.orphans} unconnected` : ""}</p>}
        <div className="ml-auto flex items-center gap-2 text-xs">
          <div className="inline-flex overflow-hidden rounded-lg border border-stone-300 dark:border-stone-700" role="group" aria-label="Dimensions">
            {(["3d", "2d"] as const).map((m) => <button key={m} type="button" onClick={() => setMode(m)} aria-pressed={mode === m} className={`px-3 py-1.5 font-medium transition-colors ${mode === m ? "bg-indigo-600 text-white" : "text-stone-600 hover:bg-stone-100 dark:text-stone-300 dark:hover:bg-stone-800"}`}>{m.toUpperCase()}</button>)}
          </div>
          <button type="button" onClick={syncCitations} disabled={syncing} className="inline-flex items-center gap-1.5 rounded-lg border border-stone-300 px-2.5 py-1.5 font-medium text-stone-600 hover:border-indigo-300 disabled:opacity-50 dark:border-stone-700 dark:text-stone-300"><RefreshCw className={`h-3.5 w-3.5 ${syncing ? "animate-spin" : ""}`} aria-hidden="true" />{syncing ? "Sync queued…" : "Sync citations"}</button>
        </div>
      </div>

      <div className={`${panel} rise mb-3 flex flex-wrap items-center gap-x-4 gap-y-2 px-3 py-2 text-xs`} style={{ ["--i" as string]: 0 }} data-testid="graph-toolbar">
        <label className="relative">
          <Search className="pointer-events-none absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-stone-400" aria-hidden="true" />
          <input type="search" value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") onSearchEnter(); }} placeholder="Find a paper or note… Enter focuses" className="w-64 rounded-lg border border-stone-200 bg-white py-1.5 pl-7 pr-2 placeholder:text-stone-400 focus:border-indigo-400 focus:outline-none dark:border-stone-700 dark:bg-stone-800" aria-label="Find a node" />
          {q && <span className="absolute -right-1 top-1/2 -translate-y-1/2 translate-x-full text-stone-400">{matches.size} match{matches.size === 1 ? "" : "es"}</span>}
        </label>
        <span className="ml-8 flex items-center gap-1.5">
          {LEGEND.map(([k, label]) => { const kind = k === "note" ? "note" : "reference"; const on = kinds.has(kind); return <button key={k} type="button" onClick={() => toggle(kinds, setKinds, kind)} className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 transition-opacity ${on ? "" : "opacity-40"} hover:bg-stone-100 dark:hover:bg-stone-800`} aria-pressed={on} title={k === "note" ? "Show notes" : "Show papers"}><span className="inline-block h-2 w-2 rounded-full" style={{ background: COLORS[k] }} />{label}</button>; })}
        </span>
        <span className="flex items-center gap-1.5">
          {LINK_LEGEND.map(([k, label]) => { const on = linkKinds.has(k); return <button key={k} type="button" onClick={() => toggle(linkKinds, setLinkKinds, k)} className={`inline-flex items-center gap-1 rounded-full px-2 py-0.5 transition-opacity ${on ? "" : "opacity-40"} hover:bg-stone-100 dark:hover:bg-stone-800`} aria-pressed={on}><span className="inline-block h-0.5 w-3" style={{ background: LINK_COLORS[k] }} />{label}</button>; })}
        </span>
        <label className="flex items-center gap-1.5 text-stone-500"><input type="checkbox" checked={hideOrphans} onChange={(e) => setHideOrphans(e.target.checked)} className="accent-indigo-500" />hide unconnected</label>
        {focus && <button type="button" onClick={() => setFocus(null)} className="inline-flex items-center gap-1 rounded-full bg-indigo-500/15 px-2 py-0.5 text-indigo-700 dark:text-indigo-200"><Crosshair className="h-3 w-3" aria-hidden="true" />focused · depth {focus.depth} <button type="button" onClick={(e) => { e.stopPropagation(); setFocus({ ...focus, depth: focus.depth === 1 ? 2 : 1 }); }} className="underline">{focus.depth === 1 ? "widen" : "narrow"}</button><X className="h-3 w-3" aria-hidden="true" /></button>}
      </div>

      {first && span > 0 && (
        <div className={`${panel} rise mb-3 flex flex-wrap items-center gap-3 px-3 py-2 text-xs`} style={{ ["--i" as string]: 1 }} data-testid="graph-timeline">
          <button type="button" onClick={play} data-testid="timeline-play" aria-label={playing ? "Pause the time-lapse" : "Play the time-lapse"} className="inline-flex h-7 w-7 items-center justify-center rounded-full bg-indigo-600 text-white hover:bg-indigo-700">{playing ? <Pause className="h-3.5 w-3.5" aria-hidden="true" /> : <Play className="h-3.5 w-3.5" aria-hidden="true" />}</button>
          <span className="tabular-nums text-stone-400">{monthLabel(first)}</span>
          <input type="range" min={0} max={span} value={cursor ?? span} onChange={(e) => { setPlaying(false); const v = Number(e.target.value); setCursor(v >= span ? null : v); }} data-testid="timeline-slider" aria-label="Time-lapse position" className="min-w-40 flex-1 accent-indigo-500" />
          <span className="tabular-nums text-stone-400">{monthLabel(today)}</span>
          <span className="min-w-52 font-medium text-stone-600 dark:text-stone-300" data-testid="timeline-caption">{monthLabel(cursorIso ?? today)} · {shown.papers} paper{shown.papers === 1 ? "" : "s"} · {shown.notes} note{shown.notes === 1 ? "" : "s"}{cursorIso ? <button type="button" onClick={() => { setPlaying(false); setCursor(null); }} className="ml-2 text-indigo-600 underline dark:text-indigo-300">today</button> : null}</span>
        </div>
      )}
      {noteTags.length > 0 && (
        <div className="mb-3 flex flex-wrap items-center gap-1.5 px-1 text-xs" data-testid="tag-filter">
          <span className="mr-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-stone-400">Tags</span>
          {noteTags.map(([t, count]) => <button key={t} type="button" onClick={() => setTag(tag === t ? null : t)} aria-pressed={tag === t} className={`rounded-full border px-2 py-0.5 transition-colors ${tag === t ? "border-teal-400 bg-teal-500/15 text-teal-800 dark:text-teal-200" : "border-stone-200 text-stone-500 hover:border-teal-300 dark:border-stone-700 dark:text-stone-400"}`}>#{t} <span className="tabular-nums opacity-70">{count}</span></button>)}
          {tag && <button type="button" onClick={() => setTag(null)} className="ml-1 text-stone-400 underline">clear</button>}
        </div>
      )}

      <div className={`${panel} rise relative overflow-hidden`} style={{ ["--i" as string]: 2 }}>
        {/* the library owns everything inside this div — React must never render children here */}
        <div ref={containerRef} style={{ height: 600 }} data-testid="graph-canvas" />
        {isEmpty ? (
          <div className="absolute inset-0 flex flex-col items-center justify-center px-8 text-center">
            <p className="mb-2 text-3xl text-stone-300" aria-hidden="true">⬡</p>
            <p className="mb-1 text-sm font-medium text-stone-600 dark:text-stone-300">Nothing to graph yet</p>
            <p className="mb-4 max-w-xs text-sm text-stone-400">File papers into this project and write notes that cite them (@key) or link each other ([[title]]); they appear here wired together.</p>
            <Link to={`/library`} className="rounded-lg border border-stone-300 px-3 py-1.5 text-sm font-medium text-stone-700 hover:border-indigo-300 dark:border-stone-700 dark:text-stone-300">Open the Library</Link>
          </div>
        ) : !ready ? <p className="pointer-events-none absolute left-4 top-4 text-sm text-stone-400">Loading graph…</p> : null}
        {stats && stats.hubs.length > 0 && !selected && (
          <div className="pointer-events-auto absolute left-3 top-3 rounded-xl border border-stone-200 bg-white/90 px-3 py-2 text-[11px] shadow-sm backdrop-blur dark:border-stone-800 dark:bg-stone-900/90" data-testid="hubs">
            <p className="mb-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-stone-400">Hubs</p>
            <ul className="space-y-0.5">{stats.hubs.map((h) => <li key={h.id}><button type="button" onClick={() => focusOn(h.id)} className="flex w-full items-center gap-2 text-left text-stone-600 hover:text-indigo-700 dark:text-stone-300 dark:hover:text-indigo-300"><span className="truncate">{h.label}</span><span className="ml-auto tabular-nums text-stone-400">{h.degree}</span></button></li>)}</ul>
          </div>
        )}
        {selected && (
          <aside className="absolute right-3 top-3 w-72 rounded-2xl border border-stone-200 bg-white/95 p-4 shadow-xl backdrop-blur dark:border-stone-800 dark:bg-stone-900/95" data-testid="node-panel">
            <button type="button" onClick={() => setSelected(null)} className="absolute right-2.5 top-2.5 text-stone-400 hover:text-stone-600 dark:hover:text-stone-200" aria-label="Close"><X className="h-4 w-4" aria-hidden="true" /></button>
            <p className="mb-1 flex items-center gap-1.5 pr-5 text-[10px] font-semibold uppercase tracking-[0.14em] text-stone-400"><span className="inline-block h-2 w-2 rounded-full" style={{ background: COLORS[selected.group] }} />{selected.type === "reference" ? (selected.group.replace("_", " ")) : "note"}</p>
            <p className="font-display text-sm font-semibold leading-snug text-stone-900 dark:text-stone-100">{selected.title}</p>
            {selected.type === "reference" ? (
              <p className="mt-1 text-[11px] text-stone-400">{[selected.authors, selected.year, selected.venue].filter(Boolean).join(" · ")}{selected.citations != null ? ` · ${selected.citations} citations` : ""}{selected.highlights ? ` · ${selected.highlights} highlight${selected.highlights === 1 ? "" : "s"}` : ""}{selected.has_pdf ? " · PDF" : ""}{selected.created_at ? ` · filed ${selected.created_at}` : ""}</p>
            ) : (
              <p className="mt-1 text-[11px] text-stone-400">{selected.words} words · edited {selected.updated_at}{selected.tags?.length ? ` · ${selected.tags.map((t) => "#" + t).join(" ")}` : ""}</p>
            )}
            <div className="mt-2 flex flex-wrap gap-1.5 text-[11px]">
              {selected.app_url && <Link to={selected.app_url} className="inline-flex items-center gap-1 rounded-md bg-indigo-600 px-2 py-0.5 font-medium text-white hover:bg-indigo-700">Open<ExternalLink className="h-3 w-3" aria-hidden="true" /></Link>}
              <button type="button" onClick={() => focusOn(selected.id, focus?.id === selected.id ? focus.depth : 1)} className="inline-flex items-center gap-1 rounded-md border border-stone-300 px-2 py-0.5 text-stone-600 hover:border-indigo-300 dark:border-stone-700 dark:text-stone-300"><Crosshair className="h-3 w-3" aria-hidden="true" />{focus?.id === selected.id ? "Focused" : "Focus"}</button>
            </div>
            <p className="mt-3 text-[10px] font-semibold uppercase tracking-[0.14em] text-stone-400">Connected · {selNeighbours.length}</p>
            <ul className="mt-1 max-h-40 space-y-0.5 overflow-auto text-xs">
              {selNeighbours.map((n) => <li key={n.id}><button type="button" onClick={() => { setSelected(n); if (focus) setFocus({ id: n.id, depth: focus.depth }); }} className="flex w-full items-center gap-1.5 text-left text-stone-600 hover:text-indigo-700 dark:text-stone-300 dark:hover:text-indigo-300"><span className="inline-block h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: COLORS[n.group] }} /><span className="truncate">{n.label}</span></button></li>)}
              {selNeighbours.length === 0 && <li className="text-stone-400">Unconnected — cite it from a note (@key) or sync citations.</li>}
            </ul>
          </aside>
        )}
      </div>
      <p className="mt-2 text-xs text-stone-400">Node size = citations (papers) or length (notes) · colour = reading status · hover highlights neighbours · click for details · Esc clears · ▶ replays the graph as it was filed</p>
    </div>
  );
}
