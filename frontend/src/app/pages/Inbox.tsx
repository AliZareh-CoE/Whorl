/** Inbox v2 (Observatory): capture anything, triage it into a first-class object. Every row
 *  shows what Atlas detected (a DOI → paper, "todo:" → Today, "decision:" → decision log …) and
 *  converts in one click; filing to a project and dismissing stay one click too.
 *  API: /quick-capture/ (hint per item), /quick-capture/{id}/convert/; MCP list_inbox, convert_capture. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, type ReactNode } from "react";
import { Link, useSearchParams } from "react-router-dom";
import { BookOpen, Check, FileText, Flag, Inbox as InboxIcon, ListChecks, Scale, X } from "lucide-react";
import { api, petReact } from "../api";
import { ErrorState } from "../../components/ErrorState";
import { Prose } from "../../components/Prose";
import { Skeleton } from "../../components/Skeleton";

type Hint = { suggested: "paper" | "note" | "todo" | "milestone" | "decision"; doi: string; arxiv_id: string; url: string; title: string };
type Capture = { id: number; text: string; text_html: string; processed: boolean; project: string | null; hint: Hint; created_at: string };
type Project = { name: string; slug: string; color: string };
type Page<T> = { count: number; results: T[] };
type Converted = { kind: string; id: number; title: string; app_url: string; created?: boolean };

const panel = "rounded-2xl border border-stone-200 bg-white dark:border-stone-800 dark:bg-stone-900";
const TARGETS: { key: Hint["suggested"]; label: string; icon: typeof BookOpen; needsProject: boolean; hint: string }[] = [
  { key: "paper", label: "Paper", icon: BookOpen, needsProject: false, hint: "Add the DOI / arXiv paper to the library (and file it into the project)" },
  { key: "todo", label: "Today", icon: ListChecks, needsProject: false, hint: "Put it on today's list" },
  { key: "note", label: "Note", icon: FileText, needsProject: true, hint: "Write it up as a note in the project" },
  { key: "milestone", label: "Milestone", icon: Flag, needsProject: true, hint: "Add a milestone to the project's current phase" },
  { key: "decision", label: "Decision", icon: Scale, needsProject: true, hint: "Record it in the project's decision log" },
];
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
  const refresh = () => { queryClient.invalidateQueries({ queryKey: ["inbox"] }); queryClient.invalidateQueries({ queryKey: ["dashboard"] }); queryClient.invalidateQueries({ queryKey: ["todos"] }); };
  const capture = useMutation({
    mutationFn: () => api("/quick-capture/", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text }) }),
    onSuccess: () => { setText(""); petReact("capture"); refresh(); },
  });
  const triage = useMutation({
    mutationFn: ({ id, project }: { id: number; project?: string }) => api(`/quick-capture/${id}/`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(project ? { processed: true, project } : { processed: true }) }),
    onMutate: ({ id }) => { queryClient.setQueryData<Page<Capture>>(["inbox", runFilter], (old) => old ? { ...old, results: old.results.map((c) => (c.id === id ? { ...c, processed: true } : c)) } : old); },
    onSettled: refresh,
  });
  const convert = useMutation({
    mutationFn: ({ id, target, project }: { id: number; target: string; project?: string }) => api<Converted>(`/quick-capture/${id}/convert/`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(project ? { target, project } : { target }) }),
    onMutate: ({ id }) => { queryClient.setQueryData<Page<Capture>>(["inbox", runFilter], (old) => old ? { ...old, results: old.results.map((c) => (c.id === id ? { ...c, processed: true } : c)) } : old); },
    onSuccess: (out) => { refresh(); if (out.kind === "reference") petReact("paper"); if (out.kind === "note") petReact("note"); flash(`${out.kind === "reference" ? (out.created ? "Added the paper" : "Paper already in the library") : out.kind === "todo" ? "On today's list" : `Created the ${out.kind}`}: ${out.title}`, out.app_url); },
    onError: (e) => { refresh(); flash(`Could not convert — ${(e as Error).message}`); },
  });

  if (isLoading) return <div className="mx-auto max-w-3xl"><Skeleton className="mb-4 h-8 w-40" /><Skeleton className="mb-6 h-24 w-full" /><Skeleton className="h-40 w-full" /></div>;
  if (error || !data) return <ErrorState message="Couldn't load the inbox." onRetry={() => refetch()} />;
  // in run mode everything the run filed is shown, triaged or not — that is the question asked
  const open = runFilter ? data.results : data.results.filter((c) => !c.processed);
  const stillOpen = data.results.filter((c) => !c.processed).length;
  const runBanner = runFilter ? (
    <div className="mb-3 flex flex-wrap items-center gap-2 rounded-lg border border-indigo-200 bg-indigo-50/60 px-3 py-2 text-xs text-indigo-800 dark:border-indigo-500/30 dark:bg-indigo-500/10 dark:text-indigo-200" data-testid="inbox-run-filter">
      <span>Showing what one automation run filed — {data.results.length} capture{data.results.length === 1 ? "" : "s"}, {stillOpen} still open.</span>
      <button type="button" onClick={() => setSearchParams({})} className="ml-auto font-medium hover:underline">Show the whole inbox</button>
    </div>
  ) : null;
  const projectRows = projects?.results ?? [];
  return <InboxBody runBanner={runBanner} openCount={stillOpen} open={open} projectRows={projectRows} text={text} setText={setText} capture={capture} convert={convert} triage={triage} toast={toast} />;
}

/* Keyboard triage (Inbox v2 slice 2): j/k or arrows move the cursor, Enter takes the
   suggested target, 1–5 pick a target, x dismisses, f files under the project — the whole
   inbox without touching the mouse. Keys are ignored while typing in the capture box. */
