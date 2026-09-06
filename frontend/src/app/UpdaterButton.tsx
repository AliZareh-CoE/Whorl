// In-app updates (Owner epic D2; owner 2026-09-06: "auto update or an update button so I
// won't need to download and install again").
//
// Desktop-only. On launch it asks the Tauri updater (GitHub Releases feed, signed) whether a
// newer build exists — silently — and turns into an "Update to x.y.z" button when one does.
// Clicking downloads + installs, then offers a restart. "Check for updates" stays available
// for a manual check. In the browser there is no __TAURI__ bridge, so it renders nothing.
import { useEffect, useState } from "react";
import { openExternal } from "./external";
import { confirmDialog } from "../components/Dialog";
import { ArrowDownToLine, RefreshCw } from "lucide-react";

type TauriApi = {
  core: { invoke: (cmd: string, args?: Record<string, unknown>) => Promise<unknown> };
  event: { listen: (name: string, cb: (ev: { payload: unknown }) => void) => Promise<() => void> };
};
type Progress = { downloaded: number; total: number | null; done: boolean };
const RECHECK_MS = 6 * 60 * 60 * 1000; // backlog #304: look again while the app stays open

function mb(n: number): string { return `${(n / 1048576).toFixed(1)} MB`; }

const isDesktop = typeof window !== "undefined" && "__TAURI__" in window;
const RELEASES = "https://github.com/alizareh-coe/project-manager/releases/tag/desktop-preview";

type State =
  | { kind: "idle" }
  | { kind: "checking" }
  | { kind: "current"; version: string }
  | { kind: "available"; version: string; notes: string | null }
  | { kind: "installing"; version: string; progress?: Progress }
  | { kind: "updated"; version: string }
  | { kind: "error"; message: string; silent?: boolean };

/** Turn the updater's raw error into the one sentence that says what to do. */
function explain(raw: string): string {
  if (/not allowed by ACL/i.test(raw)) return "This build's shell blocked the command (a capability bug fixed in 0.1.79+). Install the newest build from the releases page once; after that updates work in-app.";
  if (/404|not found/i.test(raw)) return "The update feed answered 404. The releases live in a private GitHub repository, which the app cannot read — publish them to the public feed (README › Auto-update).";
  if (/signature|verify|pubkey|public key/i.test(raw)) return "The download's signature did not match this app's public key. The release was signed with a different key — reinstall from the releases page.";
  if (/dns|resolve|connect|network|timed? ?out|offline/i.test(raw)) return "Could not reach GitHub to check for updates (offline?).";
  return raw;
}

async function tauri(): Promise<TauriApi> {
  return (await import("@tauri-apps/api")) as unknown as TauriApi;
}

export function UpdaterButton() {
  const [state, setState] = useState<State>({ kind: "idle" });

  const check = async (silent = false) => {
    if (!silent) setState({ kind: "checking" });
    try {
      const out = (await (await tauri()).core.invoke("check_update")) as {
        available_version: string | null;
        current_version: string;
        notes: string | null;
      };
      if (out.available_version) setState({ kind: "available", version: out.available_version, notes: out.notes });
      else if (!silent) setState({ kind: "current", version: out.current_version });
    } catch (e) {
      setState({ kind: "error", message: explain(String(e)), silent });
    }
  };

  // silent check once per launch, then every few hours while the window stays open
  useEffect(() => {
    if (!isDesktop) return;
    void check(true);
    const timer = window.setInterval(() => void check(true), RECHECK_MS);
    return () => window.clearInterval(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (!isDesktop) return null;

  const install = async (version: string, notes: string | null) => {
    // release notes first — the feed's body is the changelog the workflow writes
    const ok = await confirmDialog({ title: `Update to ${version}?`, confirmLabel: "Download and install", body: notes ? <pre className="max-h-56 overflow-auto whitespace-pre-wrap font-sans text-xs leading-relaxed">{notes.slice(0, 2000)}</pre> : "The app restarts when the install finishes." });
    if (!ok) return;
    setState({ kind: "installing", version });
    let stop: (() => void) | null = null;
    try {
      const t = await tauri();
      stop = await t.event.listen("update-progress", (ev) => { const p = ev.payload as Progress; setState((s) => (s.kind === "installing" ? { ...s, progress: p } : s)); });
      const out = (await t.core.invoke("install_update")) as { installed_version: string | null };
      setState(out.installed_version ? { kind: "updated", version: out.installed_version } : { kind: "current", version });
    } catch (e) {
      setState({ kind: "error", message: explain(String(e)) });
    } finally {
      stop?.();
    }
  };

  const restart = async () => {
    try {
      await (await tauri()).core.invoke("restart_app");
    } catch (e) {
      setState({ kind: "error", message: String(e) });
    }
  };

  const base = "mb-1 flex w-full items-center gap-2 rounded-md px-1.5 py-1 text-left transition-colors";

  if (state.kind === "available")
    return (
      <button onClick={() => void install(state.version, state.notes)} className={`${base} glow-accent bg-indigo-600 text-white hover:bg-indigo-500`} title={state.notes ?? `Download and install ${state.version}`} data-testid="update-available">
        <ArrowDownToLine className="h-3.5 w-3.5" aria-hidden="true" />Update to {state.version}
      </button>
    );
  if (state.kind === "installing") {
    const p = state.progress;
    const pct = p && p.total ? Math.min(100, Math.round((100 * p.downloaded) / p.total)) : null;
    const label = !p ? `Preparing ${state.version}…` : p.done ? `Installing ${state.version}…` : pct !== null ? `Downloading ${pct}%` : `Downloading ${mb(p.downloaded)}…`;
    return (
      <span className={`${base} flex-col items-stretch text-indigo-500`} data-testid="update-progress" aria-live="polite">
        <span className="flex items-center gap-2"><RefreshCw className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />{label}</span>
        {pct !== null && !p?.done && <span className="mt-1 h-1 w-full overflow-hidden rounded-full bg-indigo-500/20"><span className="block h-full rounded-full bg-indigo-500 transition-[width]" style={{ width: `${pct}%` }} /></span>}
      </span>
    );
  }
  if (state.kind === "updated")
    return (
      <button onClick={restart} className={`${base} glow-accent bg-indigo-600 text-white hover:bg-indigo-500`} title={`Installed ${state.version} — restart to finish`}>
        <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />Restart to finish update
      </button>
    );
  if (state.kind === "error")
    return (
      <span className={`${base} flex-wrap text-stone-400`} title={state.message} data-testid="updater-error">
        <button onClick={() => check()} className="hover:text-stone-700 dark:hover:text-stone-200">{state.silent ? "Updates unavailable" : "Update check failed — retry"}</button>
        <a href="/diagnostics" className="text-indigo-500 hover:underline">why?</a>
        <button type="button" onClick={() => void openExternal(RELEASES)} className="text-indigo-500 hover:underline">get it manually ↗</button>
      </span>
    );

  const label = state.kind === "checking" ? "Checking for updates…" : state.kind === "current" ? `Up to date (${state.version}) ✓` : "Check for updates";
  return (
    <button onClick={() => check()} disabled={state.kind === "checking"} className={`${base} hover:text-stone-700 disabled:opacity-60 dark:hover:text-stone-200`} title="Ask the release feed for a newer Atlas build">
      <RefreshCw className={`h-3.5 w-3.5 ${state.kind === "checking" ? "animate-spin" : ""}`} aria-hidden="true" />{label}
    </button>
  );
}
