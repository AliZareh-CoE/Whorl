/** In-app dialogs (owner reports, 2026-09-06). `window.prompt/confirm/alert` are native browser
 * dialogs that the desktop webview may swallow (no sheet appears, the promise resolves null) —
 * so every question the app asks goes through this host instead: confirm (optionally with a
 * typed-name guard for destructive actions), prompt (single or multi-line) and notice.
 *
 * Imperative API so call sites stay one line:  `if (await confirmDialog({...})) mutate()`.
 * Mount `<DialogHost />` once at the app root (main.tsx) — it renders nothing until asked. */
import { useEffect, useRef, useState } from "react";
import { AlertTriangle } from "lucide-react";

type ConfirmOpts = { title: string; body?: React.ReactNode; confirmLabel?: string; cancelLabel?: string; danger?: boolean; verify?: string };
type PromptOpts = { title: string; body?: React.ReactNode; label?: string; initial?: string; placeholder?: string; multiline?: boolean; confirmLabel?: string; validate?: (v: string) => string | null };
type NoticeOpts = { title: string; body?: React.ReactNode; okLabel?: string; wide?: boolean };
type Request =
  | { kind: "confirm"; opts: ConfirmOpts; resolve: (v: boolean) => void }
  | { kind: "prompt"; opts: PromptOpts; resolve: (v: string | null) => void }
  | { kind: "notice"; opts: NoticeOpts; resolve: (v: void) => void };

let push: ((r: Request) => void) | null = null;
const queue: Request[] = [];
function submit(r: Request) { if (push) push(r); else queue.push(r); }

export function confirmDialog(opts: ConfirmOpts): Promise<boolean> { return new Promise((resolve) => submit({ kind: "confirm", opts, resolve })); }
export function promptDialog(opts: PromptOpts): Promise<string | null> { return new Promise((resolve) => submit({ kind: "prompt", opts, resolve })); }
export function noticeDialog(opts: NoticeOpts): Promise<void> { return new Promise((resolve) => submit({ kind: "notice", opts, resolve })); }
/** Surface an error the user must see (an API failure, a Tauri command refusing). */
export function errorDialog(title: string, error: unknown): Promise<void> {
  const text = error instanceof Error ? error.message : typeof error === "string" ? error : JSON.stringify(error);
  return noticeDialog({ title, body: <pre className="max-h-48 overflow-auto whitespace-pre-wrap font-mono text-xs text-red-600 dark:text-red-300">{text}</pre> });
}

const btn = "rounded-lg px-3 py-1.5 text-sm font-medium transition-colors disabled:opacity-40";
const primary = `${btn} bg-indigo-600 text-white hover:bg-indigo-700`;
const dangerBtn = `${btn} bg-red-600 text-white hover:bg-red-700`;
const quiet = `${btn} border border-stone-300 text-stone-700 hover:border-stone-400 dark:border-stone-700 dark:text-stone-200 dark:hover:border-stone-500`;
const field = "w-full rounded-lg border border-stone-300 bg-white px-3 py-2 text-sm text-stone-900 placeholder:text-stone-400 focus:border-indigo-500 focus:outline-none focus:ring-1 focus:ring-indigo-500 dark:border-stone-700 dark:bg-stone-950 dark:text-stone-100";

export function DialogHost() {
  const [current, setCurrent] = useState<Request | null>(null);
  const [pending, setPending] = useState<Request[]>([]);
  useEffect(() => {
    push = (r) => setPending((p) => [...p, r]);
    if (queue.length) { const drained = queue.splice(0); setPending((p) => [...p, ...drained]); }
    return () => { push = null; };
  }, []);
  useEffect(() => { if (!current && pending.length) { setCurrent(pending[0]); setPending((p) => p.slice(1)); } }, [current, pending]);
  if (!current) return null;
  const done = () => setCurrent(null);
  return <Sheet key={String(pending.length) + current.kind + current.opts.title} req={current} onDone={done} />;
}

