/* Mochi, the lab familiar (Owner report 2026-09-06: "our pet is terrible … something that goes
 * viral"). One layered SVG creature whose pupils follow the cursor, that blinks, breathes,
 * glances around when idle, hops on real events, sleeps with a drifting zzz, and grows
 * accessories with its stage: egg → hatchling → scholar (round glasses) → sage (cap, scarf,
 * sparkles). Everything animates in CSS (assets/css/app.css, `.mochi`); JS only moves the
 * eyes and fires one-off reactions, so it is cheap enough to live in the sidebar forever. */
import { useCallback, useEffect, useRef, useState } from "react";

export type Reaction = "hop" | "celebrate" | "love" | "nom" | "think";

export function Creature({ stage, mood, size = 48, reaction, onClick, className = "" }: { stage: string; mood: string; size?: number; reaction?: Reaction | null; onClick?: () => void; className?: string }) {
  const ref = useRef<HTMLSpanElement>(null);
  const idle = useRef<number | null>(null);
  const lastMove = useRef(0);
  const [particles, setParticles] = useState<{ id: number; kind: Reaction; items: { x: number; y: number; d: number; r: number }[] } | null>(null);
  const asleep = mood === "sleeping";

  // pupils follow the cursor; when the mouse rests, Mochi glances around on its own
  const look = useCallback((x: number, y: number) => {
    const el = ref.current; if (!el) return;
    el.style.setProperty("--pupil-x", `${x.toFixed(2)}px`);
    el.style.setProperty("--pupil-y", `${y.toFixed(2)}px`);
  }, []);
  useEffect(() => {
    if (asleep) { look(0, 0.6); return; }
    const onMove = (e: MouseEvent) => {
      const el = ref.current; if (!el) return;
      const r = el.getBoundingClientRect();
      const cx = r.left + r.width / 2, cy = r.top + r.height * 0.42;
      const dx = e.clientX - cx, dy = e.clientY - cy;
      const dist = Math.hypot(dx, dy) || 1;
      const reach = Math.min(1, dist / 240); // far away → look all the way, close → subtle
      look((dx / dist) * 2.4 * reach, (dy / dist) * 1.8 * reach);
      lastMove.current = Date.now();
    };
    window.addEventListener("mousemove", onMove, { passive: true });
    idle.current = window.setInterval(() => {
      if (Date.now() - lastMove.current < 3500) return;
      const a = Math.random() * Math.PI * 2, m = Math.random() < 0.3 ? 0 : 1;
      look(Math.cos(a) * 1.6 * m, Math.sin(a) * 1.1 * m);
    }, 2600);
    return () => { window.removeEventListener("mousemove", onMove); if (idle.current) window.clearInterval(idle.current); };
  }, [asleep, look]);

  // one-off reactions: a class on the wrapper + a particle burst
  useEffect(() => {
    if (!reaction) return;
    const el = ref.current; if (!el) return;
    el.classList.remove("mochi-hop", "mochi-celebrate", "mochi-love", "mochi-nom", "mochi-think");
    void el.offsetWidth; // restart the animation
    el.classList.add(`mochi-${reaction}`);
    if (reaction === "celebrate" || reaction === "love") {
      const items = Array.from({ length: reaction === "love" ? 7 : 14 }, (_, i) => ({ x: Math.cos((i / 14) * Math.PI * 2) * (18 + Math.random() * 14), y: Math.sin((i / 14) * Math.PI * 2) * (14 + Math.random() * 12) - 10, d: Math.random() * 0.25, r: Math.random() * 360 }));
      setParticles({ id: Date.now(), kind: reaction, items });
      const t = window.setTimeout(() => setParticles(null), 1400);
      return () => window.clearTimeout(t);
    }
  }, [reaction]);

  const scholar = stage === "scholar" || stage === "sage";
  const sage = stage === "sage";
  const happy = mood === "happy" || mood === "thriving";

  return (
    <span ref={ref} onClick={onClick} className={`mochi mochi-${stage} mochi-${mood} ${onClick ? "cursor-pointer" : ""} ${className}`} style={{ width: size, height: size }} role={onClick ? "button" : "img"} aria-label={`Mochi the ${stage}, ${mood}`} tabIndex={onClick ? 0 : undefined} onKeyDown={onClick ? (e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onClick(); } } : undefined}>
      {particles && (
        <span className="mochi-particles" aria-hidden="true">
          {particles.items.map((p, i) => <i key={`${particles.id}-${i}`} className={particles.kind === "love" ? "mochi-heart" : "mochi-confetti"} style={{ ["--tx" as string]: `${p.x}px`, ["--ty" as string]: `${p.y}px`, ["--delay" as string]: `${p.d}s`, ["--rot" as string]: `${p.r}deg`, ["--hue" as string]: `${(i * 47) % 360}` }} />)}
        </span>
      )}
      {asleep && <span className="mochi-zzz" aria-hidden="true"><i>z</i><i>z</i><i>z</i></span>}
      <svg viewBox="0 0 64 64" width="100%" height="100%" className="mochi-svg" aria-hidden="true">
        <defs>
          <radialGradient id="mochi-body" cx="45%" cy="35%" r="70%"><stop offset="0%" stopColor="var(--mochi-hi)" /><stop offset="100%" stopColor="var(--mochi-body)" /></radialGradient>
          <radialGradient id="mochi-belly" cx="50%" cy="40%" r="60%"><stop offset="0%" stopColor="#fff9ee" /><stop offset="100%" stopColor="var(--mochi-belly)" /></radialGradient>
        </defs>
        <ellipse className="mochi-shadow" cx="32" cy="59" rx="16" ry="3" fill="#000" opacity="0.12" />
        {stage === "egg" ? (
          <g className="mochi-body">
            <path d="M32 8 C44 8 52 22 52 36 C52 49 43 57 32 57 C21 57 12 49 12 36 C12 22 20 8 32 8 Z" fill="url(#mochi-body)" stroke="var(--mochi-line)" strokeWidth="1.2" />
            <path d="M22 30 l4 -4 l3 5 l4 -6 l3 5 l4 -4" fill="none" stroke="var(--mochi-line)" strokeWidth="1.3" strokeLinejoin="round" strokeLinecap="round" opacity="0.7" />
            <ellipse cx="25" cy="18" rx="4" ry="2.4" fill="#fff" opacity="0.55" transform="rotate(-30 25 18)" />
            <g className="mochi-eyes">
              <g className="mochi-eye"><circle cx="26" cy="40" r="3.2" fill="#fff" stroke="var(--mochi-line)" strokeWidth="0.8" /><circle className="mochi-pupil" cx="26" cy="40" r="1.6" fill="#241e12" /></g>
              <g className="mochi-eye"><circle cx="38" cy="40" r="3.2" fill="#fff" stroke="var(--mochi-line)" strokeWidth="0.8" /><circle className="mochi-pupil" cx="38" cy="40" r="1.6" fill="#241e12" /></g>
              <rect className="mochi-lid" x="21" y="35" width="22" height="10" fill="var(--mochi-body)" />
            </g>
          </g>
        ) : (
          <g className="mochi-body">
            {/* ear tufts (scholar+) */}
            {scholar && <g className="mochi-tufts"><path d="M17 20 l-4 -12 l11 7 z" fill="var(--mochi-body)" stroke="var(--mochi-line)" strokeWidth="1" strokeLinejoin="round" /><path d="M47 20 l4 -12 l-11 7 z" fill="var(--mochi-body)" stroke="var(--mochi-line)" strokeWidth="1" strokeLinejoin="round" /></g>}
            {/* body */}
            <path d={stage === "hatchling" ? "M32 18 C46 18 52 30 52 41 C52 51 43 57 32 57 C21 57 12 51 12 41 C12 30 18 18 32 18 Z" : "M32 12 C48 12 54 26 54 40 C54 51 44 58 32 58 C20 58 10 51 10 40 C10 26 16 12 32 12 Z"} fill="url(#mochi-body)" stroke="var(--mochi-line)" strokeWidth="1.2" />
            {/* belly */}
            <path d="M32 30 C40 30 44 37 44 45 C44 52 38 56 32 56 C26 56 20 52 20 45 C20 37 24 30 32 30 Z" fill="url(#mochi-belly)" opacity="0.95" />
            <path d="M26 45 q6 4 12 0 M27 50 q5 3 10 0" fill="none" stroke="var(--mochi-line)" strokeWidth="0.8" opacity="0.35" strokeLinecap="round" />
            {/* wings */}
            <path className="mochi-wing mochi-wing-l" d="M13 34 C8 40 9 50 15 54 C17 46 17 40 19 34 Z" fill="var(--mochi-body)" stroke="var(--mochi-line)" strokeWidth="1" />
            <path className="mochi-wing mochi-wing-r" d="M51 34 C56 40 55 50 49 54 C47 46 47 40 45 34 Z" fill="var(--mochi-body)" stroke="var(--mochi-line)" strokeWidth="1" />
            {/* hatchling keeps a bit of shell */}
            {stage === "hatchling" && <path d="M20 22 l3 5 l3 -6 l3 6 l3 -6 l3 6 l3 -5 q-2 -6 -9 -6 q-7 0 -9 6 z" fill="#f5efe0" stroke="#d8cdb4" strokeWidth="0.8" strokeLinejoin="round" />}
            {/* face */}
            <g className="mochi-eyes">
              <g className="mochi-eye"><circle cx="24" cy="31" r={scholar ? 5.6 : 4.6} fill="#fff" stroke="var(--mochi-line)" strokeWidth="0.9" /><circle className="mochi-pupil" cx="24" cy="31.5" r={scholar ? 2.6 : 2.1} fill="#241e12" /><circle className="mochi-pupil" cx="25" cy="30.3" r="0.8" fill="#fff" /></g>
              <g className="mochi-eye"><circle cx="40" cy="31" r={scholar ? 5.6 : 4.6} fill="#fff" stroke="var(--mochi-line)" strokeWidth="0.9" /><circle className="mochi-pupil" cx="40" cy="31.5" r={scholar ? 2.6 : 2.1} fill="#241e12" /><circle className="mochi-pupil" cx="41" cy="30.3" r="0.8" fill="#fff" /></g>
              <g className="mochi-lids"><ellipse className="mochi-lid" cx="24" cy="31" rx={scholar ? 6.2 : 5.2} ry={scholar ? 6.2 : 5.2} fill="var(--mochi-body)" /><ellipse className="mochi-lid" cx="40" cy="31" rx={scholar ? 6.2 : 5.2} ry={scholar ? 6.2 : 5.2} fill="var(--mochi-body)" /></g>
            </g>
            {/* glasses (scholar+) */}
            {scholar && <g className="mochi-glasses" fill="none" stroke="var(--mochi-accent)" strokeWidth="1.3"><circle cx="24" cy="31" r="7" /><circle cx="40" cy="31" r="7" /><path d="M31 31 h2" /><path d="M17 30 l-4 -2 M47 30 l4 -2" strokeLinecap="round" /></g>}
            {/* blush */}
            <ellipse className="mochi-blush" cx="18" cy="38" rx="3" ry="1.6" fill="#f59cb1" opacity={happy ? 0.6 : 0.25} />
            <ellipse className="mochi-blush" cx="46" cy="38" rx="3" ry="1.6" fill="#f59cb1" opacity={happy ? 0.6 : 0.25} />
            {/* beak + mouth */}
            <path d="M29.5 36 l2.5 4 l2.5 -4 z" fill="#f4a338" stroke="#d98322" strokeWidth="0.6" strokeLinejoin="round" />
            <path className="mochi-mouth" d={happy ? "M26 41 q6 5 12 0" : "M28 41 q4 2.5 8 0"} fill="none" stroke="var(--mochi-line)" strokeWidth="1" strokeLinecap="round" opacity="0.6" />
            {/* feet */}
            <path d="M25 57 l-3 3 M25 57 l0 3 M25 57 l3 3 M39 57 l-3 3 M39 57 l0 3 M39 57 l3 3" stroke="#f4a338" strokeWidth="1.4" strokeLinecap="round" />
            {/* sage: cap, scarf, sparkles */}
            {sage && (
              <g className="mochi-sage">
                <path d="M22 50 q10 5 20 0 l1 4 q-11 5 -22 0 z" fill="var(--mochi-accent)" opacity="0.9" />
                <path d="M18 14 l14 -6 l14 6 l-14 6 z" fill="#2c2618" />
                <path d="M32 14 l0 6" stroke="#2c2618" strokeWidth="1.4" />
                <path d="M46 14 l0 7" stroke="#e8b945" strokeWidth="1" />
                <circle cx="46" cy="21.5" r="1.4" fill="#e8b945" />
                <g className="mochi-sparkle"><path d="M55 12 l1.2 3 l3 1.2 l-3 1.2 l-1.2 3 l-1.2 -3 l-3 -1.2 l3 -1.2 z" fill="#ffd86b" /></g>
                <g className="mochi-sparkle mochi-sparkle-2"><path d="M8 26 l0.9 2.2 l2.2 0.9 l-2.2 0.9 l-0.9 2.2 l-0.9 -2.2 l-2.2 -0.9 l2.2 -0.9 z" fill="#ffd86b" /></g>
              </g>
            )}
          </g>
        )}
      </svg>
    </span>
  );
}
