/** Today — the owner's plain to-do list (owner request, 2026-09-06). One list, one input,
 *  one click to tick. Nothing is lost overnight: open items simply stay. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Check, Pencil, Plus, Sparkles, Trash2 } from "lucide-react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { ErrorState } from "../../components/ErrorState";
import { Skeleton } from "../../components/Skeleton";

type Todo = { id: number; text: string; done: boolean; done_at: string | null; position: number; project: string | null; created_at: string };
type Page<T> = { count: number; results: T[] };

const panel = "rounded-2xl border border-stone-200 bg-white dark:border-stone-800 dark:bg-stone-900";

export default function Today() {
  const queryClient = useQueryClient();
  const [text, setText] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  const { data, isLoading, error, refetch } = useQuery({ queryKey: ["todos"], queryFn: () => api<Page<Todo>>("/todos/?page_size=200") });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["todos"] });
  const add = useMutation({
    mutationFn: (t: string) => api<Todo>("/todos/", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text: t }) }),
    onSuccess: () => { setText(""); refresh(); inputRef.current?.focus(); },
  });
  const toggle = useMutation({
    mutationFn: ({ id, done }: { id: number; done: boolean }) => api<Todo>(`/todos/${id}/`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ done }) }),
    onMutate: async ({ id, done }) => {
      await queryClient.cancelQueries({ queryKey: ["todos"] });
      const prev = queryClient.getQueryData<Page<Todo>>(["todos"]);
      if (prev) queryClient.setQueryData<Page<Todo>>(["todos"], { ...prev, results: prev.results.map((t) => (t.id === id ? { ...t, done } : t)) });
      return { prev };
    },
    onError: (_e, _v, ctx) => { if (ctx?.prev) queryClient.setQueryData(["todos"], ctx.prev); },
    onSettled: refresh,
  });
  const remove = useMutation({ mutationFn: (id: number) => api(`/todos/${id}/`, { method: "DELETE" }), onSuccess: refresh });
  const edit = useMutation({ mutationFn: ({ id, text: t }: { id: number; text: string }) => api<Todo>(`/todos/${id}/`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text: t }) }), onSuccess: refresh });
  const reorder = useMutation({
    mutationFn: async ({ a, b }: { a: Todo; b: Todo }) => {
      // swap positions (ties broken by giving the mover a fresh slot)
      const pa = a.position === b.position ? b.position + 1 : b.position;
      const pb = a.position === b.position ? a.position : a.position;
      await api(`/todos/${a.id}/`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ position: pa }) });
      await api(`/todos/${b.id}/`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ position: pb }) });
    },
    onSettled: refresh,
  });
  const [cursor, setCursor] = useState(0);
  const [editing, setEditing] = useState<number | null>(null);
  const clearDone = useMutation({ mutationFn: () => api("/todos/clear-done/", { method: "POST" }), onSuccess: refresh });

  useEffect(() => { inputRef.current?.focus(); }, []);

  if (error) return <ErrorState message="Couldn't load your list." onRetry={() => refetch()} />;
  const items = data?.results ?? [];
  const open = items.filter((t) => !t.done);
  const done = items.filter((t) => t.done);
  const today = new Date().toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" });
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement | null)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || editing !== null) return;
      const t = open[cursor];
      if (e.key === "j" || e.key === "ArrowDown") { if (e.altKey && t && cursor < open.length - 1) { e.preventDefault(); reorder.mutate({ a: t, b: open[cursor + 1] }); setCursor((i) => i + 1); return; } e.preventDefault(); setCursor((i) => Math.min(open.length - 1, i + 1)); }
      else if (e.key === "k" || e.key === "ArrowUp") { if (e.altKey && t && cursor > 0) { e.preventDefault(); reorder.mutate({ a: t, b: open[cursor - 1] }); setCursor((i) => i - 1); return; } e.preventDefault(); setCursor((i) => Math.max(0, i - 1)); }
      else if (!t) return;
      else if (e.key === " " || e.key === "Enter") { e.preventDefault(); toggle.mutate({ id: t.id, done: true }); }
      else if (e.key === "e") { e.preventDefault(); setEditing(t.id); }
      else if (e.key === "x" || e.key === "Delete") { e.preventDefault(); remove.mutate(t.id); }
      else if (e.key === "n" || e.key === "/") { e.preventDefault(); inputRef.current?.focus(); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, cursor, editing]);

  return (
    <div className="mx-auto max-w-2xl">
      <div className="mb-5">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-stone-400">{today}</p>
        <h1 className="font-display mt-1 text-3xl font-bold tracking-tight dark:text-stone-100">
          Today{" "}
          <span className="text-gradient">{open.length === 0 ? "· all clear" : `· ${open.length} to do`}</span>
        </h1>
      </div>

      <form
        onSubmit={(e) => { e.preventDefault(); const t = text.trim(); if (t) add.mutate(t); }}
        className={`${panel} hairline-gradient rise mb-4 flex items-center gap-2 p-2 pl-4`}
      >
        <Plus className="h-4 w-4 shrink-0 text-indigo-400" aria-hidden="true" />
        <input
          ref={inputRef}
          value={text}
          onChange={(e) => setText(e.target.value)}
          placeholder="What needs doing? Press Enter."
          maxLength={300}
          className="min-w-0 flex-1 bg-transparent py-2 text-base placeholder:text-stone-400 focus:outline-none dark:text-stone-100"
        />
        <button type="submit" disabled={!text.trim() || add.isPending} className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-40">Add</button>
      </form>

      <section className={`${panel} rise overflow-hidden`} style={{ ["--i" as string]: 1 }}>
        {isLoading && <div className="space-y-3 p-4">{Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-5 w-3/4" />)}</div>}
        {!isLoading && open.length === 0 && (
          <div className="px-6 py-12 text-center">
            <Sparkles className="mx-auto mb-2 h-6 w-6 text-indigo-300" aria-hidden="true" />
            <p className="text-sm font-medium text-stone-700 dark:text-stone-100">Nothing on the list.</p>
            <p className="mt-1 text-xs text-stone-400">Type the next thing above. It stays here until you tick it.</p>
          </div>
        )}
        <ul className="divide-y divide-stone-100 dark:divide-stone-800">
          {open.map((t, i) => <Row key={t.id} t={t} active={i === cursor} editing={editing === t.id} onFocus={() => setCursor(i)} onEdit={() => setEditing(t.id)} onSave={(text) => { setEditing(null); if (text.trim() && text.trim() !== t.text) edit.mutate({ id: t.id, text: text.trim() }); }} onToggle={() => toggle.mutate({ id: t.id, done: true })} onRemove={() => remove.mutate(t.id)} />)}
        </ul>
      </section>

      {done.length > 0 && (
        <section className="rise mt-5" style={{ ["--i" as string]: 2 }}>
          <div className="mb-2 flex items-center justify-between px-1">
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-stone-400">Done · {done.length}</p>
            <button type="button" onClick={() => clearDone.mutate()} className="inline-flex items-center gap-1 text-xs text-stone-400 hover:text-red-500"><Trash2 className="h-3 w-3" aria-hidden="true" />Clear done</button>
          </div>
          <ul className={`${panel} divide-y divide-stone-100 overflow-hidden dark:divide-stone-800`}>
            {done.map((t) => <Row key={t.id} t={t} active={false} editing={false} onFocus={() => undefined} onEdit={() => undefined} onSave={() => undefined} onToggle={() => toggle.mutate({ id: t.id, done: false })} onRemove={() => remove.mutate(t.id)} />)}
          </ul>
        </section>
      )}
      <p className="mt-6 text-center text-xs text-stone-400">j/k move · space ticks · e edits · x deletes · ⌥↑/↓ reorders · n new. Also from Claude Code: “add ‘book the scanner’ to my list”.</p>
    </div>
  );
}

function age(iso: string): string | null {
  const days = Math.floor((Date.now() - new Date(iso).getTime()) / 86_400_000);
  if (days <= 0) return null;
  if (days === 1) return "since yesterday";
  if (days < 7) return `since ${new Date(iso).toLocaleDateString(undefined, { weekday: "short" })}`;
  return `${days} days old`;
}

function Row({ t, active, editing, onFocus, onEdit, onSave, onToggle, onRemove }: { t: Todo; active: boolean; editing: boolean; onFocus: () => void; onEdit: () => void; onSave: (text: string) => void; onToggle: () => void; onRemove: () => void }) {
  const [draft, setDraft] = useState(t.text);
  useEffect(() => { if (editing) setDraft(t.text); }, [editing, t.text]);
  const old = t.done ? null : age(t.created_at);
  return (
    <li className={`group flex items-center gap-3 px-4 py-3 transition-colors ${active ? "bg-indigo-500/5 dark:bg-indigo-500/10" : ""}`} onMouseEnter={onFocus} data-active={active ? "1" : undefined}>
      <button
        type="button"
        onClick={onToggle}
        aria-label={t.done ? `Mark “${t.text}” not done` : `Mark “${t.text}” done`}
        className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full border-2 transition-all ${
          t.done ? "border-indigo-500 bg-indigo-500 text-white shadow-[0_0_10px_rgba(139,124,255,0.7)]" : "border-stone-300 hover:border-indigo-400 dark:border-stone-600"
        }`}
      >
        {t.done && <Check className="h-3.5 w-3.5" aria-hidden="true" strokeWidth={3} />}
      </button>
      {editing ? (
        <input autoFocus value={draft} onChange={(e) => setDraft(e.target.value)} onBlur={() => onSave(draft)} onKeyDown={(e) => { if (e.key === "Enter") onSave(draft); if (e.key === "Escape") onSave(t.text); }} maxLength={300} className="min-w-0 flex-1 rounded-md border border-indigo-300 bg-white px-2 py-1 text-base dark:border-indigo-500/50 dark:bg-stone-800 dark:text-stone-100" aria-label="Edit item" />
      ) : (
        <span onDoubleClick={t.done ? undefined : onEdit} className={`min-w-0 flex-1 text-base transition-colors ${t.done ? "text-stone-400 line-through" : "text-stone-800 dark:text-stone-100"}`}>{t.text}</span>
      )}
      {old && <span className="shrink-0 rounded-full bg-amber-500/10 px-2 py-0.5 text-[10px] text-amber-700 dark:text-amber-300" title="Carried over from an earlier day">{old}</span>}
      {t.project && <Link to={`/projects/${t.project}`} className="shrink-0 rounded-full bg-stone-100 px-2 py-0.5 text-[10px] text-stone-500 hover:text-indigo-600 dark:bg-stone-800 dark:text-stone-300 dark:hover:text-indigo-300">{t.project}</Link>}
      {!t.done && !editing && <button type="button" onClick={onEdit} aria-label="Edit" className="shrink-0 text-stone-300 opacity-0 transition-opacity hover:text-indigo-500 group-hover:opacity-100 dark:text-stone-600"><Pencil className="h-3.5 w-3.5" aria-hidden="true" /></button>}
      <button type="button" onClick={onRemove} aria-label="Delete" className="shrink-0 text-stone-300 opacity-0 transition-opacity hover:text-red-500 group-hover:opacity-100 dark:text-stone-600"><Trash2 className="h-3.5 w-3.5" aria-hidden="true" /></button>
    </li>
  );
}
