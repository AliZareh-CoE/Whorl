/** Today — the owner's plain to-do list (owner request, 2026-09-06). One list, one input,
 *  one click to tick. Nothing is lost overnight: open items simply stay. #546: an item for a
 *  later day ("review the draft on Friday", or snoozed with `s`) waits in Later, out of the way,
 *  and joins the list on its morning. #570: a deleted item waits thirty days in the Trash —
 *  the undo restores the very row (its stamp, its rule, its place), and the Trash section at
 *  the bottom restores or deletes for good. */
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Check, Pencil, Plus, Sparkles, Trash2, GripVertical, Moon, Sun, Repeat as RepeatIcon, BookOpen, ChevronRight } from "lucide-react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { dayLabel, dueState, formatDue, isLater, parseDue, relativeDue, repeatLabel } from "../dueTime";
import type { Repeat } from "../dueTime";
import { ErrorState } from "../../components/ErrorState";
import { showUndo, undoLast } from "../../components/UndoToast";
import { confirmDialog } from "../../components/Dialog";
import { Skeleton } from "../../components/Skeleton";

type Todo = { id: number; text: string; done: boolean; done_at: string | null; position: number; due_at: string | null; all_day: boolean; repeat: Repeat; project: string | null; created_at: string; deleted_at?: string | null; next?: { id: number; due_at: string } | null };
type Page<T> = { count: number; next?: string | null; results: T[] };

const panel = "rounded-2xl border border-stone-200 bg-white dark:border-stone-800 dark:bg-stone-900";