const KEY_TARGETS = ["paper", "todo", "note", "milestone", "decision"] as const;

function InboxBody({ open, projectRows, text, setText, capture, convert, triage, toast, runBanner, openCount }: { runBanner?: ReactNode; openCount?: number; open: Capture[]; projectRows: Project[]; text: string; setText: (t: string) => void; capture: { mutate: () => void; isPending: boolean }; convert: { mutate: (v: { id: number; target: string; project?: string }) => void; isPending: boolean }; triage: { mutate: (v: { id: number; project?: string }) => void; isPending: boolean }; toast: { msg: string; url?: string } | null }) {
  const [cursor, setCursor] = useState(0);
  const [legend, setLegend] = useState(false);
  const projectFor = (c: Capture) => c.project ?? projectRows[0]?.slug ?? undefined;
  useEffect(() => { if (cursor > open.length - 1) setCursor(Math.max(0, open.length - 1)); }, [open.length, cursor]);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement | null)?.tagName;
      if (e.metaKey || e.ctrlKey || e.altKey || tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
      const c = open[cursor];
      if (e.key === "j" || e.key === "ArrowDown") { e.preventDefault(); setCursor((i) => Math.min(open.length - 1, i + 1)); }
      else if (e.key === "k" || e.key === "ArrowUp") { e.preventDefault(); setCursor((i) => Math.max(0, i - 1)); }
      else if (e.key === "?") { setLegend((v) => !v); }
      else if (!c) return;
      else if (e.key === "Enter") { e.preventDefault(); convert.mutate({ id: c.id, target: c.hint.suggested, project: projectFor(c) }); }
      else if (/^[1-5]$/.test(e.key)) { const target = KEY_TARGETS[Number(e.key) - 1]; if (target === "paper" && !(c.hint.doi || c.hint.arxiv_id)) return; e.preventDefault(); convert.mutate({ id: c.id, target, project: projectFor(c) }); }
      else if (e.key === "x" || e.key === "Delete") { e.preventDefault(); triage.mutate({ id: c.id }); }
      else if (e.key === "f") { const p = projectFor(c); if (p) { e.preventDefault(); triage.mutate({ id: c.id, project: p }); } }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open, cursor, projectRows]);
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
          {legend ? <><span><kbd className="font-mono">j</kbd>/<kbd className="font-mono">k</kbd> move</span><span><kbd className="font-mono">↵</kbd> suggested</span><span><kbd className="font-mono">1</kbd> paper · <kbd className="font-mono">2</kbd> today · <kbd className="font-mono">3</kbd> note · <kbd className="font-mono">4</kbd> milestone · <kbd className="font-mono">5</kbd> decision</span><span><kbd className="font-mono">f</kbd> file</span><span><kbd className="font-mono">x</kbd> dismiss</span></> : <span>keyboard triage: j/k · ↵ · 1–5 · x</span>}
        </p>
      )}
      {open.length === 0 ? (
        <div className={`${panel} rise p-10 text-center`} style={{ ["--i" as string]: 1 }}>
          <InboxIcon className="mx-auto mb-2 h-7 w-7 text-indigo-400" aria-hidden="true" />
          <p className="font-medium text-stone-700 dark:text-stone-100">Inbox zero.</p>
          <p className="mx-auto mt-1 max-w-md text-sm text-stone-400">Capture from anywhere with ⌘K, or from Claude with the quick_capture tool. Triage here when you have a minute.</p>
        </div>
      ) : (
        <ul className="space-y-2" data-testid="inbox-list">
          {open.map((c, i) => <Row key={c.id} c={c} i={i} active={i === cursor} onFocus={() => setCursor(i)} projects={projectRows} busy={convert.isPending || triage.isPending} onConvert={(target, project) => convert.mutate({ id: c.id, target, project })} onFile={(project) => triage.mutate({ id: c.id, project })} onDismiss={() => triage.mutate({ id: c.id })} />)}
        </ul>
      )}
      {toast && (
        <div role="status" className="fixed bottom-5 right-5 z-30 flex items-center gap-3 rounded-xl border border-stone-200 bg-white px-4 py-2.5 text-sm shadow-lg dark:border-stone-700 dark:bg-stone-900 dark:text-stone-100">
          <span className="max-w-md truncate">{toast.msg}</span>{toast.url && <Link to={toast.url} className="shrink-0 font-medium text-indigo-600 hover:underline dark:text-indigo-300">open →</Link>}
        </div>
      )}
    </div>
  );
}