function Sheet({ req, onDone }: { req: Request; onDone: () => void }) {
  const [value, setValue] = useState(req.kind === "prompt" ? (req.opts.initial ?? "") : "");
  const [typed, setTyped] = useState("");
  const [error, setError] = useState<string | null>(null);
  const first = useRef<HTMLInputElement | HTMLTextAreaElement | HTMLButtonElement>(null);
  useEffect(() => { const t = window.setTimeout(() => { first.current?.focus(); if (first.current instanceof HTMLInputElement) first.current.select(); }, 20); return () => window.clearTimeout(t); }, []);

  const cancel = () => { if (req.kind === "confirm") req.resolve(false); else if (req.kind === "prompt") req.resolve(null); else req.resolve(); onDone(); };
  const verifyOk = req.kind !== "confirm" || !req.opts.verify || typed.trim() === req.opts.verify;
  const ok = () => {
    if (req.kind === "confirm") { if (!verifyOk) return; req.resolve(true); }
    else if (req.kind === "prompt") {
      const v = value; const problem = req.opts.validate?.(v) ?? null;
      if (problem) { setError(problem); return; }
      req.resolve(v);
    } else req.resolve();
    onDone();
  };
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") { e.preventDefault(); cancel(); } };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  const danger = req.kind === "confirm" && req.opts.danger;
  return (
    <div className="fixed inset-0 z-[70] flex items-center justify-center bg-stone-950/45 p-4 backdrop-blur-[2px]" onMouseDown={(e) => { if (e.target === e.currentTarget) cancel(); }} role="presentation">
      <form role="dialog" aria-modal="true" aria-labelledby="atlas-dialog-title" data-testid={`dialog-${req.kind}`} onSubmit={(e) => { e.preventDefault(); ok(); }}
        className={`w-full ${req.kind === "notice" && (req.opts as NoticeOpts).wide ? "max-w-3xl" : "max-w-md"} rounded-2xl border border-stone-200 bg-white p-5 shadow-2xl dark:border-stone-700 dark:bg-stone-900`}>
        <h2 id="atlas-dialog-title" className="flex items-center gap-2 text-base font-semibold text-stone-900 dark:text-stone-100">
          {danger && <AlertTriangle className="h-4 w-4 text-red-500" aria-hidden="true" />}{req.opts.title}
        </h2>
        {req.opts.body && <div className="mt-2 text-sm leading-relaxed text-stone-600 dark:text-stone-300">{req.opts.body}</div>}
        {req.kind === "prompt" && (
          <label className="mt-3 block text-sm">
            {req.opts.label && <span className="mb-1 block text-xs font-medium uppercase tracking-wide text-stone-400">{req.opts.label}</span>}
            {req.opts.multiline
              ? <textarea ref={first as React.RefObject<HTMLTextAreaElement>} value={value} onChange={(e) => { setValue(e.target.value); setError(null); }} rows={5} placeholder={req.opts.placeholder} className={field} onKeyDown={(e) => { if ((e.metaKey || e.ctrlKey) && e.key === "Enter") ok(); }} />
              : <input ref={first as React.RefObject<HTMLInputElement>} value={value} onChange={(e) => { setValue(e.target.value); setError(null); }} placeholder={req.opts.placeholder} className={field} />}
            {error && <span className="mt-1 block text-xs text-red-600 dark:text-red-300">{error}</span>}
          </label>
        )}
        {req.kind === "confirm" && req.opts.verify && (
          <label className="mt-3 block text-sm">
            <span className="mb-1 block text-xs text-stone-500 dark:text-stone-400">Type <b className="font-mono text-stone-800 dark:text-stone-100">{req.opts.verify}</b> to confirm</span>
            <input ref={first as React.RefObject<HTMLInputElement>} value={typed} onChange={(e) => setTyped(e.target.value)} className={field} autoComplete="off" data-testid="dialog-verify" />
          </label>
        )}
        <div className="mt-5 flex justify-end gap-2">
          {req.kind !== "notice" && <button type="button" onClick={cancel} className={quiet}>{(req.kind === "confirm" && req.opts.cancelLabel) || "Cancel"}</button>}
          <button type="submit" ref={req.kind === "notice" || (req.kind === "confirm" && !req.opts.verify) ? (first as React.RefObject<HTMLButtonElement>) : undefined} disabled={!verifyOk} className={danger ? dangerBtn : primary} data-testid="dialog-ok">
            {req.kind === "notice" ? (req.opts.okLabel ?? "OK") : (req.opts.confirmLabel ?? (req.kind === "confirm" ? "Confirm" : "Save"))}
          </button>
        </div>
      </form>
    </div>
  );
}
