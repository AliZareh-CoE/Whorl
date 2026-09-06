// Atlas constellation — a living particle field of your research (Observatory identity).
//
// Plain ES module with zero dependencies so it works offline in the desktop app and can be
// used by both the React dashboard (dynamic import) and the Django login template.
//
//   import { mountConstellation } from "/static/js/constellation.js";
//   const stop = mountConstellation(canvas, { anchors: [{ label, color, weight }], density: 1 });
//
// Anchors are your projects: bigger, brighter, labelled nodes that the drifting particles
// orbit and link to. Everything respects prefers-reduced-motion (renders one static frame).

export function mountConstellation(canvas, opts = {}) {
  const ctx = canvas.getContext("2d");
  if (!ctx) return () => {};
  const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
  const density = opts.density ?? 1;
  const anchors = (opts.anchors ?? []).slice(0, 8);
  const linkDist = opts.linkDist ?? 120;
  let w = 0, h = 0, dpr = 1, raf = 0, running = true;
  const mouse = { x: -1e4, y: -1e4, tx: -1e4, ty: -1e4 };
  let particles = [];
  let nodes = [];

  function resize() {
    const rect = canvas.getBoundingClientRect();
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    w = Math.max(1, Math.floor(rect.width));
    h = Math.max(1, Math.floor(rect.height));
    canvas.width = Math.floor(w * dpr);
    canvas.height = Math.floor(h * dpr);
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    seed();
  }

  function seed() {
    const count = Math.round((w * h) / 9000 * density);
    particles = Array.from({ length: Math.max(24, Math.min(count, 220)) }, () => ({
      x: Math.random() * w,
      y: Math.random() * h,
      vx: (Math.random() - 0.5) * 0.25,
      vy: (Math.random() - 0.5) * 0.25,
      r: 0.8 + Math.random() * 1.6,
      hue: Math.random() < 0.15 ? "cyan" : Math.random() < 0.08 ? "magenta" : "violet",
      tw: Math.random() * Math.PI * 2,
    }));
    // anchors sit on a gentle arc across the field, each with its own slow orbit
    nodes = anchors.map((a, i) => {
      const t = anchors.length === 1 ? 0.5 : i / (anchors.length - 1);
      return {
        label: a.label,
        color: a.color || "#8b7cff",
        weight: Math.max(0.2, Math.min(1, a.weight ?? 0.6)),
        cx: w * (0.18 + t * 0.64),
        cy: h * (0.42 + Math.sin(t * Math.PI) * -0.18 + (i % 2 ? 0.14 : 0)),
        phase: Math.random() * Math.PI * 2,
        x: 0, y: 0,
      };
    });
  }

  const palette = {
    violet: [139, 124, 255],
    cyan: [79, 242, 224],
    magenta: [255, 94, 196],
  };

  function frame(t) {
    ctx.clearRect(0, 0, w, h);
    mouse.x += (mouse.tx - mouse.x) * 0.08;
    mouse.y += (mouse.ty - mouse.y) * 0.08;
    const time = t / 1000;

    // anchors orbit slowly around their home point
    for (const n of nodes) {
      const rad = 10 + n.weight * 8;
      n.x = n.cx + Math.cos(time * 0.25 + n.phase) * rad;
      n.y = n.cy + Math.sin(time * 0.2 + n.phase) * rad * 0.6;
    }

    // particles drift; mouse repels gently; anchors attract faintly
    for (const p of particles) {
      const dx = p.x - mouse.x, dy = p.y - mouse.y;
      const d2 = dx * dx + dy * dy;
      if (d2 < 140 * 140) {
        const f = (1 - Math.sqrt(d2) / 140) * 0.35;
        p.vx += (dx / Math.sqrt(d2 + 1)) * f;
        p.vy += (dy / Math.sqrt(d2 + 1)) * f;
      }
      for (const n of nodes) {
        const ax = n.x - p.x, ay = n.y - p.y;
        const ad = Math.sqrt(ax * ax + ay * ay) + 1;
        if (ad < 220) { p.vx += (ax / ad) * 0.004 * n.weight; p.vy += (ay / ad) * 0.004 * n.weight; }
      }
      p.vx *= 0.985; p.vy *= 0.985;
      p.x += p.vx; p.y += p.vy;
      if (p.x < -10) p.x = w + 10; else if (p.x > w + 10) p.x = -10;
      if (p.y < -10) p.y = h + 10; else if (p.y > h + 10) p.y = -10;
    }

    // links between near particles + to anchors
    ctx.lineWidth = 1;
    for (let i = 0; i < particles.length; i++) {
      const a = particles[i];
      for (let j = i + 1; j < particles.length; j++) {
        const b = particles[j];
        const dx = a.x - b.x, dy = a.y - b.y;
        const d = dx * dx + dy * dy;
        if (d < linkDist * linkDist) {
          const alpha = (1 - Math.sqrt(d) / linkDist) * 0.28;
          ctx.strokeStyle = `rgba(160,150,255,${alpha.toFixed(3)})`;
          ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(b.x, b.y); ctx.stroke();
        }
      }
      for (const n of nodes) {
        const dx = a.x - n.x, dy = a.y - n.y;
        const d = Math.sqrt(dx * dx + dy * dy);
        if (d < 170) {
          const alpha = (1 - d / 170) * 0.5;
          ctx.strokeStyle = hexToRgba(n.color, alpha);
          ctx.beginPath(); ctx.moveTo(a.x, a.y); ctx.lineTo(n.x, n.y); ctx.stroke();
        }
      }
    }

    // particles
    for (const p of particles) {
      const [r, g, b] = palette[p.hue];
      const tw = 0.55 + 0.45 * Math.sin(time * 1.4 + p.tw);
      ctx.fillStyle = `rgba(${r},${g},${b},${(0.55 * tw + 0.25).toFixed(3)})`;
      ctx.beginPath(); ctx.arc(p.x, p.y, p.r, 0, Math.PI * 2); ctx.fill();
    }

    // anchors: glow + core + label
    for (const n of nodes) {
      const R = 6 + n.weight * 10;
      const glow = ctx.createRadialGradient(n.x, n.y, 0, n.x, n.y, R * 4);
      glow.addColorStop(0, hexToRgba(n.color, 0.55));
      glow.addColorStop(1, hexToRgba(n.color, 0));
      ctx.fillStyle = glow;
      ctx.beginPath(); ctx.arc(n.x, n.y, R * 4, 0, Math.PI * 2); ctx.fill();
      ctx.fillStyle = n.color;
      ctx.beginPath(); ctx.arc(n.x, n.y, R * 0.55, 0, Math.PI * 2); ctx.fill();
      ctx.strokeStyle = hexToRgba("#ffffff", 0.35);
      ctx.beginPath(); ctx.arc(n.x, n.y, R, 0, Math.PI * 2); ctx.stroke();
      if (n.label) {
        ctx.font = "500 11px Inter, system-ui, sans-serif";
        ctx.fillStyle = "rgba(241,242,255,0.85)";
        ctx.textAlign = "center";
        ctx.fillText(n.label, n.x, n.y + R + 16);
      }
    }
    if (running && !reduce) raf = requestAnimationFrame(frame);
  }

  function onMove(e) {
    const rect = canvas.getBoundingClientRect();
    mouse.tx = e.clientX - rect.left; mouse.ty = e.clientY - rect.top;
  }
  function onLeave() { mouse.tx = -1e4; mouse.ty = -1e4; }

  const ro = typeof ResizeObserver !== "undefined" ? new ResizeObserver(resize) : null;
  ro?.observe(canvas);
  resize();
  canvas.addEventListener("pointermove", onMove);
  canvas.addEventListener("pointerleave", onLeave);
  raf = requestAnimationFrame(frame);

  return function stop() {
    running = false;
    cancelAnimationFrame(raf);
    ro?.disconnect();
    canvas.removeEventListener("pointermove", onMove);
    canvas.removeEventListener("pointerleave", onLeave);
  };
}

function hexToRgba(hex, a) {
  const m = /^#?([0-9a-f]{6})$/i.exec(hex || "");
  if (!m) return `rgba(139,124,255,${a})`;
  const n = parseInt(m[1], 16);
  return `rgba(${(n >> 16) & 255},${(n >> 8) & 255},${n & 255},${a})`;
}
