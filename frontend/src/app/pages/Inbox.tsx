/** Inbox v2 (Observatory): capture anything, triage it into a first-class object. Every row
 *  shows what Atlas detected (a DOI → paper, "todo:" → Today, "decision:" → decision log …) and
 *  converts in one click; filing to a project and dismissing stay one click too.
 *  API: /quick-capture/ (hint per item), /quick-capture/{id}/convert/, /quick-capture/{id}/snooze/;
 *  MCP list_inbox, convert_capture, snooze_capture.
 *  #495: "Later" parks a capture until tomorrow / Monday / next week / a date — it leaves the inbox
 *  and every untriaged count until that day, then comes back with a "back from snooze" chip.
 *  #496: "Recently triaged" answers "where did that thought go?" — each capture that left the
 *  inbox shows what it became (a link), where it was filed, or that it was dismissed; Put back.
 *  #497: batch triage — tick rows (checkbox, space, ⌘A), then File / Today / Later / Dismiss the
 *  whole selection from a floating bar; POST /quick-capture/bulk/; MCP triage_captures.
 *  #499: a capture with a link learns the page's title (POST /quick-capture/{id}/enrich/, once) and
 *  shows "↗ Title — site"; a bare link converted to a note takes that title.
 *  #500: "by Friday 3pm" / "Oct 1" / "in 3 days" in the line become a due chip, the todo's due
 *  time (in this browser's zone, sent as `tz`) or the milestone's due date.
 *  #501: /inbox?capture=<text> captures that text once on arrival (a bookmarklet on the Connect
 *  page sends "page title + URL" from any browser tab) and drops the parameter. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState, type ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { BookOpen, Check, Clock, FileText, Flag, History, Inbox as InboxIcon, ListChecks, Scale, X } from "lucide-react";
import { api, petReact } from "../api";
import { promptDialog } from "../../components/Dialog";
import { showUndo } from "../../components/UndoToast";
import { ErrorState } from "../../components/ErrorState";
import { Prose } from "../../components/Prose";
import { Skeleton } from "../../components/Skeleton";

type Hint = { suggested: "paper" | "note" | "todo" | "milestone" | "decision"; doi: string; arxiv_id: string; url: string; title: string; due?: string; due_time?: string; project?: { slug: string; name: string; score: number; terms: string[] } | null };
const BROWSER_TZ = (() => { try { return Intl.DateTimeFormat().resolvedOptions().timeZone || ""; } catch { return ""; } })();
const whenLabel = (due?: string, due_time?: string) => {
  const parts: string[] = [];
  if (due) parts.push(new Date(`${due}T00:00:00`).toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" }));
  if (due_time) { const [h, m] = due_time.split(":").map(Number); parts.push(new Date(2000, 0, 1, h, m).toLocaleTimeString(undefined, { hour: "numeric", minute: m ? "2-digit" : undefined })); }
  return parts.join(" · ");
};
type Capture = { id: number; text: string; text_html: string; processed: boolean; project: string | null; snoozed_until: string | null; link_title: string; link_fetched_at: string | null; hint: Hint; created_at: string };
const siteOf = (url: string) => { try { return new URL(url).hostname.replace(/^www\./, ""); } catch { return ""; } };
type Project = { name: string; slug: string; color: string };
type Page<T> = { count: number; results: T[] };
type Converted = { kind: string; id: number; title: string; app_url: string; created?: boolean };
type HistoryRow = { id: number; text: string; project: string | null; project_name: string; outcome: "converted" | "filed" | "dismissed"; became: { kind: string; id: number; title: string; app_url: string; exists: boolean } | null; triaged_at: string };
const KIND_LABEL: Record<string, string> = { reference: "Paper", note: "Note", todo: "Today", milestone: "Milestone", decision: "Decision" };

const panel = "rounded-2xl border border-stone-200 bg-white dark:border-stone-800 dark:bg-stone-900";
const TARGETS: { key: Hint["suggested"]; label: string; icon: typeof BookOpen; needsProject: boolean; hint: string }[] = [
  { key: "paper", label: "Paper", icon: BookOpen, needsProject: false, hint: "Add the DOI / arXiv paper to the library (and file it into the project)" },
  { key: "todo", label: "Today", icon: ListChecks, needsProject: false, hint: "Put it on today's list" },
  { key: "note", label: "Note", icon: FileText, needsProject: true, hint: "Write it up as a note in the project" },
  { key: "milestone", label: "Milestone", icon: Flag, needsProject: true, hint: "Add a milestone to the project's current phase" },
  { key: "decision", label: "Decision", icon: Scale, needsProject: true, hint: "Record it in the project's decision log" },
];
const SNOOZE_OPTIONS: { key: string; label: string }[] = [{ key: "tomorrow", label: "Tomorrow" }, { key: "monday", label: "Monday" }, { key: "next-week", label: "Next week" }, { key: "weekend", label: "Weekend" }];
const todayISO = () => new Date().toLocaleDateString("sv"); // YYYY-MM-DD, local
const isSleeping = (c: Capture) => Boolean(c.snoozed_until && c.snoozed_until > todayISO());
const wakeDay = (iso: string) => new Date(`${iso}T00:00:00`).toLocaleDateString(undefined, { weekday: "short", day: "numeric", month: "short" });
function ago(iso: string): string { const d = (Date.now() - new Date(iso).getTime()) / 60000; if (d < 1) return "just now"; if (d < 60) return `${Math.round(d)} min ago`; if (d < 1440) return `${Math.round(d / 60)} h ago`; return `${Math.round(d / 1440)} d ago`; }

export default function Inbox() {
  const queryClient = useQueryClient();
  const [text, setText] = useState("");
  const [toast, setToast] = useState<{ msg: string; url?: string } | null>(null);
  const flash = (msg: string, url?: string) => { setToast({ msg, url }); setTimeout(() => setToast(null), 5000); };
  // #423: ?run=<bot run id> shows only what that run filed (a bar on the Automations chart)
  const [searchParams, setSearchParams] = useSearchParams();
  const runFilter = searchParams.get("run");
  const { data, isLoading, error, refetch } = useQuery({ queryKey: ["inbox", runFilter], queryFn: () => api<Page<Capture>>(`/quick-capture/?page_size=200${runFilter ? `&run=${encodeURIComponent(runFilter)}` : ""}`) });
  const { data: projects } = useQuery({ queryKey: ["projects-brief"], queryFn: () => api<Page<Project>>("/projects/?page_size=100") });
  const refresh = () => { queryClient.invalidateQueries({ queryKey: ["inbox"] }); queryClient.invalidateQueries({ queryKey: ["inbox-history"] }); queryClient.invalidateQueries({ queryKey: ["dashboard"] }); queryClient.invalidateQueries({ queryKey: ["todos"] }); };
  // #499: a link capture asks for its page title right after it lands; older unfetched ones
  // are looked up once per page load (a failed fetch is remembered, so this never loops)
  const enrich = useMutation({
    mutationFn: ({ id, force }: { id: number; force?: boolean }) => api<Capture>(`/quick-capture/${id}/enrich/${force ? "?force=1" : ""}`, { method: "POST" }),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["inbox"] }),
  });
  const enrichedRef = useRef<Set<number>>(new Set());
  useEffect(() => {
    const todo = (data?.results ?? []).filter((c) => !c.processed && c.hint.url && !c.link_fetched_at && !enrichedRef.current.has(c.id)).slice(0, 5);
    for (const c of todo) { enrichedRef.current.add(c.id); enrich.mutate({ id: c.id }); }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [data]);
  const capture = useMutation({
    mutationFn: (body?: string) => api<Capture>("/quick-capture/", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text: (body ?? text).trim() }) }),
    onSuccess: (made, body) => { if (body === undefined) setText(""); petReact("capture"); refresh(); if (made?.hint?.url && made.id) { enrichedRef.current.add(made.id); enrich.mutate({ id: made.id }); } if (body !== undefined) flash("Captured from the browser — triage it when you have a minute."); },
  });
  // #501: ?capture=<text> — sent by the bookmarklet; captured exactly once, then the parameter
  // is dropped so a reload does not capture it again
  const deepLinkRef = useRef(false);
  useEffect(() => {
    const incoming = searchParams.get("capture");
    if (!incoming || deepLinkRef.current) return;
    deepLinkRef.current = true;
    const next = new URLSearchParams(searchParams); next.delete("capture"); setSearchParams(next, { replace: true });
    if (incoming.trim()) capture.mutate(incoming);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [searchParams]);
  const triage = useMutation({
    mutationFn: ({ id, project }: { id: number; project?: string }) => api(`/quick-capture/${id}/`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(project ? { processed: true, project } : { processed: true }) }),
    onMutate: ({ id }) => {
      const before = queryClient.getQueryData<Page<Capture>>(["inbox", runFilter])?.results.find((c) => c.id === id);
      queryClient.setQueryData<Page<Capture>>(["inbox", runFilter], (old) => old ? { ...old, results: old.results.map((c) => (c.id === id ? { ...c, processed: true } : c)) } : old);
      return { before };
    },
    onSuccess: (_out, { id, project }, ctx) => {
      // #440: the row vanished — six seconds to take it back (processed off, project restored)
      const label = project ? `Filed under ${projects?.results.find((p) => p.slug === project)?.name ?? project}` : "Dismissed";
      showUndo(`${label} — “${(ctx?.before?.text ?? "").slice(0, 50)}”`, async () => {
        await api(`/quick-capture/${id}/`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ processed: false, project: ctx?.before?.project ?? null }) });
        refresh();
      });
    },
    onSettled: refresh,
  });
  const convert = useMutation({
    mutationFn: ({ id, target, project }: { id: number; target: string; project?: string }) => api<Converted>(`/quick-capture/${id}/convert/`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ target, tz: BROWSER_TZ, ...(project ? { project } : {}) }) }),
    onMutate: ({ id }) => { queryClient.setQueryData<Page<Capture>>(["inbox", runFilter], (old) => old ? { ...old, results: old.results.map((c) => (c.id === id ? { ...c, processed: true } : c)) } : old); },
    onSuccess: (out) => { refresh(); if (out.kind === "reference") petReact("paper"); if (out.kind === "note") petReact("note"); flash(`${out.kind === "reference" ? (out.created ? "Added the paper" : "Paper already in the library") : out.kind === "todo" ? "On today's list" : `Created the ${out.kind}`}: ${out.title}`, out.app_url); },
    onError: (e) => { refresh(); flash(`Could not convert — ${(e as Error).message}`); },
  });
  // #497: one action over the selection; file/dismiss/snooze can be undone as a batch
  const bulk = useMutation({
    mutationFn: ({ ids, action, project, until }: { ids: number[]; action: string; project?: string; until?: string }) => api<{ action: string; count: number; ids: number[] }>("/quick-capture/bulk/", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ids, action, ...(project ? { project } : {}), ...(until ? { until } : {}) }) }),
    onSuccess: (out, { action, project }) => {
      refresh();
      const n = out.count;
      const label = action === "file" ? `Filed ${n} under ${projects?.results.find((p) => p.slug === project)?.name ?? project}` : action === "dismiss" ? `Dismissed ${n}` : action === "snooze" ? `Snoozed ${n}` : action === "todo" ? `${n} on today's list` : `Woke ${n}`;
      if (action === "todo") { petReact("capture"); flash(label, "/today"); return; }
      if (action === "wake") { flash(label); return; }
      showUndo(`${label} capture${n === 1 ? "" : "s"}`, async () => {
        if (action === "snooze") await api("/quick-capture/bulk/", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ids: out.ids, action: "wake" }) });
        else await Promise.all(out.ids.map((id) => api(`/quick-capture/${id}/`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ processed: false }) })));
        refresh();
      });
    },
    onError: (e) => { refresh(); flash(`Could not triage — ${(e as Error).message}`); },
  });
  // #495: snooze = "not now"; the row leaves at once and the undo toast wakes it again
  const snooze = useMutation({
    mutationFn: ({ id, until }: { id: number; until: string }) => api<Capture>(`/quick-capture/${id}/snooze/`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ until }) }),
    onMutate: ({ id, until }) => {
      const before = queryClient.getQueryData<Page<Capture>>(["inbox", runFilter])?.results.find((c) => c.id === id);
      queryClient.setQueryData<Page<Capture>>(["inbox", runFilter], (old) => old ? { ...old, results: old.results.map((c) => (c.id === id ? { ...c, snoozed_until: until ? "9999-12-31" : null } : c)) } : old);
      return { before };
    },
    onSuccess: (out, { id, until }, ctx) => {
      if (until) showUndo(`Snoozed until ${out.snoozed_until ? wakeDay(out.snoozed_until) : "later"} — “${(ctx?.before?.text ?? "").slice(0, 50)}”`, async () => { await api(`/quick-capture/${id}/snooze/`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ until: "" }) }); refresh(); });
    },
    onError: (e) => flash(`Could not snooze — ${(e as Error).message}`),
    onSettled: refresh,
  });

  if (isLoading) return <div className="mx-auto max-w-3xl"><Skeleton className="mb-4 h-8 w-40" /><Skeleton className="mb-6 h-24 w-full" /><Skeleton className="h-40 w-full" /></div>;
  if (error || !data) return <ErrorState message="Couldn't load the inbox." onRetry={() => refetch()} />;
  // in run mode everything the run filed is shown, triaged or not — that is the question asked
  const open = runFilter ? data.results : data.results.filter((c) => !c.processed && !isSleeping(c));
  const sleeping = runFilter ? [] : data.results.filter((c) => !c.processed && isSleeping(c));
  const stillOpen = open.filter((c) => !c.processed).length;
  const runBanner = runFilter ? (
    <div className="mb-3 flex flex-wrap items-center gap-2 rounded-lg border border-indigo-200 bg-indigo-50/60 px-3 py-2 text-xs text-indigo-800 dark:border-indigo-500/30 dark:bg-indigo-500/10 dark:text-indigo-200" data-testid="inbox-run-filter">
      <span>Showing what one automation run filed — {data.results.length} capture{data.results.length === 1 ? "" : "s"}, {stillOpen} still open.</span>
      <button type="button" onClick={() => setSearchParams({})} className="ml-auto font-medium hover:underline">Show the whole inbox</button>
    </div>
  ) : null;
  const projectRows = projects?.results ?? [];
  return <InboxBody runBanner={runBanner} openCount={stillOpen} open={open} sleeping={sleeping} projectRows={projectRows} text={text} setText={setText} capture={capture} convert={convert} triage={triage} snooze={snooze} bulk={bulk} toast={toast} onRetryLink={(id) => enrich.mutate({ id, force: true })} />;
}

/* Keyboard triage (Inbox v2 slice 2): j/k or arrows move the cursor, Enter takes the
   suggested target, 1–5 pick a target, x dismisses, f files under the project — the whole
   inbox without touching the mouse. Keys are ignored while typing in the capture box. */
