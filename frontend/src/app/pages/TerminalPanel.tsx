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

// Built-in terminal panel (Owner #30 slice 5-ii): xterm.js wired to the desktop shell's
// PTY over Tauri IPC. Desktop-only — in the browser there is no PTY (and we never expose
// one server-side), so this renders a hint instead. The whole panel is gated on
// window.__TAURI__ by the caller.
type TauriApi = {
  core: { invoke: (cmd: string, args?: Record<string, unknown>) => Promise<unknown> };
  event: { listen: (e: string, cb: (ev: { payload: unknown }) => void) => Promise<() => void> };
};

function isDesktop(): boolean {
  return typeof window !== "undefined" && "__TAURI__" in window;
}

export default function TerminalPanel({ cwd }: { cwd?: string }) {
  const hostRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (!isDesktop() || !hostRef.current) return;
    let dispose = () => {};
    let unlisten: (() => void) | undefined;

    (async () => {
      ensureXtermCss();
      // dynamic import so the browser bundle never pulls the Tauri API
      const tauri = (await import("@tauri-apps/api")) as unknown as TauriApi;
      const term = new Terminal({
        fontFamily: "ui-monospace, monospace",
        fontSize: 13,
        theme: { background: "#1c1917", foreground: "#e7e5e4" },
        cursorBlink: true,
      });
      const fit = new FitAddon();
      term.loadAddon(fit);
      term.open(hostRef.current!);
      fit.fit();

      await tauri.core.invoke("terminal_spawn", { cwd, rows: term.rows, cols: term.cols });
      term.onData((d) => tauri.core.invoke("terminal_write", { data: d }));
      term.onResize(({ rows, cols }) => tauri.core.invoke("terminal_resize", { rows, cols }));
      unlisten = await tauri.event.listen("terminal-output", (ev) => term.write(ev.payload as string));

      const onWinResize = () => {
        fit.fit();
        tauri.core.invoke("terminal_resize", { rows: term.rows, cols: term.cols });
      };
      window.addEventListener("resize", onWinResize);
      dispose = () => {
        window.removeEventListener("resize", onWinResize);
        term.dispose();
      };
    })();

    return () => {
      unlisten?.();
      dispose();
    };
  }, [cwd]);

  if (!isDesktop())
    return (
      <div className="flex h-full items-center justify-center text-sm text-stone-400">
        The terminal runs in the Atlas desktop app —{" "}
        <code className="ml-1 rounded bg-stone-100 px-1 font-mono text-xs">make desktop</code>.
      </div>
    );

  return <div ref={hostRef} className="h-full w-full" />;
}
