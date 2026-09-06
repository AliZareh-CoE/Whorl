import { FitAddon } from "@xterm/addon-fit";
import { Terminal } from "@xterm/xterm";
// inline so the lazy chunk carries no separate (mis-pathed) CSS sidecar to preload
import xtermCss from "@xterm/xterm/css/xterm.css?inline";
import { useEffect, useRef } from "react";

function ensureXtermCss() {
  if (document.getElementById("xterm-inline-css")) return;
  const style = document.createElement("style");
  style.id = "xterm-inline-css";
  style.textContent = xtermCss;
  document.head.appendChild(style);
}

// One terminal session (Owner #30 slice 5-ii; multi-tab dock 2026-09-06): xterm.js wired to
// a PTY in the desktop shell over Tauri IPC. Every session has its own PTY id, so the dock
// can keep several open. Desktop-only — in the browser there is no PTY (and we never expose
// one server-side); the dock renders a hint instead of mounting this.
type TauriApi = {
  core: { invoke: <T = unknown>(cmd: string, args?: Record<string, unknown>) => Promise<T> };
  event: { listen: (e: string, cb: (ev: { payload: unknown }) => void) => Promise<() => void> };
};

export function isDesktop(): boolean {
  return typeof window !== "undefined" && "__TAURI__" in window;
}

const THEMES = {
  dark: { background: "#0e1119", foreground: "#e7e5e4", cursor: "#a5b4fc", selectionBackground: "rgba(129,140,248,0.3)", black: "#1f2333", brightBlack: "#6b7280" },
  light: { background: "#ffffff", foreground: "#1c1917", cursor: "#4f46e5", selectionBackground: "rgba(79,70,229,0.18)", black: "#e7e5e4", brightBlack: "#78716c" },
};

export type TerminalHandle = { write: (text: string) => void; focus: () => void };

export default function TerminalPanel({ cwd, visible, initialCommand, onExit, onTitle, register }: { cwd?: string; visible: boolean; initialCommand?: string; onExit?: () => void; onTitle?: (t: string) => void; register?: (h: TerminalHandle | null) => void }) {
  const hostRef = useRef<HTMLDivElement>(null);
  const fitRef = useRef<{ fit: () => void } | null>(null);
  const termRef = useRef<Terminal | null>(null);

  useEffect(() => {
    if (!isDesktop() || !hostRef.current) return;
    let dispose = () => {};
    const unlisteners: Array<() => void> = [];
    let ptyId: number | null = null;
    let cancelled = false;

    (async () => {
      ensureXtermCss();
      // dynamic import so the browser bundle never pulls the Tauri API
      const tauri = (await import("@tauri-apps/api")) as unknown as TauriApi;
      const dark = document.documentElement.classList.contains("dark");
      const term = new Terminal({
        fontFamily: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace",
        fontSize: 13,
        lineHeight: 1.25,
        theme: dark ? THEMES.dark : THEMES.light,
        cursorBlink: true,
        scrollback: 5000,
        allowProposedApi: true,
      });
      const fit = new FitAddon();
      term.loadAddon(fit);
      term.open(hostRef.current!);
      fit.fit();
      termRef.current = term; fitRef.current = fit;

      try {
        ptyId = await tauri.core.invoke<number>("terminal_spawn", { cwd, rows: term.rows, cols: term.cols });
      } catch (e) {
        term.writeln(`\x1b[31mCould not start a shell: ${String(e)}\x1b[0m`);
        return;
      }
      if (cancelled) { void tauri.core.invoke("terminal_kill", { id: ptyId }); return; }
      const id = ptyId;
      term.onData((d) => void tauri.core.invoke("terminal_write", { id, data: d }));
      term.onResize(({ rows, cols }) => void tauri.core.invoke("terminal_resize", { id, rows, cols }));
      term.onTitleChange((t) => onTitle?.(t));
      unlisteners.push(await tauri.event.listen("terminal-output", (ev) => { const p = ev.payload as { id: number; data: string }; if (p.id === id) term.write(p.data); }));
      unlisteners.push(await tauri.event.listen("terminal-exit", (ev) => { const p = ev.payload as { id: number }; if (p.id === id) { term.writeln("\r\n\x1b[2m[process exited]\x1b[0m"); onExit?.(); } }));
      register?.({ write: (text) => void tauri.core.invoke("terminal_write", { id, data: text }), focus: () => term.focus() });
      if (initialCommand) void tauri.core.invoke("terminal_write", { id, data: initialCommand + "\r" });

      const onWinResize = () => { fit.fit(); void tauri.core.invoke("terminal_resize", { id, rows: term.rows, cols: term.cols }); };
      window.addEventListener("resize", onWinResize);
      const ro = new ResizeObserver(() => onWinResize());
      ro.observe(hostRef.current!);
      term.focus();
      dispose = () => {
        window.removeEventListener("resize", onWinResize);
        ro.disconnect();
        register?.(null);
        void tauri.core.invoke("terminal_kill", { id });
        term.dispose();
      };
    })();

    return () => {
      cancelled = true;
      unlisteners.forEach((u) => u());
      dispose();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [cwd]);

  // refit when the tab becomes visible again (a hidden xterm measures 0×0)
  useEffect(() => { if (visible) window.setTimeout(() => { fitRef.current?.fit(); termRef.current?.focus(); }, 30); }, [visible]);

  if (!isDesktop())
    return (
      <div className="flex h-full items-center justify-center text-sm text-stone-400">
        The terminal runs in the Atlas desktop app —{" "}
        <code className="ml-1 rounded bg-stone-100 px-1 font-mono text-xs">make desktop</code>.
      </div>
    );

  return <div ref={hostRef} className="h-full w-full" style={{ display: visible ? "block" : "none" }} />;
}