const KEY_TARGETS = ["paper", "todo", "note", "milestone", "decision"] as const;

function InboxBody({ open, sleeping, projectRows, text, setText, capture, convert, triage, snooze, bulk, toast, runBanner, openCount, onRetryLink }: { runBanner?: ReactNode; openCount?: number; onRetryLink?: (id: number) => void; open: Capture[]; sleeping: Capture[]; projectRows: Project[]; text: string; setText: (t: string) => void; capture: { mutate: (body?: string) => void; isPending: boolean }; convert: { mutate: (v: { id: number; target: string; project?: string }) => void; isPending: boolean }; triage: { mutate: (v: { id: number; project?: string }) => void; isPending: boolean }; snooze: { mutate: (v: { id: number; until: string }) => void; isPending: boolean }; bulk: { mutate: (v: { ids: number[]; action: string; project?: string; until?: string }) => void; isPending: boolean }; toast: { msg: string; url?: string } | null }) {
  const [cursor, setCursor] = useState(0);
  const [legend, setLegend] = useState(false);
  const [showSleeping, setShowSleeping] = useState(false);
  // #497: the selection — ids of open rows; cleared when they leave the list
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [bulkProject, setBulkProject] = useState("");
  useEffect(() => { setSelected((prev) => { const live = new Set(open.map((c) => c.id)); const next = new Set([...prev].filter((id) => live.has(id))); return next.size === prev.size ? prev : next; }); }, [open]);
  useEffect(() => { if (!bulkProject && projectRows[0]) setBulkProject(projectRows[0].slug); }, [projectRows, bulkProject]);
  const toggle = (id: number) => setSelected((prev) => { const next = new Set(prev); if (next.has(id)) next.delete(id); else next.add(id); return next; });
  const runBulk = async (action: string) => {
    const ids = [...selected];
    if (!ids.length) return;
    if (action === "snooze") {
      const picked = await promptDialog({ title: `Snooze ${ids.length} capture${ids.length === 1 ? "" : "s"} until`, label: "tomorrow · monday · next-week · weekend · YYYY-MM-DD", initial: "tomorrow", validate: (v) => (/^(tomorrow|monday|next-week|weekend|\d{4}-\d{2}-\d{2})$/.test(v.trim().toLowerCase()) ? null : "tomorrow, monday, next-week, weekend or a date") });
      if (!picked) return;
      bulk.mutate({ ids, action, until: picked.trim().toLowerCase() });
    } else bulk.mutate({ ids, action, project: action === "file" || action === "todo" ? bulkProject || undefined : undefined });
    setSelected(new Set());
  };
  const snoozeUntil = async (id: number, until: string) => {
    if (until !== "date") { snooze.mutate({ id, until }); return; }
    const picked = await promptDialog({ title: "Snooze until", label: "Day it comes back (YYYY-MM-DD)", initial: todayISO(), validate: (v) => (/^\d{4}-\d{2}-\d{2}$/.test(v.trim()) && v.trim() > todayISO() ? null : "A date after today, as YYYY-MM-DD") });
    if (picked) snooze.mutate({ id, until: picked.trim() });
  };
  const projectFor = (c: Capture) => c.project ?? projectRows[0]?.slug ?? undefined;
  useEffect(() => { if (cursor > open.length - 1) setCursor(Math.max(0, open.length - 1)); }, [open.length, cursor]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement | null)?.tagName;
      const onCheckbox = tag === "INPUT" && (e.target as HTMLInputElement).type === "checkbox";
      if ((tag === "INPUT" && !onCheckbox) || tag === "TEXTAREA" || tag === "SELECT") return;
      if ((e.metaKey || e.ctrlKey) && e.key === "a" && open.length) { e.preventDefault(); setSelected(new Set(open.map((c) => c.id))); return; }
      if (e.key === "Escape" && selected.size) { setSelected(new Set()); (e.target as HTMLElement | null)?.blur?.(); return; }
      if (onCheckbox || e.metaKey || e.ctrlKey || e.altKey) return; // a focused checkbox keeps its own space
      const c = open[cursor];
      if (e.key === "j" || e.key === "ArrowDown") { e.preventDefault(); setCursor((i) => Math.min(open.length - 1, i + 1)); }
      else if (e.key === "k" || e.key === "ArrowUp") { e.preventDefault(); setCursor((i) => Math.max(0, i - 1)); }
      else if (e.key === "?") { setLegend((v) => !v); }
      else if (!c) return;
      else if (e.key === "Enter") { e.preventDefault(); convert.mutate({ id: c.id, target: c.hint.suggested, project: projectFor(c) }); }
      else if (/^[1-5]$/.test(e.key)) { const target = KEY_TARGETS[Number(e.key) - 1]; if (target === "paper" && !(c.hint.doi || c.hint.arxiv_id)) return; e.preventDefault(); convert.mutate({ id: c.id, target, project: projectFor(c) }); }
      else if (e.key === "x" || e.key === "Delete") { e.preventDefault(); triage.mutate({ id: c.id }); }
      else if (e.key === "f") { const p = projectFor(c); if (p) { e.preventDefault(); triage.mutate({ id: c.id, project: p }); } }
      else if (e.key === " ") { e.preventDefault(); toggle(c.id); }
      else if (e.key === "s") { e.preventDefault(); snooze.mutate({ id: c.id, until: "tomorrow" }); }
      else if (e.key === "w") { e.preventDefault(); snooze.mutate({ id: c.id, until: "next-week" }); }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, cursor, projectRows, selected]);
  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-4">
        <h1 className="font-display text-3xl font-bold tracking-tight dark:text-stone-100">Inbox <span className="text-gradient">{(openCount ?? open.length) === 0 ? "· zero" : `· ${openCount ?? open.length} to triage`}</span></h1>
        <p className="mt-0.5 text-sm text-stone-400">Get it out of your head now. Atlas reads DOIs, "todo:", "idea:", "decision:" and "milestone:" and files each into the right place with one click.</p>
      </div>
      <form onSubmit={(e) => { e.preventDefault(); if (text.trim()) capture.mutate(); }} className={`${panel} hairline-gradient rise mb-6 p-2 pl-4`} data-testid="capture-form">
        <textarea value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => { if ((e.metaKey || e.ctrlKey) && e.key === "Enter" && text.trim()) capture.mutate(); }} rows={2} placeholder="A stray thought, a DOI, a todo: …, an idea: … — ⌘Enter captures" aria-label="Capture" className="block w-full resize-none border-0 bg-transparent py-2 text-base leading-relaxed placeholder:text-stone-400 focus:outline-none dark:text-stone-100" />
        <div className="flex items-center justify-between pt-1">
          <span className="text-[11px] text-stone-400">{text.trim() ? `Looks like a ${(() => { const t = text.trim().toLowerCase(); if (/10\.\d{4,9}\//.test(t) || /arxiv|\d{4}\.\d{4,5}/.test(t)) return "paper"; if (/^(todo|task)\s*[:\-]/.test(t)) return "todo"; if (/^decision/.test(t)) return "decision"; if (/^milestone/.test(t)) return "milestone"; if (/^(idea|note)\s*[:\-]/.test(t) || t.length > 240) return "note"; return "todo"; })()}` : "Goes straight to the inbox — file it later."}</span>
          <button type="submit" disabled={capture.isPending || !text.trim()} className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-40">{capture.isPending ? "Capturing…" : "Capture"}</button>
        </div>
      </form>

      {runBanner}
      {open.length > 0 && (
        <p className="mb-2 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px] text-stone-400" data-testid="inbox-legend">
          <button type="button" onClick={() => setLegend((v) => !v)} className="rounded border border-stone-200 px-1.5 font-mono dark:border-stone-700" title="Keyboard triage">?</button>
          {legend ? <><span><kbd className="font-mono">j</kbd>/<kbd className="font-mono">k</kbd> move</span><span><kbd className="font-mono">↵</kbd> suggested</span><span><kbd className="font-mono">1</kbd> paper · <kbd className="font-mono">2</kbd> today · <kbd className="font-mono">3</kbd> note · <kbd className="font-mono">4</kbd> milestone · <kbd className="font-mono">5</kbd> decision</span><span><kbd className="font-mono">f</kbd> file</span><span><kbd className="font-mono">x</kbd> dismiss</span><span><kbd className="font-mono">s</kbd> tomorrow · <kbd className="font-mono">w</kbd> next week</span><span><kbd className="font-mono">space</kbd> select · <kbd className="font-mono">⌘A</kbd> all</span></> : <span>keyboard triage: j/k · ↵ · 1–5 · x · s · space</span>}
        </p>
      )}
      {open.length === 0 ? (
        <div className={`${panel} rise p-10 text-center`} style={{ ["--i" as string]: 1 }}>
          <InboxIcon className="mx-auto mb-2 h-7 w-7 text-indigo-400" aria-hidden="true" />
          <p className="font-medium text-stone-700 dark:text-stone-100">Inbox zero.</p>
          <p className="mx-auto mt-1 max-w-md text-sm text-stone-400">{sleeping.length > 0 ? `${sleeping.length} capture${sleeping.length === 1 ? " is" : "s are"} snoozed and will come back on ${sleeping.length === 1 ? "its" : "their"} day. ` : ""}Capture from anywhere with ⌘K, or from Claude with the quick_capture tool. Triage here when you have a minute.</p>
        </div>
      ) : (
        <ul className="space-y-2" data-testid="inbox-list">
          {open.map((c, i) => <Row key={c.id} c={c} i={i} active={i === cursor} onFocus={() => setCursor(i)} projects={projectRows} busy={convert.isPending || triage.isPending || snooze.isPending || bulk.isPending} onConvert={(target, project) => convert.mutate({ id: c.id, target, project })} onFile={(project) => triage.mutate({ id: c.id, project })} onDismiss={() => triage.mutate({ id: c.id })} onSnooze={(until) => snoozeUntil(c.id, until)} selected={selected.has(c.id)} onToggle={() => toggle(c.id)} onRetryLink={onRetryLink ? () => onRetryLink(c.id) : undefined} />)}
        </ul>
      )}
      {selected.size > 0 && (
        <div className="sticky bottom-4 z-20 mt-3 flex flex-wrap items-center gap-2 rounded-xl border border-indigo-300/60 bg-white/95 px-3 py-2 text-xs shadow-lg backdrop-blur dark:border-indigo-500/40 dark:bg-stone-900/95" data-testid="bulk-bar" role="toolbar" aria-label="Selection">
          <span className="font-medium text-stone-700 dark:text-stone-100" data-testid="bulk-count">{selected.size} selected</span>
          <button type="button" onClick={() => setSelected(new Set(open.map((c) => c.id)))} className="text-stone-500 hover:underline dark:text-stone-400">all {open.length}</button>
          <button type="button" onClick={() => setSelected(new Set())} className="text-stone-500 hover:underline dark:text-stone-400">none</button>
          <span className="ml-auto flex flex-wrap items-center gap-1">
            <select value={bulkProject} onChange={(e) => setBulkProject(e.target.value)} aria-label="Project for the selection" className="rounded-md border border-stone-200 bg-white px-1.5 py-0.5 text-[11px] text-stone-600 dark:border-stone-700 dark:bg-stone-800 dark:text-stone-300">
              {projectRows.map((p) => <option key={p.slug} value={p.slug}>{p.name}</option>)}
            </select>
            <button type="button" disabled={bulk.isPending || !bulkProject} onClick={() => runBulk("file")} className="inline-flex items-center gap-1 rounded-md bg-indigo-600 px-2 py-0.5 font-medium text-white hover:bg-indigo-700 disabled:opacity-40" data-testid="bulk-file"><Check className="h-3 w-3" aria-hidden="true" />File</button>
            <button type="button" disabled={bulk.isPending} onClick={() => runBulk("todo")} className="inline-flex items-center gap-1 rounded-md border border-stone-200 px-2 py-0.5 text-stone-600 hover:border-indigo-300 disabled:opacity-40 dark:border-stone-700 dark:text-stone-300" data-testid="bulk-todo"><ListChecks className="h-3 w-3" aria-hidden="true" />Today</button>
            <button type="button" disabled={bulk.isPending} onClick={() => runBulk("snooze")} className="inline-flex items-center gap-1 rounded-md border border-stone-200 px-2 py-0.5 text-stone-600 hover:border-indigo-300 disabled:opacity-40 dark:border-stone-700 dark:text-stone-300" data-testid="bulk-snooze"><Clock className="h-3 w-3" aria-hidden="true" />Later…</button>
            <button type="button" disabled={bulk.isPending} onClick={() => runBulk("dismiss")} className="inline-flex items-center gap-1 rounded-md border border-stone-200 px-2 py-0.5 text-stone-600 hover:border-red-300 hover:text-red-600 disabled:opacity-40 dark:border-stone-700 dark:text-stone-300" data-testid="bulk-dismiss"><X className="h-3 w-3" aria-hidden="true" />Dismiss</button>
          </span>
        </div>
      )}
      {sleeping.length > 0 && (
        <section className="mt-8" data-testid="inbox-snoozed">
          <button type="button" onClick={() => setShowSleeping((v) => !v)} className="mb-2 flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-stone-400 hover:text-stone-600 dark:hover:text-stone-200" data-testid="snoozed-toggle" aria-expanded={showSleeping}>
            <Clock className="h-3.5 w-3.5" aria-hidden="true" />{sleeping.length} snoozed · next back {wakeDay(sleeping.map((c) => c.snoozed_until!).sort()[0])} <span className="font-normal normal-case tracking-normal">{showSleeping ? "· hide" : "· show"}</span>
          </button>
          {showSleeping && (
            <ul className="space-y-2">
              {sleeping.map((c, i) => <Row key={c.id} c={c} i={i} active={false} onFocus={() => undefined} projects={projectRows} busy={convert.isPending || triage.isPending || snooze.isPending} onConvert={(target, project) => convert.mutate({ id: c.id, target, project })} onFile={(project) => triage.mutate({ id: c.id, project })} onDismiss={() => triage.mutate({ id: c.id })} onSnooze={(until) => snoozeUntil(c.id, until)} onWake={() => snooze.mutate({ id: c.id, until: "" })} />)}
            </ul>
          )}
        </section>
      )}
      {!runBanner && <RecentlyTriaged />}
      {toast && (
        <div role="status" className="fixed bottom-5 right-5 z-30 flex items-center gap-3 rounded-xl border border-stone-200 bg-white px-4 py-2.5 text-sm shadow-lg dark:border-stone-700 dark:bg-stone-900 dark:text-stone-100">
          <span className="max-w-md truncate">{toast.msg}</span>{toast.url && <Link to={toast.url} className="shrink-0 font-medium text-indigo-600 hover:underline dark:text-indigo-300">open →</Link>}
        </div>
      )}
    </div>
  );
}


