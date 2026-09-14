/** Plan v2 slice 2 — the roadmap: phases as draggable bars on a time axis, milestones as
 *  diamonds you can slide to a new due date, a today line, and an honest health reading per
 *  phase (behind / on track / ahead / overdue …) with a finish forecast from the completion pace.
 *  Data: GET /projects/{slug}/roadmap/; edits go through PATCH /phases/{id}/ and /milestones/{id}/.
 *  #514: dependencies are drawn as arrows between diamonds (blocker → dependant); a waiting
 *  milestone is hollow, a date conflict amber; hovering a diamond lights its whole chain. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { api } from "../../api";
import { Skeleton } from "../../../components/Skeleton";

type MilestoneRow = { id: number; title: string; due_date: string | null; done: boolean; overdue: boolean; blocked?: boolean; blocked_by?: number[]; conflict?: boolean; slack?: number | null; baseline?: string | null; moves?: number; slipped?: number | null };
type PhaseRow = { id: number; name: string; order: number; status: string; start: string; end: string; inferred: boolean; progress: number; milestones: MilestoneRow[]; state: string; label: string; forecast_end: string | null };
type Chain = { ids: number[]; titles: string[]; from: string | null; to: string | null; days: number; slack: number | null }; // #515
type RoadmapData = { project: string; today: string; range_start: string; range_end: string; phases: PhaseRow[]; critical_chain?: Chain };

const DAY = 864e5;
const PX_PER_DAY = 5;
const LEFT_W = 232;
const ROW_H = 56;

function dayOf(iso: string): number { const [y, m, d] = iso.split("-").map(Number); return Math.round(Date.UTC(y, m - 1, d) / DAY); }
function isoOf(day: number): string { return new Date(day * DAY).toISOString().slice(0, 10); }
function monthStarts(fromDay: number, toDay: number): { day: number; label: string }[] {
  const out: { day: number; label: string }[] = [];
  const d = new Date(fromDay * DAY); d.setUTCDate(1);
  while (d.getTime() / DAY <= toDay) {
    const day = Math.round(d.getTime() / DAY);
    if (day >= fromDay) out.push({ day, label: d.toLocaleDateString(undefined, { month: "short", year: d.getUTCMonth() === 0 ? "numeric" : undefined, timeZone: "UTC" }) });
    d.setUTCMonth(d.getUTCMonth() + 1);
  }
  return out;
}

const STATE_BAR: Record<string, string> = {
  on_track: "bg-indigo-500/70", ahead: "bg-emerald-500/70", behind: "bg-amber-500/75", overdue: "bg-red-500/75", blocked: "bg-red-500/60",
  done: "bg-emerald-600/60", upcoming: "bg-stone-400/50 dark:bg-stone-500/40", empty: "bg-stone-300/40 dark:bg-stone-600/30",
};
const STATE_PILL: Record<string, string> = {
  on_track: "bg-indigo-500/15 text-indigo-700 dark:text-indigo-200", ahead: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300", behind: "bg-amber-500/15 text-amber-700 dark:text-amber-300",
  overdue: "bg-red-500/15 text-red-700 dark:text-red-300", blocked: "bg-red-500/15 text-red-700 dark:text-red-300", done: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300",
  upcoming: "bg-stone-100 text-stone-500 dark:bg-stone-800 dark:text-stone-300", empty: "bg-stone-100 text-stone-400 dark:bg-stone-800",
};

type Drag = { kind: "move" | "start" | "end"; phase: number; originX: number; start: number; end: number } | { kind: "milestone"; id: number; phase: number; originX: number; day: number };

export default function Roadmap({ slug, accent, onChanged }: { slug: string; accent: string; onChanged: () => void }) {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({ queryKey: ["roadmap", slug], queryFn: () => api<RoadmapData>(`/projects/${slug}/roadmap/`) });
  const [local, setLocal] = useState<RoadmapData | null>(null);
  useEffect(() => { if (data) setLocal(data); }, [data]);
  const drag = useRef<Drag | null>(null);
  const scroller = useRef<HTMLDivElement>(null);
  const [hover, setHover] = useState<string>("");
  const [chainOf, setChainOf] = useState<number | null>(null); // #514: the hovered milestone's dependency chain
  const invalidate = () => { queryClient.invalidateQueries({ queryKey: ["roadmap", slug] }); onChanged(); };
  const savePhase = useMutation({
    mutationFn: ({ id, start, end }: { id: number; start: string; end: string }) => api(`/phases/${id}/`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ target_start: start, target_end: end }) }),
    onSettled: invalidate,
  });
  const saveMilestone = useMutation({
    mutationFn: ({ id, due }: { id: number; due: string }) => api(`/milestones/${id}/`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ due_date: due }) }),
    onSettled: invalidate,
  });

  const view = local ?? data;
  const range = useMemo(() => {
    if (!view) return null;
    const from = Math.min(dayOf(view.range_start), dayOf(view.today)) - 14;
    const to = Math.max(dayOf(view.range_end), dayOf(view.today)) + 21;
    return { from, to, width: (to - from) * PX_PER_DAY };
  }, [view]);
  const x = (day: number) => (range ? (day - range.from) * PX_PER_DAY : 0);

  // scroll so today sits a third of the way in on first render
  useEffect(() => {
    if (!range || !view || !scroller.current) return;
    const el = scroller.current;
    el.scrollLeft = Math.max(0, x(dayOf(view.today)) - el.clientWidth / 3);
  }, [range?.from, view?.today]); // eslint-disable-line react-hooks/exhaustive-deps

  useEffect(() => {
    const move = (e: PointerEvent) => {
      const d = drag.current; if (!d || !local) return;
      const delta = Math.round((e.clientX - d.originX) / PX_PER_DAY);
      setLocal({
        ...local,
        phases: local.phases.map((p) => {
          if (d.kind === "milestone") {
            if (p.id !== d.phase) return p;
            return { ...p, milestones: p.milestones.map((m) => (m.id === d.id ? { ...m, due_date: isoOf(d.day + delta) } : m)) };
          }
          if (p.id !== d.phase) return p;
          let s = d.start, en = d.end;
          if (d.kind === "move") { s += delta; en += delta; }
          if (d.kind === "start") s = Math.min(d.start + delta, en);
          if (d.kind === "end") en = Math.max(d.end + delta, s);
          return { ...p, start: isoOf(s), end: isoOf(en), inferred: false };
        }),
      });
    };
    const up = () => {
      const d = drag.current; if (!d || !local) return;
      drag.current = null;
      document.body.style.cursor = "";
      const p = local.phases.find((ph) => ph.id === d.phase);
      if (!p) return;
      if (d.kind === "milestone") { const m = p.milestones.find((mm) => mm.id === d.id); if (m?.due_date) saveMilestone.mutate({ id: m.id, due: m.due_date }); }
      else savePhase.mutate({ id: p.id, start: p.start, end: p.end });
    };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
    return () => { window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up); };
  }, [local, savePhase, saveMilestone]);

  // keyboard: ←/→ move a focused phase bar or milestone by a day (Shift: a week)
  const nudge = (p: PhaseRow, delta: number, m?: MilestoneRow) => {
    if (!local) return;
    if (m && m.due_date) { const due = isoOf(dayOf(m.due_date) + delta); setLocal({ ...local, phases: local.phases.map((ph) => (ph.id === p.id ? { ...ph, milestones: ph.milestones.map((mm) => (mm.id === m.id ? { ...mm, due_date: due } : mm)) } : ph)) }); saveMilestone.mutate({ id: m.id, due }); return; }
    const start = isoOf(dayOf(p.start) + delta), end = isoOf(dayOf(p.end) + delta);
    setLocal({ ...local, phases: local.phases.map((ph) => (ph.id === p.id ? { ...ph, start, end, inferred: false } : ph)) });
    savePhase.mutate({ id: p.id, start, end });
  };
  const onKey = (e: React.KeyboardEvent, p: PhaseRow, m?: MilestoneRow) => {
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight") return;
    e.preventDefault();
    nudge(p, (e.key === "ArrowRight" ? 1 : -1) * (e.shiftKey ? 7 : 1), m);
  };
  const begin = (e: React.PointerEvent, d: Drag) => { e.preventDefault(); e.stopPropagation(); drag.current = d; document.body.style.cursor = d.kind === "move" || d.kind === "milestone" ? "grabbing" : "ew-resize"; };

  // #514: diamond centres and dependency edges for the arrow overlay
  const geometry = useMemo(() => {
    if (!view || !range) return { centres: new Map<number, { x: number; y: number }>(), edges: [] as { from: number; to: number; conflict: boolean }[], up: new Map<number, number[]>(), down: new Map<number, number[]>() };
    const centres = new Map<number, { x: number; y: number }>();
    const up = new Map<number, number[]>(), down = new Map<number, number[]>();
    view.phases.forEach((p, i) => p.milestones.forEach((m) => { if (m.due_date) centres.set(m.id, { x: (dayOf(m.due_date) - range.from) * PX_PER_DAY, y: 32 + i * ROW_H + 48 }); }));
    const edges: { from: number; to: number; conflict: boolean }[] = [];
    for (const p of view.phases) for (const m of p.milestones) for (const b of m.blocked_by ?? []) {
      up.set(m.id, [...(up.get(m.id) ?? []), b]); down.set(b, [...(down.get(b) ?? []), m.id]);
      if (centres.has(b) && centres.has(m.id)) edges.push({ from: b, to: m.id, conflict: !!m.conflict });
    }
    return { centres, edges, up, down };
  }, [view, range]);
  // #515: the critical chain — the edges that decide the plan's end are drawn heavier
  const critical = useMemo(() => new Set<number>(view?.critical_chain?.ids ?? []), [view]);
  const onChain = (from: number, to: number) => critical.has(from) && critical.has(to);
  const chain = useMemo(() => {
    if (chainOf == null) return null;
    const ids = new Set<number>([chainOf]);
    const walk = (start: number, next: Map<number, number[]>) => { const stack = [start]; while (stack.length) { const cur = stack.pop()!; for (const n of next.get(cur) ?? []) if (!ids.has(n)) { ids.add(n); stack.push(n); } } };
    walk(chainOf, geometry.up); walk(chainOf, geometry.down);
    return ids;
  }, [chainOf, geometry]);

  if (isLoading || !view || !range) return <div className="space-y-3"><Skeleton className="h-8 w-full" />{Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-12 w-full" />)}</div>;
  const months = monthStarts(range.from, range.to);
  const todayX = x(dayOf(view.today));

  return (
    <div className="rounded-2xl border border-stone-200 bg-white dark:border-stone-800 dark:bg-stone-900" data-testid="roadmap">
      <div className="flex items-center gap-3 border-b border-stone-100 px-4 py-2 text-[11px] text-stone-400 dark:border-stone-800">
        <span>drag a bar to move it · drag its edges to resize · slide a ◆ to change a due date · focus + ←/→ nudges a day, Shift a week · → waits for · dashed ◇ waiting · <span className="text-amber-600 dark:text-amber-300">◆</span> due before its blocker · dotted ◇ where a moved ◆ was first planned</span>
        <span className="ml-auto flex items-center gap-2"><span className="inline-block h-2 w-2 rounded-sm bg-amber-500/75" />behind<span className="inline-block h-2 w-2 rounded-sm bg-red-500/75" />overdue<span className="inline-block h-2 w-2 rounded-sm bg-emerald-500/70" />ahead / done<span className="inline-block h-2 w-3 rounded-sm border border-dashed border-stone-400" />suggested dates</span>
      </div>
      <div className="flex">
        <div className="shrink-0 border-r border-stone-100 dark:border-stone-800" style={{ width: LEFT_W }}>
          <div className="h-8 border-b border-stone-100 dark:border-stone-800" />
          {view.phases.map((p) => (
            <div key={p.id} className="flex flex-col justify-center border-b border-stone-50 px-3 dark:border-stone-800/60" style={{ height: ROW_H }}>
              <p className="truncate text-sm font-medium text-stone-800 dark:text-stone-100" title={p.name}><span className="mr-1.5 font-display text-stone-300 dark:text-stone-600">{String(p.order).padStart(2, "0")}</span>{p.name}</p>
              <p className="mt-0.5 flex items-center gap-1.5 text-[10px]"><span className={`rounded-full px-1.5 py-px ${STATE_PILL[p.state] ?? STATE_PILL.empty}`} title={p.label}>{p.label}</span></p>
            </div>
          ))}
          {view.phases.length === 0 && <p className="px-3 py-6 text-xs text-stone-400">No phases yet.</p>}
        </div>
        <div ref={scroller} className="relative flex-1 overflow-x-auto">
          <div className="relative" style={{ width: range.width, height: 32 + ROW_H * view.phases.length }}>
            {/* month header + gridlines */}
            {months.map((m) => (
              <div key={m.day} className="absolute top-0 h-full border-l border-stone-100 dark:border-stone-800/70" style={{ left: x(m.day) }}>
                <span className="absolute left-1.5 top-2 whitespace-nowrap text-[10px] font-medium uppercase tracking-wider text-stone-400">{m.label}</span>
              </div>
            ))}
            <div className="absolute left-0 right-0 top-8 border-t border-stone-100 dark:border-stone-800" />
            {/* today */}
            <div className="absolute top-0 h-full w-px" style={{ left: todayX, background: accent, boxShadow: `0 0 8px ${accent}` }} data-testid="today-line">
              <span className="absolute -left-4 top-[34px] rounded px-1 text-[9px] font-semibold uppercase tracking-wider text-white" style={{ background: accent }}>today</span>
            </div>
            {/* #514: dependency arrows, blocker → dependant; under the diamonds */}
            {geometry.edges.length > 0 && (
              <svg className="pointer-events-none absolute inset-0" width={range.width} height={32 + ROW_H * view.phases.length} data-testid="dependency-arrows" aria-hidden="true">
                <defs>
                  {/* markers do not inherit the path's colour in every engine: one per colour */}
                  <marker id="dep-arrow-indigo" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#818cf8" /></marker>
                  <marker id="dep-arrow-amber" viewBox="0 0 8 8" refX="7" refY="4" markerWidth="6" markerHeight="6" orient="auto"><path d="M0,0 L8,4 L0,8 z" fill="#f59e0b" /></marker>
                </defs>
                {geometry.edges.map((e) => {
                  const a = geometry.centres.get(e.from)!, b = geometry.centres.get(e.to)!;
                  const lit = !chain || (chain.has(e.from) && chain.has(e.to));
                  const dir = b.x >= a.x ? 1 : -1; // a conflict runs right-to-left: the blocker is due later
                  const dx = Math.max(24, Math.abs(b.x - a.x) / 2) * dir;
                  const d = `M${a.x + 7 * dir},${a.y} C${a.x + dx},${a.y} ${b.x - dx},${b.y} ${b.x - 9 * dir},${b.y}`;
                  const heavy = onChain(e.from, e.to);
                  return <path key={`${e.from}-${e.to}`} d={d} fill="none" stroke={e.conflict ? "#f59e0b" : "#818cf8"} strokeWidth={heavy ? (lit && chain ? 3 : 2.5) : lit && chain ? 2 : 1.25} markerEnd={e.conflict ? "url(#dep-arrow-amber)" : "url(#dep-arrow-indigo)"} className="transition-opacity" style={{ opacity: lit ? (e.conflict || heavy ? 0.95 : 0.7) : 0.15 }} data-testid="dependency-arrow" data-critical={heavy || undefined} />;
                })}
              </svg>
            )}
            {/* rows */}
            {view.phases.map((p, i) => {
              const s = dayOf(p.start), en = dayOf(p.end);
              const top = 32 + i * ROW_H;
              const w = Math.max(PX_PER_DAY * 2, (en - s + 1) * PX_PER_DAY);
              const forecast = p.forecast_end ? dayOf(p.forecast_end) : null;
              return (
                <div key={p.id} className="absolute left-0 right-0" style={{ top, height: ROW_H }}>
                  {forecast && forecast > en && (
                    <div className="absolute top-4 h-6 rounded-r-md border border-dashed border-amber-400/70 bg-[repeating-linear-gradient(45deg,transparent,transparent_4px,rgb(245_158_11/.18)_4px,rgb(245_158_11/.18)_8px)]" style={{ left: x(en + 1), width: (forecast - en) * PX_PER_DAY }} title={`At the current pace this phase finishes around ${p.forecast_end}`}>
                      <span className="absolute -top-3.5 left-1 whitespace-nowrap text-[9px] text-amber-600 dark:text-amber-300">forecast {p.forecast_end}</span>
                    </div>
                  )}
                  <div
                    role="slider" tabIndex={0} aria-label={`${p.name}: ${p.start} to ${p.end}`} aria-valuetext={`${p.start} → ${p.end}`} onKeyDown={(e) => onKey(e, p)}
                    onPointerDown={(e) => begin(e, { kind: "move", phase: p.id, originX: e.clientX, start: s, end: en })}
                    onMouseEnter={() => setHover(`${p.name} · ${p.start} → ${p.end}${p.inferred ? " (suggested)" : ""}`)} onMouseLeave={() => setHover("")}
                    className={`group absolute top-4 h-6 cursor-grab select-none rounded-md ${STATE_BAR[p.state] ?? STATE_BAR.empty} ${p.inferred ? "border border-dashed border-stone-400/80 dark:border-stone-400/60" : ""} shadow-[0_0_10px_rgb(0_0_0/.08)] transition-shadow hover:shadow-[0_0_14px_rgb(124_108_255/.45)] active:cursor-grabbing`}
                    style={{ left: x(s), width: w }} data-testid="phase-bar"
                  >
                    <div className="absolute inset-y-0 left-0 rounded-md bg-white/35 dark:bg-white/20" style={{ width: `${p.progress}%` }} />
                    <span className="absolute inset-y-0 left-2 right-2 flex items-center truncate text-[11px] font-medium text-white drop-shadow">{p.progress > 0 ? `${p.progress}%` : ""}</span>
                    <div onPointerDown={(e) => begin(e, { kind: "start", phase: p.id, originX: e.clientX, start: s, end: en })} className="absolute inset-y-0 left-0 w-2 cursor-ew-resize rounded-l-md hover:bg-white/40" aria-hidden="true" />
                    <div onPointerDown={(e) => begin(e, { kind: "end", phase: p.id, originX: e.clientX, start: s, end: en })} className="absolute inset-y-0 right-0 w-2 cursor-ew-resize rounded-r-md hover:bg-white/40" aria-hidden="true" />
                  </div>
                  {/* #516: ghost diamonds — where a moved milestone was first planned, tied to where it is now */}
                  {p.milestones.filter((m) => m.due_date && m.baseline && m.slipped && !m.done && dayOf(m.baseline) >= range.from).map((m) => {
                    const gx = x(dayOf(m.baseline as string)), cx = x(dayOf(m.due_date as string));
                    return (
                      <span key={`ghost-${m.id}`} className="pointer-events-none absolute inset-0" aria-hidden="true" data-testid="ghost-diamond">
                        <span className="absolute top-[47px] h-px border-t border-dotted border-stone-400/70 dark:border-stone-500/70" style={{ left: Math.min(gx, cx), width: Math.abs(cx - gx) }} />
                        <span className="absolute top-[42px] h-3 w-3 -translate-x-1/2 rotate-45 rounded-[2px] border border-dashed border-stone-400/80 dark:border-stone-500" style={{ left: gx }} />
                      </span>
                    );
                  })}
                  {p.milestones.filter((m) => m.due_date).map((m) => (
                    <button
                      key={m.id} type="button" title={`${m.title} · due ${m.due_date}${m.done ? " · done" : m.overdue ? " · overdue" : ""}`} aria-label={`${m.title}, due ${m.due_date}`}
                      onPointerDown={(e) => begin(e, { kind: "milestone", id: m.id, phase: p.id, originX: e.clientX, day: dayOf(m.due_date as string) })} onKeyDown={(e) => onKey(e, p, m)}
                      onMouseEnter={() => { setChainOf(m.id); setHover(`${m.title} · due ${m.due_date}${m.conflict ? " · due before a milestone it waits for" : m.blocked ? " · waiting on another milestone" : ""}${m.slack != null && !m.done ? (m.slack <= 0 ? " · no slack" : ` · ${m.slack} d slack`) : ""}${critical.has(m.id) ? " · on the critical chain" : ""}${m.slipped && m.moves ? (m.slipped > 0 ? ` · slipped ${m.slipped} d from ${m.baseline}` : ` · pulled in ${-m.slipped} d from ${m.baseline}`) : ""}`); }} onMouseLeave={() => { setChainOf(null); setHover(""); }}
                      className={`absolute top-[42px] h-3 w-3 -translate-x-1/2 rotate-45 cursor-grab rounded-[2px] border transition-all hover:scale-125 ${chain && !chain.has(m.id) ? "opacity-25" : ""} ${critical.has(m.id) && !m.done ? "ring-2 ring-indigo-400/60 ring-offset-1 ring-offset-white dark:ring-offset-stone-900" : ""} ${m.done ? "border-emerald-500 bg-emerald-500" : m.conflict ? "border-amber-500 bg-amber-500 shadow-[0_0_8px_rgb(245_158_11/.6)]" : m.blocked ? "border-dashed border-indigo-400 bg-transparent dark:border-indigo-300" : m.overdue ? "border-red-500 bg-red-500 shadow-[0_0_8px_rgb(239_68_68/.8)]" : "border-indigo-400 bg-white dark:bg-stone-900"}`}
                      style={{ left: x(dayOf(m.due_date as string)) }} data-testid="milestone-diamond"
                    />
                  ))}
                </div>
              );
            })}
          </div>
        </div>
      </div>
      <div className="flex h-7 items-center border-t border-stone-100 px-4 text-[11px] text-stone-400 dark:border-stone-800">{hover || (savePhase.isPending || saveMilestone.isPending ? "saving…" : `${view.phases.filter((p) => p.state === "behind" || p.state === "overdue").length} phase(s) need attention`)}{!hover && (view.critical_chain?.ids?.length ?? 0) > 1 && <span className="ml-3 truncate" data-testid="roadmap-chain">· heavy arrows: the critical chain, {view.critical_chain!.titles[0]} → {view.critical_chain!.titles[view.critical_chain!.titles.length - 1]}, {view.critical_chain!.slack == null ? "no dated dependants" : view.critical_chain!.slack < 0 ? `${-view.critical_chain!.slack} d over` : view.critical_chain!.slack === 0 ? "no slack" : `${view.critical_chain!.slack} d of slack`}</span>}</div>
    </div>
  );
}
