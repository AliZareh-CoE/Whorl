/** #440 (backlog #158): a calm bottom-centre toast with an Undo — for the actions that vanish a
 *  row immediately (filing or dismissing a capture). One host, mounted once in main.tsx;
 *  `showUndo(message, undo)` from anywhere. The newest toast replaces the previous one; Undo
 *  runs the callback once, Esc or the timer just lets it go. */
import { useEffect, useState } from "react";
import { createPortal } from "react-dom";
import { Undo2, X } from "lucide-react";

type Toast = { id: number; message: string; undo: () => void | Promise<void>; ms: number };

let push: ((t: Toast) => void) | null = null;
let current: Toast | null = null; // #549: the toast on screen, so a key (`z` on Today) can fire it
let seq = 0;

export function showUndo(message: string, undo: () => void | Promise<void>, ms = 6000): void {
  const toast = { id: ++seq, message, undo, ms };
  if (push) push(toast);
}

/** Fire the undo of the toast on screen (if any) and take it down. Returns whether one ran. */
export function undoLast(): boolean {
  const t = current;
  if (!t || !push) return false;
  push(null as unknown as Toast);
  void t.undo();
  return true;
}

export function UndoHost() {
  const [toast, setToast] = useState<Toast | null>(null);
  useEffect(() => { push = setToast; return () => { push = null; current = null; }; }, []);
  useEffect(() => { current = toast; }, [toast]);
  useEffect(() => {
    if (!toast) return;
    const t = window.setTimeout(() => setToast((cur) => (cur?.id === toast.id ? null : cur)), toast.ms);
    const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") setToast(null); };
    window.addEventListener("keydown", onKey);
    return () => { window.clearTimeout(t); window.removeEventListener("keydown", onKey); };
  }, [toast]);
  if (!toast) return null;
  // a portal: `fixed` inside a transformed ancestor would pin the toast to that box, not the window
  return createPortal(
    <div className="pointer-events-none fixed inset-x-0 bottom-6 z-50 flex justify-center px-4" role="status" aria-live="polite">
      <div className="pointer-events-auto flex items-center gap-3 rounded-full border border-stone-200 bg-white/95 py-1.5 pl-4 pr-2 text-sm text-stone-700 shadow-xl backdrop-blur dark:border-stone-700 dark:bg-stone-900/95 dark:text-stone-200" data-testid="undo-toast">
        <span className="max-w-md truncate">{toast.message}</span>
        <button type="button" onClick={async () => { const t = toast; setToast(null); await t.undo(); }} className="inline-flex items-center gap-1 rounded-full bg-indigo-600 px-2.5 py-1 text-xs font-medium text-white hover:bg-indigo-700" data-testid="undo-button"><Undo2 className="h-3.5 w-3.5" aria-hidden="true" />Undo</button>
        <button type="button" onClick={() => setToast(null)} aria-label="Dismiss" className="rounded-full p-1 text-stone-400 hover:text-stone-600 dark:hover:text-stone-200"><X className="h-3.5 w-3.5" aria-hidden="true" /></button>
      </div>
    </div>,
    document.body,
  );
}