/* #496: the captures that left the inbox, newest first — what each became, with a link. */
function RecentlyTriaged() {
  const queryClient = useQueryClient();
  const [open, setOpen] = useState(false);
  const { data, isLoading } = useQuery({ queryKey: ["inbox-history"], queryFn: () => api<{ results: HistoryRow[] }>("/quick-capture/history/?limit=30"), enabled: open });
  const putBack = useMutation({
    mutationFn: (id: number) => api(`/quick-capture/${id}/`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ processed: false }) }),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["inbox"] }); queryClient.invalidateQueries({ queryKey: ["inbox-history"] }); queryClient.invalidateQueries({ queryKey: ["dashboard"] }); },
  });
  const rows = data?.results ?? [];
  return (
    <section className="mt-8" data-testid="inbox-history">
      <button type="button" onClick={() => setOpen((v) => !v)} className="mb-2 flex items-center gap-1.5 text-xs font-medium uppercase tracking-wide text-stone-400 hover:text-stone-600 dark:hover:text-stone-200" data-testid="history-toggle" aria-expanded={open}>
        <History className="h-3.5 w-3.5" aria-hidden="true" />Recently triaged <span className="font-normal normal-case tracking-normal">{open ? "· hide" : "· where did it go?"}</span>
      </button>
      {open && (isLoading ? <Skeleton className="h-16 w-full" /> : rows.length === 0 ? (
        <p className="text-xs text-stone-400">Nothing has left the inbox yet.</p>
      ) : (
        <ul className={`${panel} divide-y divide-stone-100 text-xs dark:divide-stone-800`}>
          {rows.map((h) => (
            <li key={h.id} className="flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2" data-testid="history-row" data-outcome={h.outcome}>
              <span className="min-w-0 flex-1 truncate text-stone-700 dark:text-stone-200" title={h.text}>{h.text}</span>
              <span className="shrink-0 text-stone-400">{ago(h.triaged_at)}</span>
              {h.outcome === "converted" && h.became && (h.became.exists ? (
                <Link to={h.became.app_url} className="shrink-0 font-medium text-indigo-600 hover:underline dark:text-indigo-300" data-testid="history-link">→ {KIND_LABEL[h.became.kind] ?? h.became.kind} · <span className="font-normal">{h.became.title}</span></Link>
              ) : (
                <span className="shrink-0 text-stone-400" title="The object it became was deleted since">→ {KIND_LABEL[h.became.kind] ?? h.became.kind} (deleted)</span>
              ))}
              {h.outcome === "filed" && <span className="shrink-0 rounded-full bg-emerald-500/10 px-1.5 py-0.5 text-emerald-700 dark:text-emerald-300">filed under {h.project_name || h.project}</span>}
              {h.outcome === "dismissed" && <span className="shrink-0 rounded-full bg-stone-500/10 px-1.5 py-0.5 text-stone-500 dark:text-stone-400">dismissed</span>}
              {h.outcome !== "converted" && <button type="button" disabled={putBack.isPending} onClick={() => putBack.mutate(h.id)} className="shrink-0 rounded-md border border-stone-200 px-1.5 py-0.5 text-stone-600 hover:border-indigo-300 disabled:opacity-40 dark:border-stone-700 dark:text-stone-300" data-testid="history-put-back">Put back</button>}
            </li>
          ))}
        </ul>
      ))}
    </section>
  );
}

