/** Inbox v2 (Observatory): capture anything, triage it into a first-class object. Every row
 *  shows what Atlas detected (a DOI → paper, "todo:" → Today, "decision:" → decision log …) and
 *  converts in one click; filing to a project and dismissing stay one click too.
 *  API: /quick-capture/ (hint per item), /quick-capture/{id}/convert/; MCP list_inbox, convert_capture. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { BookOpen, Check, FileText, Flag, Inbox as InboxIcon, ListChecks, Scale, X } from "lucide-react";
import { api, petReact } from "../api";
import { ErrorState } from "../../components/ErrorState";
import { Skeleton } from "../../components/Skeleton";

type Hint = { suggested: "paper" | "note" | "todo" | "milestone" | "decision"; doi: string; arxiv_id: string; url: string; title: string };
type Capture = { id: number; text: string; processed: boolean; project: string | null; hint: Hint; created_at: string };
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
  const { data, isLoading, error, refetch } = useQuery({ queryKey: ["inbox"], queryFn: () => api<Page<Capture>>("/quick-capture/?page_size=200") });
  const { data: projects } = useQuery({ queryKey: ["projects-brief"], queryFn: () => api<Page<Project>>("/projects/?page_size=100") });
  const refresh = () => { queryClient.invalidateQueries({ queryKey: ["inbox"] }); queryClient.invalidateQueries({ queryKey: ["dashboard"] }); queryClient.invalidateQueries({ queryKey: ["todos"] }); };
  const capture = useMutation({
    mutationFn: () => api("/quick-capture/", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ text }) }),
    onSuccess: () => { setText(""); petReact("capture"); refresh(); },
  });
  const triage = useMutation({
    mutationFn: ({ id, project }: { id: number; project?: string }) => api(`/quick-capture/${id}/`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(project ? { processed: true, project } : { processed: true }) }),
    onMutate: ({ id }) => { queryClient.setQueryData<Page<Capture>>(["inbox"], (old) => old ? { ...old, results: old.results.map((c) => (c.id === id ? { ...c, processed: true } : c)) } : old); },
    onSettled: refresh,
  });
  const convert = useMutation({
    mutationFn: ({ id, target, project }: { id: number; target: string; project?: string }) => api<Converted>(`/quick-capture/${id}/convert/`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(project ? { target, project } : { target }) }),
    onMutate: ({ id }) => { queryClient.setQueryData<Page<Capture>>(["inbox"], (old) => old ? { ...old, results: old.results.map((c) => (c.id === id ? { ...c, processed: true } : c)) } : old); },
    onSuccess: (out) => { refresh(); if (out.kind === "reference") petReact("paper"); if (out.kind === "note") petReact("note"); flash(`${out.kind === "reference" ? (out.created ? "Added the paper" : "Paper already in the library") : out.kind === "todo" ? "On today's list" : `Created the ${out.kind}`}: ${out.title}`, out.app_url); },
    onError: (e) => { refresh(); flash(`Could not convert — ${(e as Error).message}`); },
  });

  if (isLoading) return <div className="mx-auto max-w-3xl"><Skeleton className="mb-4 h-8 w-40" /><Skeleton className="mb-6 h-24 w-full" /><Skeleton className="h-40 w-full" /></div>;
  if (error || !data) return <ErrorState message="Couldn't load the inbox." onRetry={() => refetch()} />;
  const open = data.results.filter((c) => !c.processed);
  const projectRows = projects?.results ?? [];
  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-4">
        <h1 className="font-display text-3xl font-bold tracking-tight dark:text-stone-100">Inbox <span className="text-gradient">{open.length === 0 ? "· zero" : `· ${open.length} to triage`}</span></h1>
        <p className="mt-0.5 text-sm text-stone-400">Get it out of your head now. Atlas reads DOIs, "todo:", "idea:", "decision:" and "milestone:" and files each into the right place with one click.</p>
      </div>
      <form onSubmit={(e) => { e.preventDefault(); if (text.trim()) capture.mutate(); }} className={`${panel} hairline-gradient rise mb-6 p-2 pl-4`} data-testid="capture-form">
        <textarea value={text} onChange={(e) => setText(e.target.value)} onKeyDown={(e) => { if ((e.metaKey || e.ctrlKey) && e.key === "Enter" && text.trim()) capture.mutate(); }} rows={2} placeholder="A stray thought, a DOI, a todo: …, an idea: … — ⌘Enter captures" aria-label="Capture" className="block w-full resize-none border-0 bg-transparent py-2 text-base leading-relaxed placeholder:text-stone-400 focus:outline-none dark:text-stone-100" />
        <div className="flex items-center justify-between pt-1">
          <span className="text-[11px] text-stone-400">{text.trim() ? `Looks like a ${(() => { const t = text.trim().toLowerCase(); if (/10\.\d{4,9}\//.test(t) || /arxiv|\d{4}\.\d{4,5}/.test(t)) return "paper"; if (/^(todo|task)\s*[:\-]/.test(t)) return "todo"; if (/^decision/.test(t)) return "decision"; if (/^milestone/.test(t)) return "milestone"; if (/^(idea|note)\s*[:\-]/.test(t) || t.length > 240) return "note"; return "todo"; })()}` : "Goes straight to the inbox — file it later."}</span>
          <button type="submit" disabled={capture.isPending || !text.trim()} className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-40">{capture.isPending ? "Capturing…" : "Capture"}</button>
        </div>
      </form>

      {open.length === 0 ? (
        <div className={`${panel} rise p-10 text-center`} style={{ ["--i" as string]: 1 }}>
          <InboxIcon className="mx-auto mb-2 h-7 w-7 text-indigo-400" aria-hidden="true" />
          <p className="font-medium text-stone-700 dark:text-stone-100">Inbox zero.</p>
          <p className="mx-auto mt-1 max-w-md text-sm text-stone-400">Capture from anywhere with ⌘K, or from Claude with the quick_capture tool. Triage here when you have a minute.</p>
        </div>
      ) : (
        <ul className="space-y-2" data-testid="inbox-list">
          {open.map((c, i) => <Row key={c.id} c={c} i={i} projects={projectRows} busy={convert.isPending || triage.isPending} onConvert={(target, project) => convert.mutate({ id: c.id, target, project })} onFile={(project) => triage.mutate({ id: c.id, project })} onDismiss={() => triage.mutate({ id: c.id })} />)}
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

function Row({ c, i, projects, busy, onConvert, onFile, onDismiss }: { c: Capture; i: number; projects: Project[]; busy: boolean; onConvert: (target: string, project?: string) => void; onFile: (project: string) => void; onDismiss: () => void }) {
  const [project, setProject] = useState(c.project ?? projects[0]?.slug ?? "");
  useEffect(() => { if (!project && projects[0]) setProject(projects[0].slug); }, [projects, project]);
  const suggested = TARGETS.find((t) => t.key === c.hint.suggested)!;
  const chips: string[] = [];
  if (c.hint.doi) chips.push(`doi ${c.hint.doi}`);
  if (c.hint.arxiv_id) chips.push(`arXiv ${c.hint.arxiv_id}`);
  if (c.hint.url && !c.hint.doi) chips.push("link");
  return (
    <li className={`${panel} rise p-3`} style={{ ["--i" as string]: i + 1 }} data-testid="inbox-row">
      <p className="whitespace-pre-wrap break-words text-sm leading-relaxed text-stone-800 dark:text-stone-100">{c.text}</p>
      <div className="mt-2 flex flex-wrap items-center gap-1.5 text-[11px]">
        <span className="text-stone-400">{ago(c.created_at)}</span>
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
