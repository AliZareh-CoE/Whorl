// In-app "Check for updates" control (Owner epic D2, 2026-06-14).
//
// Desktop-only: it invokes the Tauri `check_for_updates` command, which asks the GitHub
// Releases update feed for a newer signed build and installs it if found. In the browser
// there is no __TAURI__ bridge, so the component renders nothing (like the terminal).
import { useState } from "react";

type TauriApi = {
  core: { invoke: (cmd: string, args?: Record<string, unknown>) => Promise<unknown> };
};

const isDesktop = typeof window !== "undefined" && "__TAURI__" in window;

type State =
  | { kind: "idle" }
  | { kind: "checking" }
  | { kind: "current" }
  | { kind: "updated"; version: string }
  | { kind: "error"; message: string };

export function UpdaterButton() {
  const [state, setState] = useState<State>({ kind: "idle" });
  if (!isDesktop) return null;

  const check = async () => {
    setState({ kind: "checking" });
    try {
      const tauri = (await import("@tauri-apps/api")) as unknown as TauriApi;
      const out = (await tauri.core.invoke("check_for_updates")) as {
        installed_version: string | null;
      };
      setState(
        out.installed_version
          ? { kind: "updated", version: out.installed_version }
          : { kind: "current" },
      );
    } catch (e) {
      setState({ kind: "error", message: String(e) });
    }
  };

  const restart = async () => {
    try {
      const tauri = (await import("@tauri-apps/api")) as unknown as TauriApi;
      // relaunches the whole app so the new binary + bundled server take effect; a bare
      // webview reload would keep running the old process.
      await tauri.core.invoke("restart_app");
    } catch (e) {
      setState({ kind: "error", message: String(e) });
    }
  };

  if (state.kind === "updated") {
    return (
      <button
        onClick={restart}
        className="mb-2 block text-left text-indigo-600 hover:text-indigo-700"
        title={`Installed ${state.version} — restart to finish`}
      >
        Update ready ({state.version}) — restart
      </button>
    );
  }

  const label =
    state.kind === "checking"
      ? "Checking…"
      : state.kind === "current"
        ? "Up to date ✓"
        : state.kind === "error"
          ? "Update check failed — retry"
          : "Check for updates";

  return (
    <button
      onClick={check}
      disabled={state.kind === "checking"}
      className="mb-2 block text-left hover:text-stone-600 disabled:opacity-60"
      title={state.kind === "error" ? state.message : "Check for a newer Atlas build"}
    >
      {label}
    </button>
  );
}
