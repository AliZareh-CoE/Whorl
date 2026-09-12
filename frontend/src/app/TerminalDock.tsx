/* The terminal dock (Owner ask 2026-09-06: "can we have cmd or terminal inside it just like
 * VS Code?"). A bottom panel available on every page of the app: ⌃` toggles it, tabs hold
 * independent shells, "Claude" opens a tab that runs Claude Code with Atlas already
 * registered as an MCP server. Sessions live in the desktop shell's PTYs; in a browser the
 * dock explains where the terminal lives. */
import { lazy, Suspense, useCallback, useEffect, useRef, useState } from "react";
import { ChevronDown, Maximize2, Minimize2, Plus, Sparkles, TerminalSquare, Trash2, X } from "lucide-react";

const TerminalPanel = lazy(() => import("./pages/TerminalPanel"));
type Handle = { write: (text: string) => void; focus: () => void };
type Session = { key: number; title: string; cwd?: string; initialCommand?: string; exited?: boolean };

const HEIGHT_KEY = "atlas-terminal-height";
const isDesktop = () => typeof window !== "undefined" && "__TAURI__" in window;

/** Open the dock from anywhere: `window.dispatchEvent(new CustomEvent("atlas-terminal", { detail: { cwd, command } }))`. */
export function openTerminal(detail: { cwd?: string; command?: string; toggle?: boolean } = {}) {
  window.dispatchEvent(new CustomEvent("atlas-terminal", { detail }));
}