export default function Today() {
  const queryClient = useQueryClient();
  const [text, setText] = useState("");
  const inputRef = useRef<HTMLInputElement>(null);
  // #571: one fetch for what the page shows above the Logbook (open items + today's ticks);
  // the Logbook and the Trash page separately, so a long record can never crowd the live rows
  const { data, isLoading, error, refetch } = useQuery({ queryKey: ["todos", "current"], queryFn: () => api<Page<Todo>>("/todos/?when=current&page_size=500") });
  const refresh = () => { void queryClient.invalidateQueries({ queryKey: ["todos"] }); void queryClient.invalidateQueries({ queryKey: ["todos-trash"] }); };
  // #570: the Trash — deleted items, newest first, restorable for thirty days
  const trashQuery = useQuery({ queryKey: ["todos-trash"], queryFn: () => api<Page<Todo>>("/todos/?trash=true&page_size=200") });
  // #571: the Logbook is paged — every earlier tick is kept, fifty at a time, newest first
  const logbookQuery = useInfiniteQuery({
    queryKey: ["todos", "logbook"],
    queryFn: ({ pageParam }) => api<Page<Todo>>(`/todos/?when=logbook&page=${pageParam}`),
    initialPageParam: 1,
    getNextPageParam: (last, pages) => (last.next ? pages.length + 1 : undefined),
  });
  const add = useMutation({
    mutationFn: (t: string) => api<Todo>("/todos/", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(parseDue(t)) }), // #431: "at 3pm" → due_at
    onSuccess: () => { setText(""); refresh(); inputRef.current?.focus(); },
  });
  const toggle = useMutation({
    mutationFn: ({ id, done }: { id: number; done: boolean }) => api<Todo>(`/todos/${id}/`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ done }) }),
    onMutate: async ({ id, done }) => {
      await queryClient.cancelQueries({ queryKey: ["todos", "current"] });
      const prev = queryClient.getQueryData<Page<Todo>>(["todos", "current"]);
      if (prev) queryClient.setQueryData<Page<Todo>>(["todos", "current"], { ...prev, results: prev.results.map((t) => (t.id === id ? { ...t, done } : t)) });
      return { prev };
    },
    onError: (_e, _v, ctx) => { if (ctx?.prev) queryClient.setQueryData(["todos", "current"], ctx.prev); },
    onSuccess: (row, { id, done }) => { // #549: a tick can be taken back with one key
      if (!done) return;
      const nxt = row.next ? ` · next one ${dayLabel(row.next.due_at)}` : "";
      showUndo(`Done — “${row.text.slice(0, 50)}”${nxt}`, async () => { await api(`/todos/${id}/`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ done: false }) }); refresh(); });
    },
    onSettled: refresh,
  });
  // #549 → #570: delete moves the row to the Trash; the undo restores that very row — its done
  // stamp, its rule and its chain, its place in the list — and so does the Trash section later.
  const remove = useMutation({
    mutationFn: (id: number) => api(`/todos/${id}/`, { method: "DELETE" }),
    onMutate: (id) => ({ gone: (queryClient.getQueryData<Page<Todo>>(["todos", "current"])?.results ?? []).find((t) => t.id === id) ?? null }),
    onSuccess: (_r, id, ctx) => {
      refresh();
      const gone = ctx?.gone;
      if (!gone) return;
      showUndo(`Deleted — “${gone.text.slice(0, 50)}” · in the Trash for 30 days`, async () => { await api(`/todos/${id}/restore/`, { method: "POST" }); refresh(); });
    },
  });
  const restore = useMutation({ mutationFn: (id: number) => api<Todo>(`/todos/${id}/restore/`, { method: "POST" }), onSuccess: refresh });
  const forever = useMutation({ mutationFn: (id: number) => api(`/todos/${id}/?forever=true`, { method: "DELETE" }), onSuccess: refresh });
  const emptyTrash = useMutation({ mutationFn: () => api("/todos/empty-trash/", { method: "POST" }), onSuccess: refresh });
  const edit = useMutation({ mutationFn: ({ id, text: t }: { id: number; text: string }) => { const { repeat, ...p } = parseDue(t); const body = { ...(p.due_at ? p : { text: p.text }), ...(repeat ? { repeat } : {}) }; return api<Todo>(`/todos/${id}/`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }); }, onSuccess: refresh }); // an edit without "every …" keeps the item's rule
  // #547: "every Monday" — the rule lives on the item; ticking it spawns the next occurrence
  const setRepeat = useMutation({
    mutationFn: ({ id, repeat }: { id: number; repeat: Repeat }) => api<Todo>(`/todos/${id}/`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ repeat }) }),
    onSuccess: () => { setSnoozing(null); refresh(); },
  });
  // #546: "not today" — the item moves to a later day (tomorrow / Monday / next week / weekend /
  // a date) and waits in Later; "" brings it back. A timed item keeps its clock time.
  const snooze = useMutation({
    mutationFn: ({ id, until }: { id: number; until: string }) => api<Todo>(`/todos/${id}/snooze/`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ until }) }),
    onMutate: ({ id }) => { const before = (queryClient.getQueryData<Page<Todo>>(["todos", "current"])?.results ?? []).find((t) => t.id === id); return { before: before ? { due_at: before.due_at, all_day: before.all_day } : null }; },
    onSuccess: (row, { id, until }, ctx) => {
      setSnoozing(null); refresh();
      if (!ctx?.before) return;
      const before = ctx.before; // #549: undo puts the exact previous day back, not "today"
      showUndo(until ? `Pushed to ${row.due_at ? dayLabel(row.due_at) : "later"} — “${row.text.slice(0, 50)}”` : `Back on today's list — “${row.text.slice(0, 50)}”`, async () => { await api(`/todos/${id}/`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(before) }); refresh(); });
    },
  });
  const [snoozing, setSnoozing] = useState<number | null>(null);
  // Reorder (#383): one call carries the whole open-list order — the keyboard (⌥↑/↓) and a
  // drag both go through it, with the list updated optimistically so nothing jumps back.
  const reorder = useMutation({
    mutationFn: (ids: number[]) => api("/todos/reorder/", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ids }) }),
    onMutate: async (ids) => {
      await queryClient.cancelQueries({ queryKey: ["todos", "current"] });
      const prev = queryClient.getQueryData<Page<Todo>>(["todos", "current"]);
      if (prev) {
        const rank = new Map(ids.map((id, i) => [id, i + 1]));
        const results = [...prev.results].map((t) => ({ ...t, position: rank.get(t.id) ?? t.position + ids.length })).sort((x, y) => Number(x.done) - Number(y.done) || x.position - y.position || x.id - y.id);
        queryClient.setQueryData<Page<Todo>>(["todos", "current"], { ...prev, results });
      }
      return { prev };
    },
    onError: (_e, _v, ctx) => { if (ctx?.prev) queryClient.setQueryData(["todos", "current"], ctx.prev); },
    onSettled: refresh,
  });
  const moveOpen = (from: number, to: number) => {
    if (from === to || from < 0 || to < 0 || from >= open.length || to >= open.length) return;
    const ids = open.map((t) => t.id);
    const [id] = ids.splice(from, 1);
    ids.splice(to, 0, id);
    reorder.mutate(ids);
  };
  const [drag, setDrag] = useState<{ id: number; over: number | null; after: boolean }>({ id: -1, over: null, after: false });
  const [cursor, setCursor] = useState(0);
  const [editing, setEditing] = useState<number | null>(null);
  // #550: Clear empties the Logbook (earlier days) and keeps today's record
  const clearDone = useMutation({ mutationFn: () => api("/todos/clear-done/", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ scope: "earlier" }) }), onSuccess: refresh });
  const [logbookOpen, setLogbookOpen] = useState<boolean>(() => { try { return localStorage.getItem("atlas-today-logbook") === "open"; } catch { return false; } });
  const toggleLogbook = () => setLogbookOpen((o) => { try { localStorage.setItem("atlas-today-logbook", o ? "closed" : "open"); } catch { /* private mode */ } return !o; });
  const [trashOpen, setTrashOpen] = useState<boolean>(() => { try { return localStorage.getItem("atlas-today-trash") === "open"; } catch { return false; } });
  const toggleTrash = () => setTrashOpen((o) => { try { localStorage.setItem("atlas-today-trash", o ? "closed" : "open"); } catch { /* private mode */ } return !o; });
  const trash = trashQuery.data?.results ?? [];
  const askEmptyTrash = async () => {
    if (await confirmDialog({ title: "Empty the trash?", body: `${trash.length} deleted ${trash.length === 1 ? "item goes" : "items go"} for good. The sweep would do it after thirty days anyway.`, danger: true, confirmLabel: "Empty the trash" })) emptyTrash.mutate();
  };
  const askForever = async (t: Todo) => {
    if (await confirmDialog({ title: `Delete “${t.text.slice(0, 60)}” for good?`, body: "It leaves the Trash and cannot be restored.", danger: true, confirmLabel: "Delete forever" })) forever.mutate(t.id);
  };

  useEffect(() => { inputRef.current?.focus(); }, []);

  const items = data?.results ?? [];
  const open = items.filter((t) => !t.done && !isLater(t.due_at));
  const later = items.filter((t) => !t.done && isLater(t.due_at)).sort((a, b) => String(a.due_at).localeCompare(String(b.due_at)) || a.position - b.position);
  const done = items.filter((t) => t.done);
  // #550: today's ticks stay in view; earlier days (and rows without a stamp, re-created by an undo) fold into the Logbook
  const doneToday = done.filter((t) => t.done_at && dayLabel(t.done_at) === "today");
  // #571: the Logbook comes paged from the server (when=logbook — earlier days, newest first);
  // a tick the server files under today but this browser's day does not joins it up front
  const doneOther = done.filter((t) => !(t.done_at && dayLabel(t.done_at) === "today"));
  const logPages = logbookQuery.data?.pages ?? [];
  const logLoaded = logPages.flatMap((p) => p.results);
  const logSeen = new Set<number>();
  const logbook = [...doneOther, ...logLoaded].filter((t) => !logSeen.has(t.id) && !!logSeen.add(t.id)).sort((a, b) => (b.done_at ?? "").localeCompare(a.done_at ?? ""));
  const logTotal = (logPages[0]?.count ?? 0) + doneOther.length;
  const logRemaining = Math.max(0, logTotal - logbook.length);
  const logGroups = logbook.reduce<{ label: string; items: Todo[] }[]>((acc, t) => {
    const label = t.done_at ? dayLabel(t.done_at) : "earlier";
    const last = acc[acc.length - 1];
    if (last && last.label === label) last.items.push(t); else acc.push({ label, items: [t] });
    return acc;
  }, []);
  const oldest = logbookQuery.hasNextPage ? null : ([...logbook].reverse().find((t) => t.done_at)?.done_at ?? null); // "since …" only once the whole record is in (the oldest stamped row)
  const laterGroups = later.reduce<{ label: string; items: Todo[] }[]>((acc, t) => {
    const label = dayLabel(t.due_at as string);
    const last = acc[acc.length - 1];
    if (last && last.label === label) last.items.push(t); else acc.push({ label, items: [t] });
    return acc;
  }, []);
  const today = new Date().toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" });
  const carried = open.filter((t) => !t.due_at && age(t.created_at)).length; // #431: "2 carried over" — a dated item is planned, not carried (#546)
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement | null)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || editing !== null || snoozing !== null) return;
      const t = open[cursor];
      if (e.key === "j" || e.key === "ArrowDown") { if (e.altKey && t && cursor < open.length - 1) { e.preventDefault(); moveOpen(cursor, cursor + 1); setCursor((i) => i + 1); return; } e.preventDefault(); setCursor((i) => Math.min(open.length - 1, i + 1)); }
      else if (e.key === "k" || e.key === "ArrowUp") { if (e.altKey && t && cursor > 0) { e.preventDefault(); moveOpen(cursor, cursor - 1); setCursor((i) => i - 1); return; } e.preventDefault(); setCursor((i) => Math.max(0, i - 1)); }
      else if (e.key === "z") { e.preventDefault(); undoLast(); } // #549: take the last action back (works on an empty list too)
      else if (!t) return;
      else if (e.key === " " || e.key === "Enter") { e.preventDefault(); toggle.mutate({ id: t.id, done: true }); }
      else if (e.key === "e") { e.preventDefault(); setEditing(t.id); }
      else if (e.key === "x" || e.key === "Delete") { e.preventDefault(); remove.mutate(t.id); }
      else if (e.key === "s") { e.preventDefault(); snooze.mutate({ id: t.id, until: "tomorrow" }); } // #546: not today
      else if (e.key === "S") { e.preventDefault(); setSnoozing(t.id); }
      else if (e.key === "n" || e.key === "/") { e.preventDefault(); inputRef.current?.focus(); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, cursor, editing, snoozing]);
  // the error return sits BELOW every hook on purpose (React #310 otherwise — see test_hook_order)
  if (error) return <ErrorState message="Couldn't load your list." onRetry={() => refetch()} />;

  return (
    <div className="@container mx-auto max-w-2xl">
      <div className="mb-5">
        <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-stone-400">{today}</p>
        <h1 className="font-display mt-1 text-3xl font-bold tracking-tight dark:text-stone-100">
          Today{" "}
          <span className="text-gradient">{open.length === 0 ? "· all clear" : `· ${open.length} to do`}</span>
        </h1>
        {(carried > 0 || doneToday.length > 0) && <p className="mt-1 text-xs text-stone-400">{carried > 0 && <span data-testid="carried-over">{carried} carried over from earlier days.</span>}{carried > 0 && doneToday.length > 0 && " · "}{doneToday.length > 0 && <span data-testid="done-today-count">{doneToday.length} done today.</span>}</p>}
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
          placeholder="What needs doing? “at 3pm” sets a time, “on Friday” a day."
          maxLength={300}
          className="min-w-0 flex-1 bg-transparent py-2 text-base placeholder:text-stone-400 focus:outline-none dark:text-stone-100"
        />
        <button type="submit" disabled={!text.trim() || add.isPending} className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-40">Add</button>
      </form>

      <section className={`${panel} rise relative z-[3]`} style={{ ["--i" as string]: 1 }}>
        {isLoading && <div className="space-y-3 p-4">{Array.from({ length: 4 }).map((_, i) => <Skeleton key={i} className="h-5 w-3/4" />)}</div>}
        {!isLoading && open.length === 0 && (
          <div className="px-6 py-12 text-center">
            <Sparkles className="mx-auto mb-2 h-6 w-6 text-indigo-300" aria-hidden="true" />
            <p className="text-sm font-medium text-stone-700 dark:text-stone-100">Nothing on the list.</p>
            <p className="mt-1 text-xs text-stone-400">Type the next thing above. It stays here until you tick it.</p>
          </div>
        )}
        <ul className="divide-y divide-stone-100 dark:divide-stone-800">
          {open.map((t, i) => <Row key={t.id} t={t} active={i === cursor} editing={editing === t.id} onFocus={() => setCursor(i)} onEdit={() => setEditing(t.id)} onSave={(text) => { setEditing(null); if (text.trim() && text.trim() !== t.text) edit.mutate({ id: t.id, text: text.trim() }); }} onToggle={() => toggle.mutate({ id: t.id, done: true })} onRemove={() => remove.mutate(t.id)}
            snoozing={snoozing === t.id} onSnoozeMenu={(on) => setSnoozing(on ? t.id : null)} onSnooze={(until) => snooze.mutate({ id: t.id, until })} onRepeat={(repeat) => setRepeat.mutate({ id: t.id, repeat })}
            drag={{
              dragging: drag.id === t.id,
              over: drag.over === i ? (drag.after ? "after" : "before") : null,
              onStart: (e) => { e.dataTransfer.effectAllowed = "move"; e.dataTransfer.setData("text/plain", String(t.id)); setDrag({ id: t.id, over: null, after: false }); },
              onOver: (e) => { if (drag.id < 0) return; e.preventDefault(); e.dataTransfer.dropEffect = "move"; const r = e.currentTarget.getBoundingClientRect(); const after = e.clientY > r.top + r.height / 2; if (drag.over !== i || drag.after !== after) setDrag((d) => ({ ...d, over: i, after })); },
              onDrop: (e) => { e.preventDefault(); const from = open.findIndex((o) => o.id === drag.id); if (from < 0) return; let to = i + (drag.after ? 1 : 0); if (from < to) to -= 1; moveOpen(from, to); setCursor(to); setDrag({ id: -1, over: null, after: false }); },
              onEnd: () => setDrag({ id: -1, over: null, after: false }),
            }} />)}
        </ul>
      </section>

      {later.length > 0 && (
        <section className="rise relative z-[2] mt-5" style={{ ["--i" as string]: 2 }} data-testid="later-section">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-x-3 gap-y-1 px-1">
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-stone-400"><Moon className="mr-1 inline h-3 w-3 -translate-y-px" aria-hidden="true" />Later · {later.length}</p>
            <p className="text-[11px] text-stone-400">each joins the list on its day</p>
          </div>
          <div className={panel}>
            {laterGroups.map((g, i) => (
              <div key={g.label} data-testid="later-group">
                <p className={`border-b border-stone-100 bg-stone-50/60 px-4 py-1.5 ${i === 0 ? "rounded-t-2xl" : ""} text-[11px] font-medium capitalize text-stone-500 dark:border-stone-800 dark:bg-stone-800/40 dark:text-stone-400`} data-testid="later-day">{g.label}</p>
                <ul className="divide-y divide-stone-100 dark:divide-stone-800">
                  {g.items.map((t) => <LaterRow key={t.id} t={t} snoozing={snoozing === t.id} onSnoozeMenu={(on) => setSnoozing(on ? t.id : null)} onSnooze={(until) => snooze.mutate({ id: t.id, until })} onRepeat={(repeat) => setRepeat.mutate({ id: t.id, repeat })} onToggle={() => toggle.mutate({ id: t.id, done: true })} onRemove={() => remove.mutate(t.id)} />)}
                </ul>
              </div>
            ))}
          </div>
        </section>
      )}

      {doneToday.length > 0 && (
        <section className="rise relative z-[1] mt-5" style={{ ["--i" as string]: 3 }} data-testid="done-today">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-x-3 gap-y-1 px-1">
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-stone-400">Done today · {doneToday.length}</p>
          </div>
          <ul className={`${panel} divide-y divide-stone-100 overflow-hidden dark:divide-stone-800`}>
            {doneToday.map((t) => <Row key={t.id} t={t} active={false} editing={false} onFocus={() => undefined} onEdit={() => undefined} onSave={() => undefined} onToggle={() => toggle.mutate({ id: t.id, done: false })} onRemove={() => remove.mutate(t.id)} />)}
          </ul>
        </section>
      )}

      {logbook.length > 0 && (
        <section className="rise mt-5" style={{ ["--i" as string]: 4 }} data-testid="logbook">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-x-3 gap-y-1 px-1">
            <button type="button" onClick={toggleLogbook} aria-expanded={logbookOpen} data-testid="logbook-toggle" className="inline-flex items-center gap-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-stone-400 hover:text-stone-600 dark:hover:text-stone-200">
              <ChevronRight className={`h-3 w-3 transition-transform ${logbookOpen ? "rotate-90" : ""}`} aria-hidden="true" /><BookOpen className="h-3 w-3" aria-hidden="true" />Logbook · {logTotal}{oldest && <span className="ml-1 font-normal normal-case tracking-normal">· since {dayLabel(oldest)}</span>}
            </button>
            <button type="button" onClick={() => clearDone.mutate()} data-testid="clear-logbook" className="inline-flex items-center gap-1 text-xs text-stone-400 hover:text-red-500"><Trash2 className="h-3 w-3" aria-hidden="true" />Clear the logbook</button>
          </div>
          {logbookOpen && (
            <div className={`${panel} overflow-hidden`}>
              {logGroups.map((g) => (
                <div key={g.label} data-testid="logbook-group">
                  <p className="border-b border-stone-100 bg-stone-50/60 px-4 py-1.5 text-[11px] font-medium capitalize text-stone-500 dark:border-stone-800 dark:bg-stone-800/40 dark:text-stone-400" data-testid="logbook-day">{g.label}</p>
                  <ul className="divide-y divide-stone-100 dark:divide-stone-800">
                    {g.items.map((t) => <LogRow key={t.id} t={t} onToggle={() => toggle.mutate({ id: t.id, done: false })} onRemove={() => remove.mutate(t.id)} />)}
                  </ul>
                </div>
              ))}
              {logbookQuery.hasNextPage && (
                <button type="button" onClick={() => void logbookQuery.fetchNextPage()} disabled={logbookQuery.isFetchingNextPage} data-testid="logbook-more" className="flex w-full items-center justify-center gap-1 border-t border-stone-100 px-4 py-2 text-xs text-stone-400 transition-colors hover:text-indigo-600 disabled:opacity-60 dark:border-stone-800 dark:hover:text-indigo-300">
                  {logbookQuery.isFetchingNextPage ? "Loading…" : `Show older · ${logRemaining} more`}
                </button>
              )}
            </div>
          )}
        </section>
      )}
      {trash.length > 0 && (
        <section className="rise mt-5" style={{ ["--i" as string]: 5 }} data-testid="trash">
          <div className="mb-2 flex flex-wrap items-center justify-between gap-x-3 gap-y-1 px-1">
            <button type="button" onClick={toggleTrash} aria-expanded={trashOpen} data-testid="trash-toggle" className="inline-flex items-center gap-1 text-[11px] font-semibold uppercase tracking-[0.14em] text-stone-400 hover:text-stone-600 dark:hover:text-stone-200">
              <ChevronRight className={`h-3 w-3 transition-transform ${trashOpen ? "rotate-90" : ""}`} aria-hidden="true" /><Trash2 className="h-3 w-3" aria-hidden="true" />Trash · {trash.length}<span className="ml-1 font-normal normal-case tracking-normal">· kept 30 days</span>
            </button>
            <button type="button" onClick={() => void askEmptyTrash()} data-testid="empty-trash" className="inline-flex items-center gap-1 text-xs text-stone-400 hover:text-red-500">Empty the trash</button>
          </div>
          {trashOpen && (
            <ul className={`${panel} divide-y divide-stone-100 overflow-hidden dark:divide-stone-800`}>
              {trash.map((t) => <TrashRow key={t.id} t={t} onRestore={() => restore.mutate(t.id)} onForever={() => void askForever(t)} />)}
            </ul>
          )}
        </section>
      )}
      <p className="mt-6 text-center text-xs text-stone-400">j/k move · space ticks · e edits · x deletes (30 days in the Trash) · s pushes to tomorrow, S picks a day · z undoes · ⌥↑/↓ or drag reorders · n new · “at 3pm” sets a time, “on Friday” a day, “every Monday” a rule. Also from Claude Code: “add ‘book the scanner’ to my list”.</p>
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

/** #546: an all-day item due today wears no chip on today's list — the list is today. */
function showsDue(iso: string, allDay: boolean): boolean {
  return !allDay || (!isLater(iso) && dayLabel(iso) !== "today");
}

/** #431: the time chip — quiet when far off, amber within two hours, red once it has passed. */
function DueChip({ iso, allDay }: { iso: string; allDay: boolean }) {
  if (allDay) { // #546: a day-only item on today's list is either today's (no chip — the list is today) or a day late
    const late = showsDue(iso, allDay);
    if (!late) return null;
    return <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] capitalize ${late ? "bg-red-500/10 text-red-600 dark:text-red-300" : "bg-stone-100 text-stone-500 dark:bg-stone-800 dark:text-stone-300"}`} data-testid="due-chip" data-state={late ? "overdue" : "today"} title={late ? "Planned for an earlier day" : "Planned for today"}>{dayLabel(iso)}</span>;
  }
  const state = dueState(iso);
  const cls = state === "overdue" ? "bg-red-500/10 text-red-600 dark:text-red-300" : state === "soon" ? "bg-amber-500/10 text-amber-700 dark:text-amber-300" : "bg-stone-100 text-stone-500 dark:bg-stone-800 dark:text-stone-300";
  return <span className={`shrink-0 rounded-full px-2 py-0.5 text-[10px] tabular-nums ${cls}`} data-testid="due-chip" data-state={state} title={relativeDue(iso)}>{formatDue(iso)}{state === "overdue" ? " · overdue" : state === "soon" ? ` · ${relativeDue(iso)}` : ""}</span>;
}

const SNOOZE_OPTIONS: [string, string][] = [["tomorrow", "Tomorrow"], ["monday", "Monday"], ["next-week", "Next week"], ["weekend", "Weekend"]];
const REPEAT_OPTIONS: [Repeat, string][] = [["", "Never"], ["daily", "Daily"], ["weekdays", "Weekdays"], ["weekly", "Weekly"], ["monthly", "Monthly"]];

/** #550: a Logbook row — a quiet record of an earlier day. A repeating row keeps no untick here:
 *  unticking it would take back the occurrence it spawned (the #547 rule), which is a surprise
 *  a week later; today's Done section is where that undo belongs. */
function LogRow({ t, onToggle, onRemove }: { t: Todo; onToggle: () => void; onRemove: () => void }) {
  const canUntick = !t.repeat;
  return (
    <li className="group flex flex-wrap items-center gap-x-3 gap-y-1 px-4 py-2" data-testid="logbook-row">
      {canUntick ? (
        <button type="button" onClick={onToggle} aria-label={`Mark “${t.text}” not done`} className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full border-2 border-indigo-500/60 bg-indigo-500/60 text-white transition-all hover:bg-indigo-500"><Check className="h-3 w-3" aria-hidden="true" strokeWidth={3} /></button>
      ) : (
        <span title="Ticking this one spawned the next occurrence — untick it from today's Done, not from the logbook" data-testid="logbook-locked" className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full border-2 border-indigo-500/40 bg-indigo-500/40 text-white"><Check className="h-3 w-3" aria-hidden="true" strokeWidth={3} /></span>
      )}
      <span className="min-w-0 @lg:min-w-[13rem] flex-1 text-sm text-stone-400 line-through dark:text-stone-500" data-testid="todo-text">{t.text}</span>
      <button type="button" onClick={onRemove} aria-label="Delete" className="shrink-0 text-stone-300 opacity-0 transition-opacity pointer-coarse:opacity-100 hover:text-red-500 group-hover:opacity-100 dark:text-stone-600"><Trash2 className="h-3.5 w-3.5" aria-hidden="true" /></button>
      {(t.repeat || t.project || t.done_at) && <span className="order-last flex min-w-0 basis-full flex-wrap items-center gap-1 @lg:order-none @lg:basis-auto pl-8" data-testid="todo-meta">
        <RepeatChip t={t} />
        {t.project && <Link to={`/projects/${t.project}`} className="shrink-0 rounded-full bg-stone-100 px-2 py-0.5 text-[10px] text-stone-500 hover:text-indigo-600 dark:bg-stone-800 dark:text-stone-300 dark:hover:text-indigo-300">{t.project}</Link>}
        {t.done_at && <span className="shrink-0 text-[10px] tabular-nums text-stone-400">{new Date(t.done_at).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })}</span>}
      </span>}
    </li>
  );
}

/** #570: a row in the Trash — muted, with the day it was deleted; Restore puts it back exactly
 *  as it was, the bin deletes it for good (after a confirm). */
function TrashRow({ t, onRestore, onForever }: { t: Todo; onRestore: () => void; onForever: () => void }) {
  return (
    <li className="group flex flex-wrap items-center gap-x-3 gap-y-1 px-4 py-2" data-testid="trash-row">
      <Trash2 className="h-4 w-4 shrink-0 text-stone-300 dark:text-stone-600" aria-hidden="true" />
      <span className={`min-w-0 @lg:min-w-[13rem] flex-1 text-sm text-stone-500 dark:text-stone-400 ${t.done ? "line-through" : ""}`} data-testid="todo-text">{t.text}</span>
      <span className="flex shrink-0 items-center gap-2" data-testid="todo-actions">
        <button type="button" onClick={onRestore} data-testid="trash-restore" className="rounded-lg border border-stone-200 px-2 py-0.5 text-xs text-stone-600 hover:border-indigo-300 hover:text-indigo-600 dark:border-stone-700 dark:text-stone-300 dark:hover:text-indigo-300">Restore</button>
        <button type="button" onClick={onForever} data-testid="trash-forever" aria-label="Delete forever" title="Delete forever" className="shrink-0 text-stone-300 hover:text-red-500 dark:text-stone-600"><Trash2 className="h-3.5 w-3.5" aria-hidden="true" /></button>
      </span>
      {(t.deleted_at || t.project || t.repeat) && <span className="order-last flex min-w-0 basis-full flex-wrap items-center gap-1 @lg:order-none @lg:basis-auto pl-7" data-testid="todo-meta">
        <RepeatChip t={t} />
        {t.deleted_at && <span className="shrink-0 text-[10px] text-stone-400" data-testid="trash-when">deleted {dayLabel(t.deleted_at)}</span>}
        {t.project && <span className="shrink-0 rounded-full bg-stone-100 px-2 py-0.5 text-[10px] text-stone-500 dark:bg-stone-800 dark:text-stone-300">{t.project}</span>}
      </span>}
    </li>
  );
}

/** #547: the "↻ every Monday" chip on a repeating row. */
function RepeatChip({ t }: { t: Todo }) {
  if (!t.repeat) return null;
  return <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-indigo-500/10 px-2 py-0.5 text-[10px] text-indigo-600 dark:text-indigo-300" data-testid="repeat-chip" data-repeat={t.repeat} title="Ticking it puts the next one in Later"><RepeatIcon className="h-2.5 w-2.5" aria-hidden="true" />{repeatLabel(t.repeat, t.due_at)}</span>;
}

/** #546: the "not today" menu — four quick days and a date picker; on a Later row also "Today". */
function SnoozeMenu({ onPick, onClose, later, repeat, onRepeat }: { onPick: (until: string) => void; onClose: () => void; later?: boolean; repeat?: Repeat; onRepeat?: (r: Repeat) => void }) {
  const ref = useRef<HTMLDivElement>(null);
  useEffect(() => {
    const away = (e: MouseEvent) => { if (ref.current && !ref.current.contains(e.target as Node)) onClose(); };
    const esc = (e: KeyboardEvent) => { if (e.key === "Escape") { e.stopPropagation(); onClose(); } };
    document.addEventListener("mousedown", away);
    window.addEventListener("keydown", esc, true);
    return () => { document.removeEventListener("mousedown", away); window.removeEventListener("keydown", esc, true); };
  }, [onClose]);
  const min = new Date(); min.setDate(min.getDate() + 1);
  const minIso = `${min.getFullYear()}-${String(min.getMonth() + 1).padStart(2, "0")}-${String(min.getDate()).padStart(2, "0")}`; // local, not UTC
  return (
    <div ref={ref} data-testid="snooze-menu" className="absolute right-3 top-full z-20 mt-1 w-max max-w-[calc(100%-1.5rem)] rounded-xl border border-stone-200 bg-white p-1.5 shadow-lg dark:border-stone-700 dark:bg-stone-900" onClick={(e) => e.stopPropagation()}>
      <div className="flex flex-wrap items-center gap-1">
        <span className="px-1 text-[10px] uppercase tracking-wider text-stone-400">Day</span>
        {later && <button type="button" data-testid="snooze-option" onClick={() => onPick("")} className="rounded-lg px-2 py-1 text-xs font-medium text-indigo-600 hover:bg-indigo-500/10 dark:text-indigo-300">Today</button>}
        {SNOOZE_OPTIONS.map(([v, label]) => <button key={v} type="button" data-testid="snooze-option" data-until={v} onClick={() => onPick(v)} className="rounded-lg px-2 py-1 text-xs text-stone-700 hover:bg-stone-100 dark:text-stone-200 dark:hover:bg-stone-800">{label}</button>)}
        <input type="date" aria-label="Pick a day" data-testid="snooze-date" min={minIso} onChange={(e) => { if (e.target.value) onPick(e.target.value); }} className="rounded-lg border border-stone-200 bg-transparent px-1.5 py-0.5 text-xs text-stone-600 dark:border-stone-700 dark:text-stone-300" />
      </div>
      {onRepeat && (
        <div className="mt-1 flex flex-wrap items-center gap-1 border-t border-stone-100 pt-1 dark:border-stone-800" data-testid="repeat-row">
          <span className="px-1 text-[10px] uppercase tracking-wider text-stone-400">Repeat</span>
          {REPEAT_OPTIONS.map(([v, label]) => <button key={v || "never"} type="button" data-testid="repeat-option" data-repeat={v} onClick={() => onRepeat(v)} className={`rounded-lg px-2 py-1 text-xs ${(repeat ?? "") === v ? "bg-indigo-500/10 font-medium text-indigo-600 dark:text-indigo-300" : "text-stone-700 hover:bg-stone-100 dark:text-stone-200 dark:hover:bg-stone-800"}`}>{label}</button>)}
        </div>
      )}
    </div>
  );
}

/** #546: a row in Later — quieter than today's, with "Today" to bring it back. */
function LaterRow({ t, snoozing, onSnoozeMenu, onSnooze, onRepeat, onToggle, onRemove }: { t: Todo; snoozing: boolean; onSnoozeMenu: (on: boolean) => void; onSnooze: (until: string) => void; onRepeat: (r: Repeat) => void; onToggle: () => void; onRemove: () => void }) {
  return (
    <li className="group relative flex flex-wrap items-center gap-x-3 gap-y-1 px-4 py-2" data-testid="later-row">
      <button type="button" onClick={onToggle} aria-label={`Mark “${t.text}” done`} className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full border-2 border-stone-200 transition-all hover:border-indigo-400 dark:border-stone-700" />
      <span className="min-w-0 @lg:min-w-[13rem] flex-1 text-sm text-stone-600 dark:text-stone-300" data-testid="todo-text">{t.text}</span>
      <span className="flex shrink-0 items-center gap-3" data-testid="todo-actions">
        <button type="button" onClick={() => onSnooze("")} aria-label="Bring back to today" title="Today" data-testid="wake-button" className="shrink-0 text-stone-300 opacity-0 transition-opacity pointer-coarse:opacity-100 hover:text-amber-500 group-hover:opacity-100 dark:text-stone-600"><Sun className="h-3.5 w-3.5" aria-hidden="true" /></button>
        <button type="button" onClick={() => onSnoozeMenu(!snoozing)} aria-label="Another day" title="Another day" data-testid="snooze-button" className="shrink-0 text-stone-300 opacity-0 transition-opacity pointer-coarse:opacity-100 hover:text-indigo-500 group-hover:opacity-100 dark:text-stone-600"><Moon className="h-3.5 w-3.5" aria-hidden="true" /></button>
        <button type="button" onClick={onRemove} aria-label="Delete" className="shrink-0 text-stone-300 opacity-0 transition-opacity pointer-coarse:opacity-100 hover:text-red-500 group-hover:opacity-100 dark:text-stone-600"><Trash2 className="h-3.5 w-3.5" aria-hidden="true" /></button>
      </span>
      {(t.repeat || (!t.all_day && t.due_at) || t.project) && <span className="order-last flex min-w-0 basis-full flex-wrap items-center gap-1 @lg:order-none @lg:basis-auto pl-8" data-testid="todo-meta">
        <RepeatChip t={t} />
        {!t.all_day && t.due_at && <span className="shrink-0 rounded-full bg-stone-100 px-2 py-0.5 text-[10px] tabular-nums text-stone-500 dark:bg-stone-800 dark:text-stone-300" data-testid="later-time">{new Date(t.due_at).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })}</span>}
        {t.project && <Link to={`/projects/${t.project}`} className="shrink-0 rounded-full bg-stone-100 px-2 py-0.5 text-[10px] text-stone-500 hover:text-indigo-600 dark:bg-stone-800 dark:text-stone-300 dark:hover:text-indigo-300">{t.project}</Link>}
      </span>}
      {snoozing && <SnoozeMenu later onPick={onSnooze} onClose={() => onSnoozeMenu(false)} repeat={t.repeat} onRepeat={onRepeat} />}
    </li>
  );
}

type DragProps = { dragging: boolean; over: "before" | "after" | null; onStart: (e: React.DragEvent<HTMLLIElement>) => void; onOver: (e: React.DragEvent<HTMLLIElement>) => void; onDrop: (e: React.DragEvent<HTMLLIElement>) => void; onEnd: () => void };

function Row({ t, active, editing, onFocus, onEdit, onSave, onToggle, onRemove, drag, snoozing, onSnoozeMenu, onSnooze, onRepeat }: { t: Todo; active: boolean; editing: boolean; onFocus: () => void; onEdit: () => void; onSave: (text: string) => void; onToggle: () => void; onRemove: () => void; drag?: DragProps; snoozing?: boolean; onSnoozeMenu?: (on: boolean) => void; onSnooze?: (until: string) => void; onRepeat?: (r: Repeat) => void }) {
  const [draft, setDraft] = useState(t.text);
  useEffect(() => { if (editing) setDraft(t.text); }, [editing, t.text]);
  const old = t.done || t.due_at ? null : age(t.created_at); // #546: a dated item's chip is its day, never its age
  const meta = !!old || (!t.done && (!!t.repeat || (!!t.due_at && showsDue(t.due_at, t.all_day)))) || !!t.project; // #551: anything for the chip group
  return (
    <li className={`group relative flex flex-wrap items-center gap-x-3 gap-y-1 px-4 py-3 transition-colors first:rounded-t-2xl last:rounded-b-2xl ${active ? "bg-indigo-500/5 dark:bg-indigo-500/10" : ""} ${drag?.dragging ? "opacity-40" : ""}`} onMouseEnter={onFocus} data-active={active ? "1" : undefined} data-testid="todo-row"
        draggable={drag ? !editing : undefined} onDragStart={drag?.onStart} onDragOver={drag?.onOver} onDrop={drag?.onDrop} onDragEnd={drag?.onEnd}>
      {drag?.over && <span aria-hidden="true" className={`pointer-events-none absolute left-3 right-3 h-0.5 rounded-full bg-indigo-500 ${drag.over === "before" ? "top-0" : "bottom-0"}`} />}
      {drag && <span data-testid="drag-handle" title="Drag to reorder" className="-ml-1 shrink-0 cursor-grab text-stone-300 opacity-0 transition-opacity pointer-coarse:opacity-100 group-hover:opacity-100 active:cursor-grabbing dark:text-stone-600"><GripVertical className="h-4 w-4" aria-hidden="true" /></span>}
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
        <span onDoubleClick={t.done ? undefined : onEdit} className={`min-w-0 @lg:min-w-[13rem] flex-1 text-base transition-colors ${t.done ? "text-stone-400 line-through" : "text-stone-800 dark:text-stone-100"}`} data-testid="todo-text">{t.text}</span>
      )}
      <span className="flex shrink-0 items-center gap-3" data-testid="todo-actions">
        {!t.done && !editing && <button type="button" onClick={onEdit} aria-label="Edit" className="shrink-0 text-stone-300 opacity-0 transition-opacity pointer-coarse:opacity-100 hover:text-indigo-500 group-hover:opacity-100 dark:text-stone-600"><Pencil className="h-3.5 w-3.5" aria-hidden="true" /></button>}
        {!t.done && !editing && onSnoozeMenu && <button type="button" onClick={() => onSnoozeMenu(!snoozing)} aria-label="Not today" title="Not today — push to a later day (s: tomorrow)" data-testid="snooze-button" className="shrink-0 text-stone-300 opacity-0 transition-opacity pointer-coarse:opacity-100 hover:text-indigo-500 group-hover:opacity-100 dark:text-stone-600"><Moon className="h-3.5 w-3.5" aria-hidden="true" /></button>}
        <button type="button" onClick={onRemove} aria-label="Delete" className="shrink-0 text-stone-300 opacity-0 transition-opacity pointer-coarse:opacity-100 hover:text-red-500 group-hover:opacity-100 dark:text-stone-600"><Trash2 className="h-3.5 w-3.5" aria-hidden="true" /></button>
      </span>
      {meta && <span className={`order-last flex min-w-0 basis-full flex-wrap items-center gap-1 @lg:order-none @lg:basis-auto ${drag ? "pl-[3.75rem]" : "pl-9"}`} data-testid="todo-meta">
        {old && <span className="shrink-0 rounded-full bg-amber-500/10 px-2 py-0.5 text-[10px] text-amber-700 dark:text-amber-300" title="Carried over from an earlier day">{old}</span>}
        {!t.done && <RepeatChip t={t} />}
        {!t.done && t.due_at && <DueChip iso={t.due_at} allDay={t.all_day} />}
        {t.project && <Link to={`/projects/${t.project}`} className="shrink-0 rounded-full bg-stone-100 px-2 py-0.5 text-[10px] text-stone-500 hover:text-indigo-600 dark:bg-stone-800 dark:text-stone-300 dark:hover:text-indigo-300">{t.project}</Link>}
      </span>}
      {snoozing && onSnooze && onSnoozeMenu && <SnoozeMenu onPick={onSnooze} onClose={() => onSnoozeMenu(false)} repeat={t.repeat} onRepeat={onRepeat} />}
    </li>
  );
}
