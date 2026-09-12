/** Context menus and "⋯" action menus (owner report 2026-09-06: "left click doesn't have much
 * functionality"). One component drives both: right-click anywhere that calls `menu.open(e,
 * items)`, or a `<Kebab items />` button on a row. Keyboard: ↑↓ move, Enter selects, Esc closes.
 * Items are plain objects so pages declare actions as data. */
import { useCallback, useEffect, useRef, useState } from "react";
import { MoreHorizontal } from "lucide-react";

export type MenuItem =
  | "-"
  | { label: string; icon?: React.ReactNode; hint?: string; danger?: boolean; disabled?: boolean; onSelect: () => void };

type Open = { x: number; y: number; items: MenuItem[] } | null;

export function useMenu() {
  const [state, setState] = useState<Open>(null);
  const open = useCallback((e: { clientX: number; clientY: number; preventDefault: () => void; stopPropagation?: () => void }, items: MenuItem[]) => {
    e.preventDefault(); e.stopPropagation?.();
    setState({ x: e.clientX, y: e.clientY, items });
  }, []);
  const close = useCallback(() => setState(null), []);
  const element = state ? <MenuPopup x={state.x} y={state.y} items={state.items} onClose={close} /> : null;
  return { open, close, element, isOpen: !!state };
}

export function MenuPopup({ x, y, items, onClose }: { x: number; y: number; items: MenuItem[]; onClose: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const [pos, setPos] = useState({ left: x, top: y });
  const [active, setActive] = useState(-1);
  const enabled = items.map((it, i) => (it !== "-" && !it.disabled ? i : -1)).filter((i) => i >= 0);
  useEffect(() => {
    const el = ref.current; if (!el) return;
    const r = el.getBoundingClientRect();
    setPos({ left: Math.max(4, Math.min(x, window.innerWidth - r.width - 4)), top: Math.max(4, Math.min(y, window.innerHeight - r.height - 4)) });
  }, [x, y]);
  useEffect(() => {
    const down = (e: MouseEvent) => { if (!ref.current?.contains(e.target as Node)) onClose(); };
    const key = (e: KeyboardEvent) => {
      if (e.key === "Escape") { e.preventDefault(); onClose(); }
      else if (e.key === "ArrowDown" || e.key === "ArrowUp") {
        e.preventDefault();
        setActive((a) => { const idx = enabled.indexOf(a); const n = e.key === "ArrowDown" ? (idx + 1) % enabled.length : (idx - 1 + enabled.length) % enabled.length; return enabled[n] ?? -1; });
      } else if (e.key === "Enter" && active >= 0) { e.preventDefault(); const it = items[active]; if (it !== "-") { onClose(); it.onSelect(); } }
    };
    // close on a user-initiated scroll (wheel/touch), not on `scroll` events: the page's smooth
    // scrollIntoView still fires those for a moment after the click that opened the menu
    window.addEventListener("mousedown", down); window.addEventListener("keydown", key);
    window.addEventListener("resize", onClose); window.addEventListener("wheel", onClose, { passive: true }); window.addEventListener("touchmove", onClose, { passive: true });
    return () => { window.removeEventListener("mousedown", down); window.removeEventListener("keydown", key); window.removeEventListener("resize", onClose); window.removeEventListener("wheel", onClose); window.removeEventListener("touchmove", onClose); };
  }, [onClose, active, items, enabled]);
  return (
    <div ref={ref} role="menu" data-testid="context-menu" style={{ left: pos.left, top: pos.top }}
      className="fixed z-[60] min-w-[11rem] rounded-xl border border-stone-200 bg-white/95 p-1 text-sm shadow-xl backdrop-blur dark:border-stone-700 dark:bg-stone-900/95" onContextMenu={(e) => e.preventDefault()}>
      {items.map((it, i) => it === "-"
        ? <div key={i} className="my-1 h-px bg-stone-100 dark:bg-stone-800" role="separator" />
        : (
          <button key={i} type="button" role="menuitem" disabled={it.disabled} onMouseEnter={() => setActive(i)}
            onClick={() => { onClose(); it.onSelect(); }}
            className={`flex w-full items-center gap-2 rounded-lg px-2.5 py-1.5 text-left transition-colors disabled:opacity-40 ${active === i ? (it.danger ? "bg-red-500/10" : "bg-stone-100 dark:bg-stone-800") : ""} ${it.danger ? "text-red-600 dark:text-red-300" : "text-stone-700 dark:text-stone-200"}`}>
            {it.icon && <span className="flex h-4 w-4 shrink-0 items-center justify-center opacity-70" aria-hidden="true">{it.icon}</span>}
            <span className="min-w-0 flex-1 truncate">{it.label}</span>
            {it.hint && <span className="ml-3 shrink-0 font-mono text-[10px] text-stone-400">{it.hint}</span>}
          </button>
        ))}
    </div>
  );
}

/** The "⋯" button every row can carry: opens the same popup anchored under the button. */
export function Kebab({ items, label = "More actions", className = "" }: { items: MenuItem[]; label?: string; className?: string }) {
  const [at, setAt] = useState<{ x: number; y: number } | null>(null);
  return (
    <>
      <button type="button" aria-label={label} title={label} aria-haspopup="menu" aria-expanded={!!at} data-testid="kebab"
        onClick={(e) => { e.preventDefault(); e.stopPropagation(); const r = e.currentTarget.getBoundingClientRect(); setAt({ x: r.left, y: r.bottom + 4 }); }}
        onContextMenu={(e) => { e.preventDefault(); e.stopPropagation(); setAt({ x: e.clientX, y: e.clientY }); }}
        className={`inline-flex h-6 w-6 items-center justify-center rounded-md text-stone-400 transition-colors hover:bg-stone-100 hover:text-stone-700 dark:hover:bg-stone-800 dark:hover:text-stone-100 ${className}`}>
        <MoreHorizontal className="h-4 w-4" aria-hidden="true" />
      </button>
      {at && <MenuPopup x={at.x} y={at.y} items={items} onClose={() => setAt(null)} />}
    </>
  );
}