function Row({ c, i, active, onFocus, projects, busy, onConvert, onFile, onDismiss }: { c: Capture; i: number; active: boolean; onFocus: () => void; projects: Project[]; busy: boolean; onConvert: (target: string, project?: string) => void; onFile: (project: string) => void; onDismiss: () => void }) {
  const [project, setProject] = useState(c.project ?? projects[0]?.slug ?? "");
  useEffect(() => { if (!project && projects[0]) setProject(projects[0].slug); }, [projects, project]);
  const suggested = TARGETS.find((t) => t.key === c.hint.suggested)!;
  const chips: string[] = [];
  if (c.hint.doi) chips.push(`doi ${c.hint.doi}`);
  if (c.hint.arxiv_id) chips.push(`arXiv ${c.hint.arxiv_id}`);
  if (c.hint.url && !c.hint.doi) chips.push("link");
  return (
    <li className={`${panel} rise p-3 transition-shadow ${active ? "ring-2 ring-indigo-500/60" : ""}`} style={{ ["--i" as string]: i + 1 }} data-testid="inbox-row" data-active={active ? "1" : undefined} onMouseEnter={onFocus}>
      {/* #407: [[note]] and @cite-key mentions in a capture are links */}
      <Prose html={c.text_html} className="break-words text-sm text-stone-800 dark:text-stone-100" testId="capture-text" />
      <div className="mt-2 flex flex-wrap items-center gap-1.5 text-[11px]">
        <span className="text-stone-400">{ago(c.created_at)}</span>
        {c.processed && <span className="rounded-full bg-emerald-500/15 px-1.5 py-0.5 text-emerald-700 dark:text-emerald-300" title="Already triaged">filed</span>}
        {chips.map((ch) => <span key={ch} className="rounded-full bg-indigo-500/10 px-1.5 py-0.5 font-mono text-indigo-700 dark:text-indigo-200">{ch}</span>)}
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
          <button type="button" disabled={busy} onClick={onDismiss} title="Dismiss" className="rounded-md px-1.5 py-0.5 text-stone-400 hover:text-red-500" aria-label="Dismiss"><X className="h-3.5 w-3.5" aria-hidden="true" /></button>
        </span>
      </div>
    </li>
  );
}
