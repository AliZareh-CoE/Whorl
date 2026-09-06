/** Plan v2 slice 3 — milestone drawer: title, due date, notes (autosave), tasks, delete.
 *  Opens from a milestone title on the Plan page; all edits are PATCH /milestones/{id}/ and
 *  /tasks/. */
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Check, Plus, Trash2, X } from "lucide-react";
import { confirmDialog } from "../../../components/Dialog";
import { api } from "../../api";

type Task = { id: number; title: string; done: boolean; due_date?: string | null };
export type DrawerMilestone = { id: number; title: string; due_date: string | null; completed_at: string | null; notes?: string; tasks: Task[]; phase: string };

export default function MilestoneDrawer({ slug, milestone, onClose }: { slug: string; milestone: DrawerMilestone; onClose: () => void }) {
  const queryClient = useQueryClient();
  const invalidate = () => { queryClient.invalidateQueries({ queryKey: ["plan", slug] }); queryClient.invalidateQueries({ queryKey: ["focus", slug] }); queryClient.invalidateQueries({ queryKey: ["roadmap", slug] }); queryClient.invalidateQueries({ queryKey: ["overview", slug] }); };
  const [title, setTitle] = useState(milestone.title);
  const [due, setDue] = useState(milestone.due_date ?? "");
  const [notes, setNotes] = useState(milestone.notes ?? "");
  const [taskDraft, setTaskDraft] = useState("");
  const [saving, setSaving] = useState(false);
  const timer = useRef<number>(0);
  useEffect(() => { setTitle(milestone.title); setDue(milestone.due_date ?? ""); setNotes(milestone.notes ?? ""); }, [milestone.id]); // eslint-disable-line react-hooks/exhaustive-deps
  const patch = useMutation({
    mutationFn: (body: Record<string, unknown>) => api(`/milestones/${milestone.id}/`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
    onSettled: () => { setSaving(false); invalidate(); },
  });
  const queue = (body: Record<string, unknown>) => { setSaving(true); window.clearTimeout(timer.current); timer.current = window.setTimeout(() => patch.mutate(body), 700); };
  const remove = useMutation({ mutationFn: () => api(`/milestones/${milestone.id}/`, { method: "DELETE" }), onSuccess: () => { invalidate(); onClose(); } });
  const addTask = useMutation({ mutationFn: (t: string) => api(`/tasks/`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ milestone: milestone.id, title: t }) }), onSuccess: invalidate });
  const toggleTask = useMutation({ mutationFn: (t: Task) => api(`/tasks/${t.id}/`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ done: !t.done }) }), onSuccess: invalidate });
  const removeTask = useMutation({ mutationFn: (id: number) => api(`/tasks/${id}/`, { method: "DELETE" }), onSuccess: invalidate });
  useEffect(() => { const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); }; window.addEventListener("keydown", onKey); return () => window.removeEventListener("keydown", onKey); }, [onClose]);
  return (
    <aside className="drawer-solid rise fixed inset-y-0 right-0 z-30 w-full max-w-md overflow-y-auto border-l border-stone-200 p-5 shadow-2xl dark:border-stone-800" role="dialog" aria-label={`Milestone: ${milestone.title}`} data-testid="milestone-drawer">
      <div className="mb-3 flex items-center justify-between text-[10px] font-semibold uppercase tracking-[0.14em] text-stone-400">
        <span>Milestone · {milestone.phase}</span>
        <span className="flex items-center gap-3 normal-case tracking-normal">{saving ? "saving…" : patch.isSuccess ? "saved" : ""}<button type="button" onClick={onClose} aria-label="Close" className="rounded-md p-1 hover:bg-stone-100 dark:hover:bg-stone-800"><X className="h-4 w-4" aria-hidden="true" /></button></span>
      </div>
      <input value={title} onChange={(e) => { setTitle(e.target.value); queue({ title: e.target.value }); }} className="font-display w-full bg-transparent text-xl font-semibold leading-snug text-stone-900 focus:outline-none dark:text-stone-100" aria-label="Milestone title" />
      <div className="mt-3 flex flex-wrap items-center gap-3 text-sm">
        <label className="flex items-center gap-2 text-stone-500">Due
          <input type="date" value={due} onChange={(e) => { setDue(e.target.value); queue({ due_date: e.target.value || null }); }} className="rounded-md border border-stone-300 bg-white px-2 py-1 text-sm dark:border-stone-700 dark:bg-stone-800 dark:text-stone-100" aria-label="Due date" />
        </label>
        <button type="button" onClick={() => patch.mutate({ completed_at: milestone.completed_at ? null : new Date().toISOString() })} className={`inline-flex items-center gap-1 rounded-md px-2.5 py-1 text-xs font-medium ${milestone.completed_at ? "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300" : "border border-stone-300 text-stone-600 hover:border-indigo-300 dark:border-stone-700 dark:text-stone-300"}`}><Check className="h-3 w-3" aria-hidden="true" />{milestone.completed_at ? "Completed — undo" : "Mark complete"}</button>
      </div>
      <div className="mt-5">
        <p className="mb-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-stone-400">Notes</p>
        <textarea value={notes} onChange={(e) => { setNotes(e.target.value); queue({ notes: e.target.value }); }} rows={6} placeholder="What does done look like? Links, criteria, who to ask. Markdown, autosaves." className="w-full resize-y rounded-lg border border-stone-200 bg-stone-50 px-3 py-2 text-sm leading-relaxed placeholder:text-stone-400 focus:border-indigo-400 focus:outline-none dark:border-stone-800 dark:bg-stone-950/40 dark:text-stone-200" aria-label="Milestone notes" />
      </div>
      <div className="mt-5">
        <p className="mb-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-stone-400">Tasks <span className="normal-case tracking-normal">{milestone.tasks.filter((t) => t.done).length}/{milestone.tasks.length}</span></p>
        <ul className="space-y-1.5">
          {milestone.tasks.map((t) => (
            <li key={t.id} className="group flex items-center gap-2 text-sm">
              <button type="button" onClick={() => toggleTask.mutate(t)} aria-label={`Toggle ${t.title}`} className={`flex h-4 w-4 shrink-0 items-center justify-center rounded border text-[10px] ${t.done ? "border-stone-400 bg-stone-400 text-white" : "border-stone-300 text-transparent hover:border-indigo-400 dark:border-stone-600"}`}><Check className="h-2.5 w-2.5" aria-hidden="true" /></button>
              <span className={`min-w-0 flex-1 ${t.done ? "text-stone-400 line-through" : "text-stone-700 dark:text-stone-200"}`}>{t.title}</span>
              <button type="button" onClick={() => removeTask.mutate(t.id)} aria-label={`Delete ${t.title}`} className="text-stone-300 opacity-0 hover:text-red-500 group-hover:opacity-100"><Trash2 className="h-3.5 w-3.5" aria-hidden="true" /></button>
            </li>
          ))}
        </ul>
        <form onSubmit={(e) => { e.preventDefault(); const t = taskDraft.trim(); if (t) { addTask.mutate(t); setTaskDraft(""); } }} className="mt-2 flex items-center gap-2">
          <Plus className="h-4 w-4 text-stone-300" aria-hidden="true" />
          <input value={taskDraft} onChange={(e) => setTaskDraft(e.target.value)} placeholder="New task… Enter to add" className="min-w-0 flex-1 bg-transparent py-0.5 text-sm placeholder:text-stone-400 focus:outline-none dark:text-stone-100" aria-label="New task" />
        </form>
      </div>
      <div className="mt-8 border-t border-stone-100 pt-4 dark:border-stone-800">
        <button type="button" onClick={async () => { if (await confirmDialog({ title: `Delete “${milestone.title}”?`, body: milestone.tasks.length ? `Its ${milestone.tasks.length} task${milestone.tasks.length === 1 ? "" : "s"} go with it.` : undefined, danger: true, confirmLabel: "Delete milestone" })) remove.mutate(); }} className="inline-flex items-center gap-1 text-xs text-stone-400 hover:text-red-500"><Trash2 className="h-3.5 w-3.5" aria-hidden="true" />Delete milestone</button>
      </div>
    </aside>
  );
}
