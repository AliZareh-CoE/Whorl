/** Render-error boundary (#382): a crash while drawing a page shows what happened — message,
 *  component stack, retry / reload / diagnostics — instead of unmounting the whole tree into
 *  a blank window. The report is also posted to the server log (POST /client-errors/). */
import { Component, type ErrorInfo, type ReactNode } from "react";
import { api } from "../app/api";

type Props = { scope: "app" | "page"; resetKey?: string; children: ReactNode };
type State = { error: Error | null; stack: string };

export function reportClientError(where: string, errors: string[]): void {
  const version = document.documentElement.getAttribute("data-version") ?? "";
  api("/client-errors/", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ where, url: location.pathname, errors, version }),
  }).catch(() => undefined);
}

export class ErrorBoundary extends Component<Props, State> {
  state: State = { error: null, stack: "" };

  static getDerivedStateFromError(error: Error): Partial<State> {
    return { error };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    const stack = (info.componentStack ?? "").trim();
    this.setState({ stack });
    reportClientError(`render:${this.props.scope}`, [String(error?.stack || error).slice(0, 1500), stack.slice(0, 1200)]);
  }

  componentDidUpdate(prev: Props) {
    // navigating away from the page that crashed gives it a fresh start
    if (this.state.error && prev.resetKey !== this.props.resetKey) this.setState({ error: null, stack: "" });
  }

  render() {
    const { error, stack } = this.state;
    if (!error) return this.props.children;
    const details = `${error?.stack || String(error)}\n${stack}`;
    const whole = this.props.scope === "app";
    return (
      <div role="alert" data-testid="render-failure" className={whole ? "mx-auto mt-[12vh] max-w-2xl px-6" : "mx-auto max-w-2xl"}>
        <div className="rounded-2xl border border-red-200 bg-white p-6 text-stone-800 shadow-xl dark:border-red-900/60 dark:bg-stone-900 dark:text-stone-100">
          <h1 className="mb-1 text-lg font-semibold">{whole ? "Atlas hit an error and stopped drawing" : "This page hit an error"}</h1>
          <p className="mb-3 text-sm text-stone-500 dark:text-stone-400">{String(error?.message || error)}</p>
          <pre className="mb-4 max-h-56 overflow-auto rounded-lg bg-stone-950 p-3 font-mono text-[11px] leading-4 text-stone-200">{details}</pre>
          <div className="flex flex-wrap items-center gap-2 text-sm">
            <button type="button" onClick={() => this.setState({ error: null, stack: "" })} className="rounded-lg bg-indigo-600 px-3 py-1.5 font-medium text-white hover:bg-indigo-500">Try again</button>
            <button type="button" onClick={() => location.reload()} className="rounded-lg border border-stone-300 px-3 py-1.5 hover:border-indigo-400 dark:border-stone-700">Reload</button>
            <button type="button" onClick={() => void navigator.clipboard?.writeText(details)} className="rounded-lg border border-stone-300 px-3 py-1.5 hover:border-indigo-400 dark:border-stone-700">Copy details</button>
            <a href="/diagnostics" className="text-indigo-600 hover:underline dark:text-indigo-300">Diagnostics</a>
          </div>
          <p className="mt-3 text-xs text-stone-400">The report was written to the server log, which the Diagnostics page shows.</p>
        </div>
      </div>
    );
  }
}