function Row({ c, i, active, onFocus, projects, busy, onConvert, onFile, onDismiss, onSnooze, onWake, selected, onToggle, onRetryLink }: { c: Capture; i: number; active: boolean; onFocus: () => void; projects: Project[]; busy: boolean; onConvert: (target: string, project?: string) => void; onFile: (project: string) => void; onDismiss: () => void; onSnooze: (until: string) => void; onWake?: () => void; selected?: boolean; onToggle?: () => void; onRetryLink?: () => void }) {
  // #494: the project Atlas suggests from the capture's words wins over "the first project"
  const [project, setProject] = useState(c.project ?? c.hint.project?.slug ?? projects[0]?.slug ?? "");
  const [later, setLater] = useState(false);
  useEffect(() => { if (!later) return; const close = () => setLater(false); document.addEventListener("click", close); return () => document.removeEventListener("click", close); }, [later]);
  const sleeping = isSleeping(c);
  const wokeToday = Boolean(c.snoozed_until) && !sleeping && !c.processed;
  useEffect(() => { if (!project && projects[0]) setProject(projects[0].slug); }, [projects, project]);
  const suggested = TARGETS.find((t) => t.key === c.hint.suggested)!;
  const chips: string[] = [];
  if (c.hint.doi) chips.push(`doi ${c.hint.doi}`);
  if (c.hint.arxiv_id) chips.push(`arXiv ${c.hint.arxiv_id}`);
  if (c.hint.url && !c.hint.doi) chips.push(`link · ${siteOf(c.hint.url) || "web"}`);
  const when = whenLabel(c.hint.due, c.hint.due_time);
  const bareLink = Boolean(c.hint.url) && c.text.trim() === c.hint.url;
  return (
    <li className={`${panel} rise p-3 transition-shadow ${active ? "ring-2 ring-indigo-500/60" : ""} ${selected ? "bg-indigo-50/60 dark:bg-indigo-500/10" : ""} ${later ? "relative z-30" : ""}`} style={{ ["--i" as string]: i + 1 }} data-testid="inbox-row" data-active={active ? "1" : undefined} data-selected={selected ? "1" : undefined} onMouseEnter={onFocus}>
      <div className="flex items-start gap-2">
        {onToggle && <input type="checkbox" checked={Boolean(selected)} onChange={onToggle} aria-label="Select capture" className="mt-1 h-3.5 w-3.5 shrink-0 accent-indigo-600" data-testid="select-capture" />}
        {/* #407: [[note]] and @cite-key mentions in a capture are links */}
        <div className="min-w-0 flex-1">
          <Prose html={c.text_html} className={`break-words text-sm text-stone-800 dark:text-stone-100 ${bareLink && c.link_title ? "text-[11px] text-stone-400" : ""}`} testId="capture-text" />
          {c.hint.url && !c.hint.doi && (
            <p className="mt-0.5 flex flex-wrap items-baseline gap-x-2 text-xs" data-testid="link-title">
              {c.link_title ? (
                <a href={c.hint.url} target="_blank" rel="noreferrer" className={`min-w-0 truncate font-medium text-indigo-600 hover:underline dark:text-indigo-300 ${bareLink ? "text-sm" : ""}`} title={c.hint.url}>↗ {c.link_title}</a>
              ) : c.link_fetched_at ? (
                <span className="text-stone-400">no title found{onRetryLink && <> · <button type="button" onClick={onRetryLink} className="hover:underline">try again</button></>}</span>
              ) : (
                <span className="text-stone-400">fetching the page title…</span>
              )}
              <span className="text-stone-400">{siteOf(c.hint.url)}</span>
            </p>
          )}
        </div>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-1.5 text-[11px]">
        <span className="text-stone-400">{ago(c.created_at)}</span>
        {c.processed && <span className="rounded-full bg-emerald-500/15 px-1.5 py-0.5 text-emerald-700 dark:text-emerald-300" title="Already triaged">filed</span>}
        {sleeping && <span className="rounded-full bg-amber-500/15 px-1.5 py-0.5 text-amber-700 dark:text-amber-300" data-testid="snoozed-chip">back {wakeDay(c.snoozed_until!)}</span>}
        {wokeToday && <span className="rounded-full bg-amber-500/15 px-1.5 py-0.5 text-amber-700 dark:text-amber-300" title={`Snoozed until ${wakeDay(c.snoozed_until!)}`} data-testid="woke-chip">back from snooze</span>}
        {chips.map((ch) => <span key={ch} className="rounded-full bg-indigo-500/10 px-1.5 py-0.5 font-mono text-indigo-700 dark:text-indigo-200">{ch}</span>)}
        {when && <span className="rounded-full bg-sky-500/10 px-1.5 py-0.5 text-sky-700 dark:text-sky-300" title={c.hint.suggested === "milestone" ? "Read from the line — becomes the milestone's due date" : "Read from the line — becomes the due time on Today"} data-testid="when-chip">due {when}</span>}
        {c.hint.project && !c.project && project === c.hint.project.slug && <span className="rounded-full bg-emerald-500/10 px-1.5 py-0.5 text-emerald-700 dark:text-emerald-300" title={`Suggested from ${c.hint.project.terms.join(", ")}`} data-testid="suggested-project">suggested · {c.hint.project.name}</span>}
        <span className="ml-auto flex flex-wrap items-center gap-1">
          <select value={project} onChange={(e) => setProject(e.target.value)} aria-label="Project" className="rounded-md border border-stone-200 bg-white px-1.5 py-0.5 text-[11px] text-stone-600 dark:border-stone-700 dark:bg-stone-800 dark:text-stone-300">
            {projects.map((p) => <option key={p.slug} value={p.slug}>{p.name}</option>)}
          </select>
          {TARGETS.filter((t) => t.key === "paper" ? Boolean(c.hint.doi || c.hint.arxiv_id) : true).map((t) => (
            <button key={t.key} type="button" disabled={busy || (t.needsProject && !project)} onClick={() => onConvert(t.key, project || undefined)} title={t.hint} className={`inline-flex items-center gap-1 rounded-md px-2 py-0.5 transition-colors disabled:opacity-40 ${t.key === suggested.key ? "bg-indigo-600 font-medium text-white hover:bg-indigo-700" : "border border-stone-200 text-stone-600 hover:border-indigo-300 dark:border-stone-700 dark:text-stone-300"}`} data-testid={`convert-${t.key}`}>
              <t.icon className="h-3 w-3" aria-hidden="true" />{t.label}
            </button>
          ))}
          <button type="button" disabled={busy || !project} onClick={() => onFile(project)} title="Keep it as a capture, filed under the project" className="inline-flex items-center gap-1 rounded-md border border-stone-200 px-2 py-0.5 text-stone-600 hover:border-indigo-300 disabled:opacity-40 dark:border-stone-700 dark:text-stone-300"><Check className="h-3 w-3" aria-hidden="true" />File</button>
          {sleeping && onWake ? (
            <button type="button" disabled={busy} onClick={onWake} title="Back to the inbox now" className="inline-flex items-center gap-1 rounded-md border border-amber-300/60 px-2 py-0.5 text-amber-700 hover:border-amber-400 disabled:opacity-40 dark:text-amber-300" data-testid="wake"><Clock className="h-3 w-3" aria-hidden="true" />Wake</button>
          ) : (
            <span className="relative">
              <button type="button" disabled={busy} onClick={(e) => { e.stopPropagation(); setLater((v) => !v); }} title="Not now — hide it until a day you pick (s = tomorrow, w = next week)" className="inline-flex items-center gap-1 rounded-md border border-stone-200 px-2 py-0.5 text-stone-600 hover:border-indigo-300 disabled:opacity-40 dark:border-stone-700 dark:text-stone-300" data-testid="snooze-menu" aria-expanded={later}><Clock className="h-3 w-3" aria-hidden="true" />Later</button>
              {later && (
                <span className="absolute right-0 top-full z-20 mt-1 flex w-36 flex-col rounded-lg border border-stone-200 bg-white p-1 text-left shadow-lg dark:border-stone-700 dark:bg-stone-900" role="menu" data-testid="snooze-options">
                  {SNOOZE_OPTIONS.map((o) => <button key={o.key} type="button" role="menuitem" onClick={() => { setLater(false); onSnooze(o.key); }} className="rounded px-2 py-1 text-left text-xs text-stone-700 hover:bg-stone-100 dark:text-stone-200 dark:hover:bg-stone-800" data-testid={`snooze-${o.key}`}>{o.label}</button>)}
                  <button type="button" role="menuitem" onClick={() => { setLater(false); onSnooze("date"); }} className="rounded px-2 py-1 text-left text-xs text-stone-700 hover:bg-stone-100 dark:text-stone-200 dark:hover:bg-stone-800" data-testid="snooze-date">Pick a date…</button>
                </span>
              )}
            </span>
          )}
          <button type="button" disabled={busy} onClick={onDismiss} title="Dismiss" className="rounded-md px-1.5 py-0.5 text-stone-400 hover:text-red-500" aria-label="Dismiss"><X className="h-3.5 w-3.5" aria-hidden="true" /></button>
        </span>
      </div>
    </li>
  );
}
