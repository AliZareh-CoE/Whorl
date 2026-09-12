/** The plan as an orbit (#392, Observatory second pass): one SVG strip under the Plan header —
 *  each phase is an arc of the orbit sized by its milestones, coloured by status (the phase in
 *  progress glows in the project accent), and every milestone is a moon on that arc: filled
 *  when done, ringed red when overdue. Hover a moon for its title; click an arc to jump to the
 *  phase card. Pure presentation over the plan the page already holds — no extra request. */
import { useMemo } from "react";

type Milestone = { id: number; title: string; due_date: string | null; completed_at: string | null; overdue: boolean };
type Phase = { id: number; name: string; status: string; progress: number; milestones: Milestone[] };

const H = 92;
const TRACK_Y = 58;
const STATUS_STROKE: Record<string, string> = { done: "accent", in_progress: "accent", blocked: "#f59e0b", not_started: "#78716c" };

function short(name: string, max: number): string {
  return name.length > max ? name.slice(0, max - 1).trimEnd() + "…" : name;
}

export default function Orbit({ phases, accent, width = 1000, onOpen }: { phases: Phase[]; accent: string; width?: number; onOpen: (id: number) => void }) {
  const layout = useMemo(() => {
    const gap = 14;
    const pad = 12;
    const weights = phases.map((p) => Math.max(1, p.milestones.length));
    const total = weights.reduce((a, b) => a + b, 0) || 1;
    const usable = width - pad * 2 - gap * Math.max(0, phases.length - 1);
    let x = pad;
    return phases.map((p, i) => {
      const w = Math.max(48, (usable * weights[i]) / total);
      const seg = { phase: p, x0: x, x1: x + w, moons: p.milestones.map((m, j) => ({ m, cx: x + (w * (j + 1)) / (p.milestones.length + 1) })) };
      x += w + gap;
      return seg;
    });
  }, [phases, width]);

  if (phases.length === 0) return null;
  return (
    <div className="mb-5 overflow-hidden rounded-2xl border border-stone-200 bg-white/60 dark:border-stone-800 dark:bg-stone-950/40" data-testid="plan-orbit" role="img" aria-label={`${phases.length} phases on the orbit`}>
      <svg viewBox={`0 0 ${width} ${H}`} width="100%" height={H} preserveAspectRatio="none" className="block" style={{ overflow: "visible" }}>
        <defs>
          <filter id="orbit-glow" x="-20%" y="-200%" width="140%" height="500%"><feGaussianBlur stdDeviation="3" /></filter>
        </defs>
        {layout.map(({ phase, x0, x1, moons }) => {
          const strokeKey = STATUS_STROKE[phase.status] ?? "#78716c";
          const stroke = strokeKey === "accent" ? accent : strokeKey;
          const active = phase.status === "in_progress";
          const dim = phase.status === "not_started";
          return (
            <g key={phase.id} className="cursor-pointer" onClick={() => onOpen(phase.id)} data-testid="orbit-phase">
              <title>{`${phase.name} · ${phase.status.replace("_", " ")} · ${phase.progress}%`}</title>
              {/* an SVG group only takes clicks where something is painted — this rect makes the whole arc clickable */}
              <rect x={x0 - 6} y={TRACK_Y - 34} width={x1 - x0 + 12} height={66} fill="transparent" />
              {active && <line x1={x0} x2={x1} y1={TRACK_Y} y2={TRACK_Y} stroke={accent} strokeWidth={6} strokeLinecap="round" opacity={0.55} filter="url(#orbit-glow)" />}
              <line x1={x0} x2={x1} y1={TRACK_Y} y2={TRACK_Y} stroke={stroke} strokeWidth={dim ? 1.5 : 2.5} strokeLinecap="round" opacity={dim ? 0.5 : phase.status === "done" ? 0.9 : 1} strokeDasharray={dim ? "3 5" : undefined} />
              {phase.status === "in_progress" && phase.progress > 0 && (
                <line x1={x0} x2={x0 + ((x1 - x0) * Math.min(100, phase.progress)) / 100} y1={TRACK_Y} y2={TRACK_Y} stroke={accent} strokeWidth={4} strokeLinecap="round" />
              )}
              <text x={x0} y={TRACK_Y - 22} fontSize={11} fontWeight={active ? 600 : 500} fill="currentColor" className={dim ? "text-stone-400" : "text-stone-700 dark:text-stone-200"} style={{ letterSpacing: 0.2 }}>
                {short(phase.name, Math.max(6, Math.floor((x1 - x0) / 6.2)))}
              </text>
              <text x={x0} y={TRACK_Y + 26} fontSize={10} fill="currentColor" className="text-stone-400 dark:text-stone-500">
                {phase.milestones.filter((m) => m.completed_at).length}/{phase.milestones.length}
              </text>
              {moons.map(({ m, cx }) => {
                const done = Boolean(m.completed_at);
                return (
                  <g key={m.id} data-testid="orbit-moon">
                    <title>{`${m.title}${m.due_date ? ` · due ${m.due_date}` : ""}${done ? " · done" : m.overdue ? " · overdue" : ""}`}</title>
                    {done && <circle cx={cx} cy={TRACK_Y} r={9} fill={accent} opacity={0.18} />}
                    <circle cx={cx} cy={TRACK_Y} r={done ? 5 : 4.5} fill={done ? accent : undefined} className={done ? undefined : "fill-white dark:fill-stone-950"} stroke={m.overdue && !done ? "#ef4444" : done ? accent : stroke} strokeWidth={m.overdue && !done ? 2.5 : 1.8} />
                  </g>
                );
              })}
            </g>
          );
        })}
      </svg>
    </div>
  );
}
