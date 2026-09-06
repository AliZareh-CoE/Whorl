// In-app updates (Owner epic D2; owner 2026-09-06: "auto update or an update button so I
// won't need to download and install again").
//
// Desktop-only. On launch it asks the Tauri updater (GitHub Releases feed, signed) whether a
// newer build exists — silently — and turns into an "Update to x.y.z" button when one does.
// Clicking downloads + installs, then offers a restart. "Check for updates" stays available
// for a manual check. In the browser there is no __TAURI__ bridge, so it renders nothing.
import { useEffect, useState } from "react";
import { openExternal } from "./external";
import { ArrowDownToLine, RefreshCw } from "lucide-react";

type TauriApi = {
  core: { invoke: (cmd: string, args?: Record<string, unknown>) => Promise<unknown> };
};

const isDesktop = typeof window !== "undefined" && "__TAURI__" in window;
const RELEASES = "https://github.com/alizareh-coe/project-manager/releases/tag/desktop-preview";

type State =
  | { kind: "idle" }
  | { kind: "checking" }
  | { kind: "current"; version: string }
  | { kind: "available"; version: string; notes: string | null }
  | { kind: "installing"; version: string }
  | { kind: "updated"; version: string }
  | { kind: "error"; message: string; silent?: boolean };

/** Turn the updater's raw error into the one sentence that says what to do. */
function explain(raw: string): string {
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

  // silent check once per launch (the desktop shell mounts the app once)
  useEffect(() => {
    if (isDesktop) void check(true);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  if (!isDesktop) return null;

  const install = async (version: string) => {
    setState({ kind: "installing", version });
    try {
      const out = (await (await tauri()).core.invoke("install_update")) as { installed_version: string | null };
      setState(out.installed_version ? { kind: "updated", version: out.installed_version } : { kind: "current", version });
    } catch (e) {
      setState({ kind: "error", message: String(e) });
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
      <button onClick={() => install(state.version)} className={`${base} glow-accent bg-indigo-600 text-white hover:bg-indigo-500`} title={state.notes ?? `Download and install ${state.version}`}>
        <ArrowDownToLine className="h-3.5 w-3.5" aria-hidden="true" />Update to {state.version}
      </button>
    );
  if (state.kind === "installing")
    return (
      <span className={`${base} text-indigo-500`}><RefreshCw className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />Installing {state.version}…</span>
    );
  if (state.kind === "updated")
    return (
      <button onClick={restart} className={`${base} glow-accent bg-indigo-600 text-white hover:bg-indigo-500`} title={`Installed ${state.version} — restart to finish`}>
        <RefreshCw className="h-3.5 w-3.5" aria-hidden="true" />Restart to finish update
      </button>
    );
  if (state.kind === "error")
    return (
      <span className={`${base} flex-wrap text-stone-400`} title={state.message} data-testid="updater-error">
        <button onClick={() => check()} className="hover:text-stone-700 dark:hover:text-stone-200">{state.silent ? "Updates unavailable — why?" : "Update check failed — retry"}</button>
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
