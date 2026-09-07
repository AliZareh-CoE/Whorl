/** Constellation (#387, Observatory second pass): the project's papers and notes as a small
 *  sky under the overview header — nodes from GET /projects/{slug}/graph/, laid out by a tiny
 *  force pass, drifting slowly, hover for the title, click to open. Nothing to draw → nothing
 *  rendered (an empty box would say less than no box). */
import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../../api";

type Node = { id: string; type: string; label: string; title?: string; group?: string; size?: number; app_url?: string; degree?: number };
type LinkT = { source: string; target: string; kind: string };
type Graph = { nodes: Node[]; links: LinkT[] };
type Star = { id: string; x: number; y: number; vx: number; vy: number; r: number; color: string; title: string; url: string; type: string; phase: number };

const NOTE = "#2dd4bf";
const MAX_NODES = 320;
const H = 132;

function hexAlpha(hex: string, alpha: number): string {
  const m = /^#([0-9a-f]{6})$/i.exec(hex);
  if (!m) return hex;
  const n = parseInt(m[1], 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${alpha})`;
}

/** A few dozen ticks of charge + springs + gravity, then rest: enough for a sky, cheap enough for a header. */
export function layout(nodes: Node[], links: LinkT[], width: number, height: number, accent: string): { stars: Star[]; edges: [number, number][] } {
  const seed = nodes.length * 7919;
  let s = seed;
  const rand = () => { s = (s * 1103515245 + 12345) & 0x7fffffff; return s / 0x7fffffff; };
  const stars: Star[] = nodes.map((n, i) => ({
    id: n.id,
    x: width * (0.08 + 0.84 * rand()),
    y: height * (0.15 + 0.7 * rand()),
    vx: 0, vy: 0,
    r: n.type === "note" ? 2.2 : Math.max(1.4, Math.min(4.2, 1.2 + Math.sqrt(n.size ?? 4) * 0.55)),
    color: n.type === "note" ? NOTE : n.group === "to_read" ? hexAlpha(accent, 0.55) : accent,
    title: n.title || n.label,
    url: n.app_url || "",
    type: n.type,
    phase: (i * 0.618) % 1,
  }));
  const index = new Map(stars.map((st, i) => [st.id, i]));
  const edges: [number, number][] = [];
  for (const l of links) {
    const a = index.get(typeof l.source === "string" ? l.source : (l.source as { id: string }).id);
    const b = index.get(typeof l.target === "string" ? l.target : (l.target as { id: string }).id);
    if (a !== undefined && b !== undefined && a !== b) edges.push([a, b]);
  }
  // A wide, short band: repulsion works sideways only (n² charges in a 130 px band just pile
  // up on the walls); each star keeps a home height it springs back to, links tug gently.
  const cx = width / 2;
  const home = stars.map(() => height * (0.14 + 0.72 * rand()));
  const charge = Math.max(6, Math.min(40, (width * 0.9) / stars.length));
  const pad = 12;
  for (let tick = 0; tick < 110; tick++) {
    const k = 1 - tick / 110;
    for (let i = 0; i < stars.length; i++) {
      const a = stars[i];
      for (let j = i + 1; j < stars.length; j++) {
        const b = stars[j];
        let dx = a.x - b.x;
        const dy = a.y - b.y;
        if (Math.abs(dx) < 0.5) dx = rand() - 0.5;
        const d = Math.max(Math.sqrt(dx * dx + dy * dy), 18);
        const f = (charge * k * Math.sign(dx)) / d; // 1/d: long reach, so the band fills
        a.vx += f; b.vx -= f;
      }
      a.vx += (cx - a.x) * 0.0005 * k;
      a.vy += (home[i] - a.y) * 0.12;
    }
    for (const [i, j] of edges) {
      const a = stars[i], b = stars[j];
      const dx = b.x - a.x, dy = b.y - a.y;
      const d = Math.sqrt(dx * dx + dy * dy) || 1;
      const f = ((d - 110) / d) * 0.006 * k;
      a.vx += dx * f; a.vy += dy * f * 0.25; b.vx -= dx * f; b.vy -= dy * f * 0.25;
    }
    for (const st of stars) {
      const vmax = 5;
      st.vx = Math.max(-vmax, Math.min(vmax, st.vx)); st.vy = Math.max(-vmax, Math.min(vmax, st.vy));
      st.x += st.vx; st.y += st.vy;
      if (st.x < pad) st.vx += (pad - st.x) * 0.3; if (st.x > width - pad) st.vx -= (st.x - (width - pad)) * 0.3;
      st.x = Math.max(4, Math.min(width - 4, st.x)); st.y = Math.max(pad, Math.min(height - pad, st.y));
      st.vx *= 0.55; st.vy *= 0.5;
    }
  }
  return { stars, edges };
}

export default function Constellation({ slug, accent }: { slug: string; accent: string }) {
  const navigate = useNavigate();
  const wrap = useRef<HTMLDivElement>(null);
  const canvas = useRef<HTMLCanvasElement>(null);
  const [width, setWidth] = useState(0);
  const [hover, setHover] = useState<Star | null>(null);
  const graph = useQuery({ queryKey: ["graph", slug], queryFn: () => api<Graph>(`/projects/${slug}/graph/`), staleTime: 5 * 60_000 });
  const accentHex = /^#[0-9a-f]{6}$/i.test(accent) ? accent : "#7c6cff";

  useEffect(() => {
    const el = wrap.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setWidth(el.clientWidth));
    ro.observe(el);
    setWidth(el.clientWidth);
    return () => ro.disconnect();
  }, [graph.data]);

  const sky = useMemo(() => {
    if (!graph.data || width < 40) return null;
    let nodes = graph.data.nodes;
    if (nodes.length > MAX_NODES) nodes = [...nodes].sort((a, b) => (b.degree ?? 0) - (a.degree ?? 0)).slice(0, MAX_NODES);
    if (nodes.length < 2) return null;
    return layout(nodes, graph.data.links, width, H, accentHex);
  }, [graph.data, width, accentHex]);

  useEffect(() => {
    const c = canvas.current;
    if (!c || !sky) return;
    const ctx = c.getContext("2d");
    if (!ctx) return;
    const dpr = Math.min(2, window.devicePixelRatio || 1);
    c.width = Math.round(width * dpr); c.height = Math.round(H * dpr);
    const still = window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
    let raf = 0;
    const draw = (t: number) => {
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      ctx.clearRect(0, 0, width, H);
      const dark = document.documentElement.classList.contains("dark");
      const drift = (st: Star) => still ? [st.x, st.y] : [st.x + Math.sin(t / 4200 + st.phase * 6.28) * 2.2, st.y + Math.cos(t / 5100 + st.phase * 6.28) * 1.6];
      ctx.lineWidth = 0.7;
      for (const [i, j] of sky.edges) {
        const [ax, ay] = drift(sky.stars[i]); const [bx, by] = drift(sky.stars[j]);
        ctx.strokeStyle = dark ? "rgba(165,180,252,0.16)" : "rgba(79,70,229,0.14)";
        ctx.beginPath(); ctx.moveTo(ax, ay); ctx.lineTo(bx, by); ctx.stroke();
      }
      for (const st of sky.stars) {
        const [x, y] = drift(st);
        const tw = still ? 1 : 0.8 + 0.2 * Math.sin(t / 900 + st.phase * 12);
        const hovered = hover?.id === st.id;
        if (dark || hovered) {
          const g = ctx.createRadialGradient(x, y, 0, x, y, st.r * (hovered ? 5 : 3.2));
          g.addColorStop(0, hexAlpha(st.color.startsWith("#") ? st.color : accentHex, 0.35 * tw));
          g.addColorStop(1, "rgba(0,0,0,0)");
          ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y, st.r * (hovered ? 5 : 3.2), 0, 6.283); ctx.fill();
        }
        ctx.fillStyle = st.color; ctx.globalAlpha = tw; ctx.beginPath(); ctx.arc(x, y, hovered ? st.r + 1.2 : st.r, 0, 6.283); ctx.fill(); ctx.globalAlpha = 1;
      }
      if (!still) raf = requestAnimationFrame(draw);
    };
    raf = requestAnimationFrame(draw);
    const onVis = () => { if (document.hidden) cancelAnimationFrame(raf); else raf = requestAnimationFrame(draw); };
    document.addEventListener("visibilitychange", onVis);
    return () => { cancelAnimationFrame(raf); document.removeEventListener("visibilitychange", onVis); };
  }, [sky, width, hover, accentHex]);

  // the wrapper must mount before the layout can know its width — so gate on the data, not the sky
  if (!graph.data || graph.data.nodes.length < 2) return null;
  const refs = graph.data.nodes.filter((n) => n.type === "reference").length;
  const notes = graph.data.nodes.length - refs;
  const nearest = (e: React.MouseEvent<HTMLCanvasElement>): Star | null => {
    if (!sky) return null;
    const r = e.currentTarget.getBoundingClientRect();
    const x = e.clientX - r.left, y = e.clientY - r.top;
    let best: Star | null = null, bd = 14 * 14;
    for (const st of sky.stars) { const d = (st.x - x) ** 2 + (st.y - y) ** 2; if (d < bd) { bd = d; best = st; } }
    return best;
  };
  return (
    <div ref={wrap} className="relative mb-5 overflow-hidden rounded-2xl border border-stone-200 bg-white/60 dark:border-stone-800 dark:bg-stone-950/40" data-testid="constellation" role="img" aria-label={`${refs} papers and ${notes} notes in this project, drawn as a constellation`}>
      <canvas ref={canvas} style={{ width: width || "100%", height: H, display: "block", cursor: hover ? "pointer" : "default" }} onMouseMove={(e) => setHover(nearest(e))} onMouseLeave={() => setHover(null)}
              onClick={(e) => { const st = nearest(e); if (st?.url) navigate(st.url); }} />
      {hover && (
        <div className="pointer-events-none absolute left-3 top-2 max-w-sm truncate rounded-md bg-stone-900/90 px-2 py-1 text-[11px] text-stone-100 shadow dark:bg-stone-800/95" style={{ left: Math.min(width - 260, hover.x + 10), top: Math.max(4, hover.y - 26) }}>
          <span className="mr-1 text-stone-400">{hover.type === "note" ? "note" : "paper"}</span>{hover.title}
        </div>
      )}
      <p className="pointer-events-none absolute bottom-2 right-3 text-[10px] uppercase tracking-[0.14em] text-stone-400">
        {refs} papers · {notes} notes · {sky?.edges.length ?? 0} links · <Link to={`/projects/${slug}/graph`} className="pointer-events-auto normal-case tracking-normal text-indigo-500 hover:underline dark:text-indigo-300">open the graph</Link>
      </p>
    </div>
  );
}
