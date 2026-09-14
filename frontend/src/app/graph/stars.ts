/** #511 — the graph as a constellation. One renderer for every 2D force-graph in Atlas (the
 *  graph page, the note's local graph): a soft glow halo, a bright core with a highlight,
 *  labels that appear as you zoom, and a seeded starfield behind the dark theme. The 3D page
 *  gets the same idea as additive glow sprites when the vendored bundle exposes THREE. */

export type StarOptions = { dim?: boolean; ring?: string | null; label?: string; showLabel?: boolean; dark: boolean; scale: number };

/** `#rrggbb` + alpha (0–1) → `#rrggbbaa`; an 8-digit input is cut back to 6 first. */
export function hexAlpha(color: string, alpha: number): string {
  const base = color.length === 9 ? color.slice(0, 7) : color;
  return base + Math.round(Math.max(0, Math.min(1, alpha)) * 255).toString(16).padStart(2, "0");
}

export function drawStar(ctx: CanvasRenderingContext2D, x: number, y: number, r: number, color: string, o: StarOptions) {
  if (!Number.isFinite(x) || !Number.isFinite(y) || !Number.isFinite(r) || r <= 0) return; // the first frames have no layout yet
  const base = color.length === 9 ? color.slice(0, 7) : color;
  const alpha = o.dim ? 0.22 : 1;
  const halo = r * (o.dark ? 2.4 : 2.0);
  const g = ctx.createRadialGradient(x, y, r * 0.6, x, y, halo);
  g.addColorStop(0, hexAlpha(base, (o.dark ? 0.38 : 0.24) * alpha));
  g.addColorStop(1, hexAlpha(base, 0));
  ctx.fillStyle = g; ctx.beginPath(); ctx.arc(x, y, halo, 0, 2 * Math.PI); ctx.fill();
  ctx.fillStyle = hexAlpha(base, alpha); ctx.beginPath(); ctx.arc(x, y, r, 0, 2 * Math.PI); ctx.fill();
  ctx.fillStyle = hexAlpha("#ffffff", 0.55 * alpha); ctx.beginPath(); ctx.arc(x - r * 0.32, y - r * 0.32, r * 0.3, 0, 2 * Math.PI); ctx.fill();
  if (o.ring) { ctx.lineWidth = Math.max(0.8, 1.6 / o.scale); ctx.strokeStyle = o.ring; ctx.beginPath(); ctx.arc(x, y, r + 2 / o.scale, 0, 2 * Math.PI); ctx.stroke(); }
  if (o.label && o.showLabel) {
    ctx.font = `${Math.max(3, 10 / o.scale)}px system-ui, sans-serif`; ctx.textAlign = "center"; ctx.textBaseline = "top";
    ctx.fillStyle = hexAlpha(o.dark ? "#cbd5e1" : "#44403c", o.dim ? 0.35 : 0.9);
    ctx.fillText(o.label.length > 26 ? `${o.label.slice(0, 25)}…` : o.label, x, y + r + 3 / o.scale);
  }
}

/** Hit area for a custom-painted node (force-graph paints this in a colour of its own). */
export function paintStarArea(ctx: CanvasRenderingContext2D, x: number, y: number, r: number, color: string) {
  if (!Number.isFinite(x) || !Number.isFinite(y)) return;
  ctx.fillStyle = color; ctx.beginPath(); ctx.arc(x, y, r + 2, 0, 2 * Math.PI); ctx.fill();
}

// a fixed field of faint stars in graph space — the same sky every visit
const STARS: { x: number; y: number; s: number; a: number }[] = [];
let seed = 7;
const rand = () => { seed = (seed * 16807) % 2147483647; return seed / 2147483647; };
for (let i = 0; i < 220; i++) STARS.push({ x: (rand() - 0.5) * 2600, y: (rand() - 0.5) * 1800, s: 0.6 + rand() * 1.1, a: 0.12 + rand() * 0.3 });

export function drawStarfield(ctx: CanvasRenderingContext2D, scale: number, dark: boolean) {
  if (!dark) return;
  for (const s of STARS) { ctx.fillStyle = hexAlpha("#c7d2fe", s.a); ctx.beginPath(); ctx.arc(s.x, s.y, s.s / Math.sqrt(scale), 0, 2 * Math.PI); ctx.fill(); }
}

/** A canvas glow texture per colour for the 3D page's sprites (cached). */
const textures = new Map<string, unknown>();
export function glowSprite(THREE: any, color: string, size: number, dim: boolean) {
  const base = color.length === 9 ? color.slice(0, 7) : color;
  const key = `${base}-${dim}`;
  let tex = textures.get(key) as any;
  if (!tex) {
    const c = document.createElement("canvas"); c.width = c.height = 64; const ctx = c.getContext("2d")!;
    const g = ctx.createRadialGradient(32, 32, 2, 32, 32, 32);
    g.addColorStop(0, hexAlpha("#ffffff", dim ? 0.25 : 0.95)); g.addColorStop(0.25, hexAlpha(base, dim ? 0.2 : 0.9)); g.addColorStop(1, hexAlpha(base, 0));
    ctx.fillStyle = g; ctx.fillRect(0, 0, 64, 64);
    tex = new THREE.CanvasTexture(c); textures.set(key, tex);
  }
  const sprite = new THREE.Sprite(new THREE.SpriteMaterial({ map: tex, transparent: true, depthWrite: false, blending: THREE.AdditiveBlending }));
  sprite.scale.set(size, size, 1);
  return sprite;
}