export default function TerminalDock() {
  const [open, setOpen] = useState(false);
  const [maximized, setMaximized] = useState(false);
  const [height, setHeight] = useState<number>(() => { try { return Number(localStorage.getItem(HEIGHT_KEY)) || 280; } catch { return 280; } });
  const [sessions, setSessions] = useState<Session[]>([]);
  const [active, setActive] = useState<number>(0);
  const handles = useRef(new Map<number, Handle>());
  const nextKey = useRef(1);
  const dragging = useRef<{ startY: number; startH: number } | null>(null);

  const addSession = useCallback((opts: { cwd?: string; initialCommand?: string; title?: string } = {}) => {
    const key = nextKey.current++;
    setSessions((s) => [...s, { key, title: opts.title ?? (opts.initialCommand ? opts.initialCommand.split(" ")[0] : `shell ${key}`), cwd: opts.cwd, initialCommand: opts.initialCommand }]);
    setActive(key);
    setOpen(true);
    return key;
  }, []);

  useEffect(() => {
    const onEvent = (e: Event) => {
      const d = (e as CustomEvent<{ cwd?: string; command?: string; toggle?: boolean }>).detail || {};
      if (d.toggle) { setOpen((v) => { if (!v && sessions.length === 0) addSession({ cwd: d.cwd }); return !v; }); return; }
      if (d.command) addSession({ cwd: d.cwd, initialCommand: d.command });
      else if (sessions.length === 0) addSession({ cwd: d.cwd });
      else setOpen(true);
    };
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "`") { e.preventDefault(); onEvent(new CustomEvent("atlas-terminal", { detail: { toggle: true } })); }
    };
    window.addEventListener("atlas-terminal", onEvent);
    window.addEventListener("keydown", onKey);
    return () => { window.removeEventListener("atlas-terminal", onEvent); window.removeEventListener("keydown", onKey); };
  }, [addSession, sessions.length]);

  useEffect(() => { try { localStorage.setItem(HEIGHT_KEY, String(height)); } catch { /* private mode */ } }, [height]);

  const closeSession = (key: number) => {
    setSessions((s) => { const next = s.filter((x) => x.key !== key); if (active === key) setActive(next[next.length - 1]?.key ?? 0); if (next.length === 0) setOpen(false); return next; });
    handles.current.delete(key);
  };

  const onDragStart = (e: React.MouseEvent) => {
    dragging.current = { startY: e.clientY, startH: height };
    const move = (ev: MouseEvent) => { if (!dragging.current) return; setHeight(Math.min(window.innerHeight - 120, Math.max(120, dragging.current.startH + (dragging.current.startY - ev.clientY)))); };
    const up = () => { dragging.current = null; window.removeEventListener("mousemove", move); window.removeEventListener("mouseup", up); };
    window.addEventListener("mousemove", move); window.addEventListener("mouseup", up);
  };

  if (!open) return null;
  const h = maximized ? window.innerHeight - 48 : height;
  const activeSession = sessions.find((s) => s.key === active);

  return (
    <div className="fixed bottom-0 left-60 right-0 z-30 flex flex-col border-t border-stone-200 bg-white shadow-[0_-8px_30px_rgba(0,0,0,0.12)] dark:border-stone-800 dark:bg-[#0e1119]" style={{ height: h }} data-testid="terminal-dock" role="region" aria-label="Terminal">
      <div onMouseDown={onDragStart} className="h-1 shrink-0 cursor-row-resize bg-transparent hover:bg-indigo-500/40" title="Drag to resize" />
      <div className="flex h-8 shrink-0 items-center gap-0.5 border-b border-stone-200 px-2 text-xs dark:border-stone-800">
        <TerminalSquare className="mr-1 h-3.5 w-3.5 text-stone-400" aria-hidden="true" />
        <div className="flex min-w-0 items-stretch overflow-x-auto" role="tablist">
          {sessions.map((s) => (
            <div key={s.key} role="tab" aria-selected={s.key === active} onClick={() => { setActive(s.key); handles.current.get(s.key)?.focus(); }} className={`group flex cursor-pointer items-center gap-1.5 rounded-t-md px-2.5 py-1 ${s.key === active ? "bg-stone-100 text-stone-900 dark:bg-white/10 dark:text-stone-100" : "text-stone-500 hover:text-stone-800 dark:hover:text-stone-200"}`}>
              <span className={`truncate ${s.exited ? "line-through opacity-60" : ""}`}>{s.title}</span>
              <button type="button" onClick={(e) => { e.stopPropagation(); closeSession(s.key); }} className="opacity-0 hover:text-red-500 group-hover:opacity-100" aria-label={`Close ${s.title}`}><X className="h-3 w-3" aria-hidden="true" /></button>
            </div>
          ))}
        </div>
        <button type="button" onClick={() => addSession({ cwd: activeSession?.cwd })} className="ml-1 rounded p-1 text-stone-400 hover:bg-stone-100 hover:text-stone-800 dark:hover:bg-white/10 dark:hover:text-stone-100" title="New terminal" aria-label="New terminal"><Plus className="h-3.5 w-3.5" aria-hidden="true" /></button>
        <button type="button" onClick={() => addSession({ cwd: activeSession?.cwd, initialCommand: "claude", title: "claude" })} className="ml-1 inline-flex items-center gap-1 rounded-md bg-indigo-600/90 px-2 py-0.5 text-[11px] font-medium text-white hover:bg-indigo-600" title="Open Claude Code in a new tab (Atlas is already registered as its MCP server)"><Sparkles className="h-3 w-3" aria-hidden="true" />Claude</button>
        <span className="ml-auto hidden text-[10px] text-stone-400 md:inline">⌃` toggles</span>
        {activeSession && <button type="button" onClick={() => handles.current.get(active)?.write("clear\r")} className="rounded p-1 text-stone-400 hover:text-stone-800 dark:hover:text-stone-100" title="Clear" aria-label="Clear"><Trash2 className="h-3.5 w-3.5" aria-hidden="true" /></button>}
        <button type="button" onClick={() => setMaximized((v) => !v)} className="rounded p-1 text-stone-400 hover:text-stone-800 dark:hover:text-stone-100" title={maximized ? "Restore" : "Maximize"} aria-label="Maximize">{maximized ? <Minimize2 className="h-3.5 w-3.5" aria-hidden="true" /> : <Maximize2 className="h-3.5 w-3.5" aria-hidden="true" />}</button>
        <button type="button" onClick={() => setOpen(false)} className="rounded p-1 text-stone-400 hover:text-stone-800 dark:hover:text-stone-100" title="Hide (⌃`)" aria-label="Hide terminal"><ChevronDown className="h-3.5 w-3.5" aria-hidden="true" /></button>
      </div>
      <div className="min-h-0 flex-1 p-1">
        {!isDesktop() && (
          <div className="flex h-full flex-col items-center justify-center gap-1 text-center text-sm text-stone-500">
            <p>The terminal runs inside the <strong>Atlas desktop app</strong>, next to your files — a real shell, like VS Code's.</p>
            <p className="text-xs">In the app: ⌃` opens it anywhere, and the <em>Claude</em> button starts Claude Code with Atlas already connected.</p>
          </div>
        )}
        {isDesktop() && sessions.map((s) => (
          <Suspense key={s.key} fallback={s.key === active ? <p className="p-3 text-xs text-stone-400">Starting a shell…</p> : null}>
            <TerminalPanel cwd={s.cwd} visible={s.key === active} initialCommand={s.initialCommand} onExit={() => setSessions((all) => all.map((x) => (x.key === s.key ? { ...x, exited: true } : x)))} onTitle={(t) => { if (t && !s.initialCommand) setSessions((all) => all.map((x) => (x.key === s.key ? { ...x, title: t.slice(0, 28) } : x))); }} register={(hd) => { if (hd) handles.current.set(s.key, hd); else handles.current.delete(s.key); }} />
          </Suspense>
        ))}
      </div>
    </div>
  );
}
