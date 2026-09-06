/** Writing studio v2 (Observatory). Board: manuscripts by status with deadline countdowns and a
 *  new-manuscript form. Studio: one page per manuscript — status pipeline, abstract, compile +
 *  word count, bibliography (add from the project's library, cite keys), cite check with one-click
 *  fixes, submission timeline. Everything here is also in the API (/manuscripts/…) and MCP. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { AlertTriangle, BookOpen, Check, Copy, ExternalLink, FileDown, Loader2, MessageSquareReply, Package, Plus, RefreshCw, Search, Trash2, X } from "lucide-react";
import { api, petReact } from "../api";
import { Skeleton, SkeletonLines } from "../../components/Skeleton";
import { ErrorState } from "../../components/ErrorState";

type Event = { id: number; kind: string; date: string; notes: string };
type MFile = { id: number; path: string; kind: string; is_main: boolean };
type Manuscript = { id: number; project: string; project_name: string; title: string; status: string; target_venue: string; deadline: string | null; abstract: string; compile_status: string; compiled_at: string | null; events: Event[]; files: MFile[] };
type Page<T> = { count: number; results: T[] };
type BibRow = { link_id: number; reference_id: number; cite_key: string; bibtex_key: string; title: string; year: number | null; authors: string; venue: string };
type CiteCheck = { cited: string[]; missing_from_bib: string[]; uncited_in_bib: string[]; matched: string[]; resolvable: Record<string, number>; tex_files: number };
type WordCount = { words: number; headers?: number; captions?: number; math?: number };
type Compile = { status: string; diagnostics: { level: string; file: string; line: number | null; message: string }[]; compiled_at: string | null; pdf_url: string | null; log: string };
type LibRef = { id: number; bibtex_key: string; title: string; year: number | null; authors: { family?: string; given?: string }[] };
type Project = { slug: string; name: string };
type ResponseProgress = { note_id: number; title: string; done: number; total: number; percent: number; app_url: string } | null;

const COLUMNS: [string, string][] = [["idea", "Idea"], ["outlining", "Outlining"], ["drafting", "Drafting"], ["internal_review", "Internal review"], ["submitted", "Submitted"], ["under_review", "Under review"], ["revision", "Revision"], ["accepted", "Accepted"], ["published", "Published"], ["shelved", "Shelved"]];
const EVENT_KINDS: [string, string][] = [["submitted", "Submitted"], ["desk_reject", "Desk reject"], ["reviews_received", "Reviews received"], ["revision_submitted", "Revision submitted"], ["accepted", "Accepted"], ["rejected", "Rejected"], ["published", "Published"], ["note", "Note"]];
const panel = "rounded-2xl border border-stone-200 bg-white dark:border-stone-800 dark:bg-stone-900";
const railH = "mb-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-stone-400 dark:text-stone-500";
const JSON_H = { "Content-Type": "application/json" };

function daysUntil(deadline: string | null): number | null {
  if (!deadline) return null;
  const due = new Date(deadline + "T00:00"); const today = new Date(); today.setHours(0, 0, 0, 0);
  return Math.round((due.getTime() - today.getTime()) / 86_400_000);
}
function deadlineLabel(deadline: string | null): { text: string; urgent: boolean } | null {
  const days = daysUntil(deadline);
  if (days === null) return null;
  if (days < 0) return { text: `${-days} d overdue`, urgent: true };
  if (days === 0) return { text: "due today", urgent: true };
  if (days <= 7) return { text: `${days} d left`, urgent: true };
  return { text: `${days} d left`, urgent: false };
}
function useDebounced<T>(value: T, ms: number): T { const [v, setV] = useState(value); useEffect(() => { const t = setTimeout(() => setV(value), ms); return () => clearTimeout(t); }, [value, ms]); return v; }

export function WritingBoard() {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data, isLoading, error, refetch } = useQuery({ queryKey: ["manuscripts"], queryFn: () => api<Page<Manuscript>>("/manuscripts/?page_size=200") });
  const projects = useQuery({ queryKey: ["projects-brief"], queryFn: () => api<Page<Project>>("/projects/?page_size=100") });
  const [title, setTitle] = useState("");
  const [project, setProject] = useState("");
  const create = useMutation({
    mutationFn: () => api<Manuscript>("/manuscripts/", { method: "POST", headers: JSON_H, body: JSON.stringify({ project, title: title.trim(), status: "idea" }) }),
    onSuccess: (m) => { queryClient.invalidateQueries({ queryKey: ["manuscripts"] }); navigate(`/manuscripts/${m.id}`); },
  });
  useEffect(() => { if (!project && projects.data?.results.length) setProject(projects.data.results[0].slug); }, [projects.data, project]);
  if (isLoading) return <div role="status" aria-label="Loading"><Skeleton className="mb-1 h-7 w-40" /><Skeleton className="mb-6 h-4 w-64" /><div className="flex gap-5">{Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-40 w-64" />)}</div></div>;
  if (error || !data) return <ErrorState message="Couldn't load manuscripts." onRetry={() => refetch()} />;
  const rows = data.results;
  const populated = COLUMNS.filter(([key]) => rows.some((m) => m.status === key));
  const soon = rows.filter((m) => { const d = daysUntil(m.deadline); return d !== null && d <= 14 && !["published", "shelved"].includes(m.status); }).sort((a, b) => (daysUntil(a.deadline)! - daysUntil(b.deadline)!));
  return (
    <div>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <h1 className="font-display text-3xl font-bold tracking-tight dark:text-stone-100">Writing {rows.length > 0 && <span className="text-gradient">· {rows.length} manuscript{rows.length === 1 ? "" : "s"}</span>}</h1>
        <p className="text-sm text-stone-400">idea → outlining → drafting → review → submitted → published</p>
      </div>
      <form onSubmit={(e) => { e.preventDefault(); if (title.trim() && project) create.mutate(); }} className={`${panel} hairline-gradient rise mb-4 flex flex-wrap items-center gap-2 p-2 pl-4`} data-testid="new-manuscript">
        <Plus className="h-4 w-4 shrink-0 text-indigo-400" aria-hidden="true" />
        <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="New manuscript — working title…" className="min-w-0 flex-1 bg-transparent py-2 text-base placeholder:text-stone-400 focus:outline-none dark:text-stone-100" aria-label="New manuscript title" />
        <select value={project} onChange={(e) => setProject(e.target.value)} className="rounded-lg border border-stone-200 bg-white px-2 py-1.5 text-sm dark:border-stone-700 dark:bg-stone-800" aria-label="Project">
          {(projects.data?.results ?? []).map((p) => <option key={p.slug} value={p.slug}>{p.name}</option>)}
        </select>
        <button type="submit" disabled={!title.trim() || !project || create.isPending} className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-40">Start</button>
      </form>
      {soon.length > 0 && (
        <div className={`${panel} rise mb-4 px-4 py-3`} style={{ ["--i" as string]: 1 }} data-testid="deadlines">
          <p className={railH}>Deadlines within two weeks</p>
          <ul className="flex flex-wrap gap-x-6 gap-y-1 text-sm">{soon.map((m) => { const dl = deadlineLabel(m.deadline)!; return <li key={m.id}><Link to={`/manuscripts/${m.id}`} className="hover:underline dark:text-stone-100">{m.title}</Link> <span className={`text-xs ${dl.urgent ? "font-medium text-red-600 dark:text-red-300" : "text-stone-400"}`}>{dl.text}</span></li>; })}</ul>
        </div>
      )}
      {rows.length === 0 ? (
        <div className={`${panel} rise p-10 text-center`} style={{ ["--i" as string]: 2 }}>
          <BookOpen className="mx-auto mb-2 h-7 w-7 text-indigo-400" aria-hidden="true" />
          <p className="mb-1 font-medium text-stone-700 dark:text-stone-100">No manuscripts yet</p>
          <p className="mx-auto max-w-md text-sm text-stone-400">A manuscript tracks one paper from idea to publication with its own bibliography, cite check, LaTeX source and submission timeline. Give it a working title above.</p>
        </div>
      ) : (
        <div className="flex gap-4 overflow-x-auto pb-4">
          {populated.map(([key, label], ci) => {
            const items = rows.filter((m) => m.status === key);
            return (
              <section key={key} className={`${panel} rise w-64 shrink-0 p-3`} style={{ ["--i" as string]: ci + 2 }}>
                <h2 className="mb-2 flex items-baseline gap-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-stone-400">{label}<span className="text-stone-300 dark:text-stone-600">{items.length}</span></h2>
                <div className="space-y-2">
                  {items.map((m) => { const dl = deadlineLabel(m.deadline); return (
                    <Link key={m.id} to={`/manuscripts/${m.id}`} className="block rounded-xl border border-stone-200 p-3 text-sm transition-colors hover:border-indigo-300 hover:bg-indigo-50/40 dark:border-stone-800 dark:hover:border-indigo-500/50 dark:hover:bg-indigo-500/10">
                      <span className="font-medium text-stone-900 dark:text-stone-100">{m.title}</span>
                      <p className="mt-1 text-xs text-stone-400">{m.project_name}{m.target_venue ? ` · ${m.target_venue}` : ""}</p>
                      {dl && <p className={`mt-1.5 text-xs ${dl.urgent ? "font-medium text-red-600 dark:text-red-300" : "text-stone-400"}`}>{dl.text}</p>}
                    </Link>
                  ); })}
                </div>
              </section>
            );
          })}
        </div>
      )}
    </div>
  );
}

export function ManuscriptDetail() {
  const { id } = useParams();
  const queryClient = useQueryClient();
  const { data: m, isLoading } = useQuery({ queryKey: ["manuscript", id], queryFn: () => api<Manuscript>(`/manuscripts/${id}/`) });
  const invalidate = () => { queryClient.invalidateQueries({ queryKey: ["manuscript", id] }); queryClient.invalidateQueries({ queryKey: ["manuscripts"] }); };
  const patch = useMutation({
    mutationFn: (body: Partial<Manuscript>) => api(`/manuscripts/${id}/`, { method: "PATCH", headers: JSON_H, body: JSON.stringify(body) }),
    onMutate: (body) => { queryClient.setQueryData<Manuscript>(["manuscript", id], (old) => (old ? { ...old, ...body } : old)); },
    onSettled: invalidate,
  });
  const [toast, setToast] = useState("");
  const flash = (msg: string) => { setToast(msg); setTimeout(() => setToast(""), 3500); };
  if (isLoading || !m) return <div role="status" aria-label="Loading" className="space-y-4"><Skeleton className="h-4 w-32" /><Skeleton className="h-7 w-2/3" /><div className={`${panel} max-w-2xl p-5`}><SkeletonLines lines={3} /></div></div>;
  const dl = deadlineLabel(m.deadline);
  const stepIndex = COLUMNS.findIndex(([k]) => k === m.status);
  return (
    <div>
      <nav className="mb-4 text-sm text-stone-500 dark:text-stone-400"><Link to="/writing" className="hover:underline">Writing</Link> / <Link to={`/projects/${m.project}`} className="hover:underline">{m.project_name}</Link> / {m.title}</nav>
      <div className="mb-2 flex flex-wrap items-center gap-3">
        <input value={m.title} onChange={(e) => patch.mutate({ title: e.target.value })} className="font-display min-w-0 flex-1 bg-transparent text-3xl font-bold tracking-tight text-stone-900 focus:outline-none dark:text-stone-100" aria-label="Manuscript title" />
        <a href={`/projects/${m.project}/writing/${m.id}/editor/`} className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700">LaTeX editor<ExternalLink className="h-3.5 w-3.5" aria-hidden="true" /></a>
      </div>
      <div className="mb-4 flex flex-wrap items-center gap-x-4 gap-y-2 text-sm text-stone-500 dark:text-stone-400">
        <label className="flex items-center gap-1.5">venue <input value={m.target_venue} onChange={(e) => patch.mutate({ target_venue: e.target.value })} placeholder="target venue" className="w-44 rounded-md border border-transparent bg-transparent px-1 py-0.5 hover:border-stone-300 focus:border-indigo-400 focus:outline-none dark:text-stone-200 dark:hover:border-stone-700" aria-label="Target venue" /></label>
        <label className="flex items-center gap-1.5">deadline <input type="date" value={m.deadline ?? ""} onChange={(e) => patch.mutate({ deadline: e.target.value || null })} className="rounded-md border border-transparent bg-transparent px-1 py-0.5 hover:border-stone-300 focus:border-indigo-400 focus:outline-none dark:text-stone-200 dark:hover:border-stone-700" aria-label="Deadline" />
          {dl && <span className={`rounded-full px-2 py-0.5 text-xs ${dl.urgent ? "bg-red-500/10 font-medium text-red-600 dark:text-red-300" : "bg-stone-100 text-stone-500 dark:bg-stone-800"}`}>{dl.text}</span>}
        </label>
      </div>
      <ol className={`${panel} rise mb-4 flex flex-wrap items-center gap-1 p-1.5`} aria-label="Status pipeline" data-testid="pipeline">
        {COLUMNS.map(([k, label], i) => (
          <li key={k}><button type="button" onClick={() => patch.mutate({ status: k })} aria-current={k === m.status ? "step" : undefined} className={`rounded-lg px-2.5 py-1 text-xs transition-colors ${k === m.status ? "bg-indigo-600 font-medium text-white" : i < stepIndex && k !== "shelved" ? "text-indigo-600 hover:bg-indigo-50 dark:text-indigo-300 dark:hover:bg-indigo-500/10" : "text-stone-500 hover:bg-stone-100 dark:text-stone-400 dark:hover:bg-stone-800"}`}>{i < stepIndex && k !== "shelved" ? <Check className="mr-1 inline h-3 w-3" aria-hidden="true" /> : null}{label}</button></li>
        ))}
      </ol>
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_minmax(0,1fr)]">
        <div className="space-y-4">
          <AbstractCard m={m} onSave={(abstract) => patch.mutate({ abstract })} />
          <CompileCard m={m} />
          <TimelineCard m={m} onChanged={invalidate} />
        </div>
        <div className="space-y-4">
          <BibliographyCard m={m} onCopied={flash} />
          <CiteCheckCard m={m} onChanged={() => queryClient.invalidateQueries({ queryKey: ["bibliography", id] })} />
        </div>
      </div>
      {toast && <div role="status" className="fixed bottom-5 right-5 z-30 rounded-xl border border-stone-200 bg-white px-4 py-2.5 text-sm shadow-lg dark:border-stone-700 dark:bg-stone-900 dark:text-stone-100">{toast}</div>}
    </div>
  );
}

function AbstractCard({ m, onSave }: { m: Manuscript; onSave: (abstract: string) => void }) {
  const [text, setText] = useState(m.abstract);
  const timer = useRef<number>(0);
  useEffect(() => { setText(m.abstract); }, [m.id]); // eslint-disable-line react-hooks/exhaustive-deps
  const words = text.trim() ? text.trim().split(/\s+/).length : 0;
  return (
    <section className={`${panel} rise p-4`} style={{ ["--i" as string]: 1 }}>
      <div className="mb-2 flex items-baseline justify-between"><p className={`${railH} mb-0`}>Abstract</p><span className="text-[11px] tabular-nums text-stone-400">{words} words{words > 250 ? " · over 250" : ""}</span></div>
      <textarea value={text} onChange={(e) => { setText(e.target.value); window.clearTimeout(timer.current); timer.current = window.setTimeout(() => onSave(e.target.value), 900); }} rows={6} placeholder="The abstract — autosaves. Aim for 150–250 words." className="w-full resize-y rounded-lg border border-stone-200 bg-stone-50 px-3 py-2 text-sm leading-relaxed placeholder:text-stone-400 focus:border-indigo-400 focus:outline-none dark:border-stone-800 dark:bg-stone-950/40 dark:text-stone-200" aria-label="Abstract" />
    </section>
  );
}

function CompileCard({ m }: { m: Manuscript }) {
  const queryClient = useQueryClient();
  const status = useQuery({ queryKey: ["compile", m.id], queryFn: () => api<Compile>(`/manuscripts/${m.id}/compile-status/`), refetchInterval: (q) => (q.state.data?.status === "running" ? 1500 : false) });
  const wc = useQuery({ queryKey: ["wordcount", m.id], queryFn: () => api<WordCount>(`/manuscripts/${m.id}/word-count/`) });
  const compile = useMutation({ mutationFn: () => api(`/manuscripts/${m.id}/compile/`, { method: "POST" }), onSettled: () => queryClient.invalidateQueries({ queryKey: ["compile", m.id] }) });
  const s = status.data;
  const main = m.files.find((f) => f.is_main);
  const errors = s?.diagnostics.filter((d) => d.level === "error").length ?? 0;
  return (
    <section className={`${panel} rise p-4`} style={{ ["--i" as string]: 2 }} data-testid="compile-card">
      <div className="mb-2 flex flex-wrap items-center gap-2">
        <p className={`${railH} mb-0`}>Source & compile</p>
        <span className="text-[11px] text-stone-400">{m.files.length} file{m.files.length === 1 ? "" : "s"}{main ? ` · main ${main.path}` : ""}</span>
        <span className="ml-auto flex items-center gap-2 text-xs">
          {s && <span className={`rounded-full px-2 py-0.5 ${s.status === "ok" ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300" : s.status === "failed" ? "bg-red-500/10 text-red-700 dark:text-red-300" : s.status === "running" ? "bg-indigo-500/10 text-indigo-700 dark:text-indigo-200" : "bg-stone-100 text-stone-500 dark:bg-stone-800"}`}>{s.status === "running" ? "compiling…" : s.status === "ok" ? "compiled" : s.status === "failed" ? `failed · ${errors} error${errors === 1 ? "" : "s"}` : "not compiled"}</span>}
          {s?.pdf_url && <a href={s.pdf_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 rounded-md border border-stone-300 px-2 py-0.5 text-stone-600 hover:border-indigo-300 dark:border-stone-700 dark:text-stone-300">PDF<ExternalLink className="h-3 w-3" aria-hidden="true" /></a>}
          <button type="button" onClick={() => compile.mutate()} disabled={compile.isPending || s?.status === "running" || (m.files.length === 0)} className="inline-flex items-center gap-1 rounded-md bg-indigo-600 px-2 py-0.5 font-medium text-white hover:bg-indigo-700 disabled:opacity-40"><RefreshCw className={`h-3 w-3 ${s?.status === "running" ? "animate-spin" : ""}`} aria-hidden="true" />Compile</button>
        </span>
      </div>
      <div className="grid grid-cols-3 gap-2 text-center">
        {[["words", wc.data?.words], ["headings", wc.data?.headers], ["captions", wc.data?.captions]].map(([k, v]) => <div key={k as string} className="rounded-xl border border-stone-100 px-2 py-2 dark:border-stone-800"><p className="font-display text-xl font-bold tabular-nums text-stone-900 dark:text-stone-100">{v ?? "–"}</p><p className="text-[10px] uppercase tracking-wider text-stone-400">{k as string}</p></div>)}
      </div>
      {s?.status === "failed" && s.diagnostics.length > 0 && (
        <ul className="mt-3 space-y-1 text-xs">{s.diagnostics.slice(0, 5).map((d, i) => <li key={i} className="flex items-start gap-1.5 text-red-600 dark:text-red-300"><AlertTriangle className="mt-0.5 h-3 w-3 shrink-0" aria-hidden="true" /><span><span className="font-mono">{d.file}{d.line ? `:${d.line}` : ""}</span> {d.message}</span></li>)}</ul>
      )}
      <p className="mt-2 flex flex-wrap items-center gap-x-3 text-[11px] text-stone-400"><span>{s?.compiled_at ? `Last compiled ${new Date(s.compiled_at).toLocaleString()}` : "Word count is approximate (LaTeX detex)."}</span><a href={`/projects/${m.project}/writing/${m.id}/editor/`} className="hover:underline">open the editor ↗</a><a href={`/projects/${m.project}/writing/${m.id}/submission.zip`} className="inline-flex items-center gap-1 hover:underline" title="arXiv-ready source + .bib"><Package className="h-3 w-3" aria-hidden="true" />submission .zip</a></p>
    </section>
  );
}

function BibliographyCard({ m, onCopied }: { m: Manuscript; onCopied: (msg: string) => void }) {
  const queryClient = useQueryClient();
  const bib = useQuery({ queryKey: ["bibliography", String(m.id)], queryFn: () => api<BibRow[]>(`/manuscripts/${m.id}/bibliography/`) });
  const [q, setQ] = useState("");
  const dq = useDebounced(q, 200);
  const lib = useQuery({ queryKey: ["lib-search", m.project, dq], queryFn: () => api<Page<LibRef>>(`/references/?project=${m.project}&q=${encodeURIComponent(dq)}&page_size=8`), enabled: dq.trim().length > 0 });
  const refresh = () => { queryClient.invalidateQueries({ queryKey: ["bibliography", String(m.id)] }); queryClient.invalidateQueries({ queryKey: ["cite-check", m.id] }); };
  const add = useMutation({ mutationFn: (reference: number) => api<BibRow[]>(`/manuscripts/${m.id}/bibliography/`, { method: "POST", headers: JSON_H, body: JSON.stringify({ reference }) }), onSuccess: () => { petReact("paper"); refresh(); setQ(""); } });
  const remove = useMutation({ mutationFn: (reference: number) => api(`/manuscripts/${m.id}/bibliography/${reference}/`, { method: "DELETE" }), onSuccess: refresh });
  const inBib = new Set((bib.data ?? []).map((r) => r.reference_id));
  const copy = async (text: string, what: string) => { await navigator.clipboard?.writeText(text); onCopied(`Copied ${what}.`); };
  return (
    <section className={`${panel} rise p-4`} style={{ ["--i" as string]: 1 }} data-testid="bibliography-card">
      <div className="mb-2 flex items-center gap-2">
        <p className={`${railH} mb-0`}>Bibliography <span className="normal-case tracking-normal text-stone-400">{bib.data?.length ?? ""}</span></p>
        <span className="ml-auto flex items-center gap-2 text-[11px]">
          {(bib.data?.length ?? 0) > 0 && <button type="button" onClick={() => copy((bib.data ?? []).map((r) => `\\cite{${r.cite_key}}`).join(" "), "all cite commands")} className="inline-flex items-center gap-1 text-stone-400 hover:text-indigo-600 dark:hover:text-indigo-300"><Copy className="h-3 w-3" aria-hidden="true" />cite all</button>}
          <a href={`/api/v1/manuscripts/${m.id}/bib/`} className="inline-flex items-center gap-1 text-stone-400 hover:text-indigo-600 dark:hover:text-indigo-300"><FileDown className="h-3 w-3" aria-hidden="true" />.bib</a>
        </span>
      </div>
      <div className="relative mb-2">
        <Search className="pointer-events-none absolute left-2.5 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-stone-400" aria-hidden="true" />
        <input value={q} onChange={(e) => setQ(e.target.value)} placeholder={`Add from ${m.project_name}'s literature — title, author, key…`} className="w-full rounded-lg border border-stone-200 bg-white py-1.5 pl-8 pr-2 text-sm placeholder:text-stone-400 focus:border-indigo-400 focus:outline-none dark:border-stone-700 dark:bg-stone-800" aria-label="Search the project's literature" />
        {dq && (
          <ul className="absolute left-0 right-0 top-full z-20 mt-1 max-h-60 overflow-auto rounded-xl border border-stone-200 bg-white shadow-xl dark:border-stone-700 dark:bg-stone-900" data-testid="lib-results">
            {(lib.data?.results ?? []).map((r) => (
              <li key={r.id} className="flex items-center gap-2 px-3 py-1.5 text-sm">
                <span className="min-w-0 flex-1 truncate"><span className="font-mono text-xs text-indigo-500">@{r.bibtex_key}</span> <span className="text-stone-700 dark:text-stone-200">{r.title}</span></span>
                {inBib.has(r.id) ? <span className="text-[11px] text-stone-400">in bib</span> : <button type="button" onClick={() => add.mutate(r.id)} className="inline-flex items-center gap-0.5 rounded-md bg-indigo-600 px-2 py-0.5 text-[11px] font-medium text-white hover:bg-indigo-700"><Plus className="h-3 w-3" aria-hidden="true" />Add</button>}
              </li>
            ))}
            {lib.data && lib.data.results.length === 0 && <li className="px-3 py-2 text-xs text-stone-400">Nothing in this project's literature matches — file it from the Library first.</li>}
          </ul>
        )}
      </div>
      {bib.data && bib.data.length === 0 && <p className="text-xs text-stone-400">Empty — search above to add the papers this manuscript cites. The cite check below tells you which keys the LaTeX uses.</p>}
      <ul className="divide-y divide-stone-100 dark:divide-stone-800">
        {(bib.data ?? []).map((r) => (
          <li key={r.link_id} className="group flex items-center gap-2 py-1.5 text-sm">
            <button type="button" onClick={() => copy(`\\cite{${r.cite_key}}`, `\\cite{${r.cite_key}}`)} className="shrink-0 rounded-md bg-stone-100 px-1.5 py-0.5 font-mono text-[11px] text-stone-600 hover:bg-indigo-500/15 hover:text-indigo-700 dark:bg-stone-800 dark:text-stone-300" title="Copy \\cite{…}">{r.cite_key}</button>
            <Link to={`/references/${r.reference_id}`} className="min-w-0 flex-1 truncate text-stone-700 hover:text-indigo-700 dark:text-stone-200 dark:hover:text-indigo-300" title={r.title}>{r.title}</Link>
            <span className="shrink-0 text-[11px] text-stone-400">{[r.authors, r.year].filter(Boolean).join(" ")}</span>
            <button type="button" onClick={() => remove.mutate(r.reference_id)} aria-label={`Remove ${r.cite_key}`} className="text-stone-300 opacity-0 hover:text-red-500 group-hover:opacity-100"><X className="h-3.5 w-3.5" aria-hidden="true" /></button>
          </li>
        ))}
      </ul>
    </section>
  );
}

function CiteCheckCard({ m, onChanged }: { m: Manuscript; onChanged: () => void }) {
  const queryClient = useQueryClient();
  const check = useQuery({ queryKey: ["cite-check", m.id], queryFn: () => api<CiteCheck>(`/manuscripts/${m.id}/cite-check/`) });
  const refresh = () => { queryClient.invalidateQueries({ queryKey: ["cite-check", m.id] }); onChanged(); };
  const add = useMutation({ mutationFn: (reference: number) => api(`/manuscripts/${m.id}/bibliography/`, { method: "POST", headers: JSON_H, body: JSON.stringify({ reference }) }), onSuccess: refresh });
  const c = check.data;
  const clean = c && c.missing_from_bib.length === 0 && c.uncited_in_bib.length === 0;
  return (
    <section className={`${panel} rise p-4`} style={{ ["--i" as string]: 2 }} data-testid="cite-check-card">
      <div className="mb-2 flex items-center gap-2">
        <p className={`${railH} mb-0`}>Cite check</p>
        {c && <span className="text-[11px] text-stone-400">{c.cited.length} key{c.cited.length === 1 ? "" : "s"} in {c.tex_files || "the"} .tex {c.tex_files === 1 ? "file" : c.tex_files ? "files" : "source"}</span>}
        <button type="button" onClick={() => check.refetch()} className="ml-auto text-[11px] text-stone-400 hover:text-indigo-600 dark:hover:text-indigo-300" aria-label="Re-run the cite check"><RefreshCw className={`h-3.5 w-3.5 ${check.isFetching ? "animate-spin" : ""}`} aria-hidden="true" /></button>
      </div>
      {check.isLoading && <p className="text-xs text-stone-400">Checking…</p>}
      {c && c.cited.length === 0 && c.uncited_in_bib.length === 0 && <p className="text-xs text-stone-400">No \cite commands yet — write in the editor and the check runs on every visit.</p>}
      {clean && c.cited.length > 0 && <p className="flex items-center gap-1.5 text-sm text-emerald-600 dark:text-emerald-300"><Check className="h-4 w-4" aria-hidden="true" />Every citation is in the bibliography and every entry is cited.</p>}
      {c && c.missing_from_bib.length > 0 && (
        <div className="mb-2">
          <p className="text-xs font-medium text-red-600 dark:text-red-300">Cited but not in the bibliography · {c.missing_from_bib.length}</p>
          <ul className="mt-1 space-y-1 text-sm">{c.missing_from_bib.map((k) => <li key={k} className="flex items-center gap-2"><span className="font-mono text-xs text-stone-700 dark:text-stone-200">{k}</span>{c.resolvable[k] ? <button type="button" onClick={() => add.mutate(c.resolvable[k])} className="inline-flex items-center gap-0.5 rounded-md bg-indigo-600 px-2 py-0.5 text-[11px] font-medium text-white hover:bg-indigo-700"><Plus className="h-3 w-3" aria-hidden="true" />Add from library</button> : <span className="text-[11px] text-stone-400">not in the library — add it by DOI first</span>}</li>)}</ul>
        </div>
      )}
      {c && c.uncited_in_bib.length > 0 && (
        <div>
          <p className="text-xs font-medium text-amber-600 dark:text-amber-300">In the bibliography but never cited · {c.uncited_in_bib.length}</p>
          <p className="mt-1 font-mono text-xs text-stone-500 dark:text-stone-400">{c.uncited_in_bib.join(", ")}</p>
        </div>
      )}
    </section>
  );
}

function TimelineCard({ m, onChanged }: { m: Manuscript; onChanged: () => void }) {
  const queryClient = useQueryClient();
  const [kind, setKind] = useState("submitted");
  const [date, setDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [notes, setNotes] = useState("");
  const [reviewText, setReviewText] = useState("");
  const progress = useQuery({ queryKey: ["response-progress", m.id], queryFn: () => api<{ progress: ResponseProgress }>(`/manuscripts/${m.id}/response-progress/`).then((r) => r.progress) });
  const add = useMutation({
    mutationFn: () => kind === "reviews_received"
      ? api<{ points: number; note: { id: number; app_url: string } }>(`/manuscripts/${m.id}/reviews/`, { method: "POST", headers: JSON_H, body: JSON.stringify({ text: reviewText, date, notes }) })
      : api(`/manuscripts/${m.id}/events/`, { method: "POST", headers: JSON_H, body: JSON.stringify({ kind, date, notes }) }),
    onSuccess: () => { setNotes(""); setReviewText(""); queryClient.invalidateQueries({ queryKey: ["response-progress", m.id] }); queryClient.invalidateQueries({ queryKey: ["notes"] }); onChanged(); },
  });
  const pr = progress.data;
  const remove = useMutation({ mutationFn: (eventId: number) => api(`/manuscripts/${m.id}/events/${eventId}/`, { method: "DELETE" }), onSuccess: onChanged });
  return (
    <section className={`${panel} rise p-4`} style={{ ["--i" as string]: 3 }} data-testid="timeline-card">
      <p className={railH}>Submission timeline</p>
      {m.events.length === 0 ? <p className="mb-3 text-xs text-stone-400">Nothing logged yet — submissions, reviews, decisions and notes build the story of this paper.</p> : (
        <ol className="relative mb-3 space-y-3 border-l border-stone-200 pl-4 dark:border-stone-700">
          {m.events.map((e) => (
            <li key={e.id} className="group text-sm">
              <span className={`absolute -left-[5px] mt-1.5 h-2.5 w-2.5 rounded-full ${e.kind === "accepted" || e.kind === "published" ? "bg-emerald-500" : e.kind === "rejected" || e.kind === "desk_reject" ? "bg-red-500" : "bg-indigo-500"}`} />
              <div className="flex items-baseline gap-2"><span className="font-medium capitalize text-stone-900 dark:text-stone-100">{e.kind.replace(/_/g, " ")}</span><span className="text-xs text-stone-400">{e.date}</span><button type="button" onClick={() => remove.mutate(e.id)} aria-label="Delete event" className="ml-auto text-stone-300 opacity-0 hover:text-red-500 group-hover:opacity-100"><Trash2 className="h-3 w-3" aria-hidden="true" /></button></div>
              {e.notes && <p className="mt-0.5 text-xs leading-relaxed text-stone-500 dark:text-stone-400">{e.notes}</p>}
            </li>
          ))}
        </ol>
      )}
      {pr && (
        <div className="mb-3 rounded-xl border border-indigo-500/20 bg-indigo-500/5 px-3 py-2" data-testid="response-progress">
          <div className="flex items-center gap-2 text-xs">
            <MessageSquareReply className="h-3.5 w-3.5 text-indigo-500" aria-hidden="true" />
            <Link to={pr.app_url} className="min-w-0 flex-1 truncate font-medium text-stone-800 hover:text-indigo-700 dark:text-stone-100 dark:hover:text-indigo-300" title={pr.title}>Response to reviewers</Link>
            <span className="tabular-nums text-stone-500 dark:text-stone-300">{pr.done}/{pr.total} points answered</span>
          </div>
          <div className="mt-1.5 h-1.5 w-full overflow-hidden rounded-full bg-stone-100 dark:bg-stone-800"><div className="h-1.5 rounded-full bg-indigo-500 transition-[width] duration-500" style={{ width: `${pr.percent}%` }} /></div>
        </div>
      )}
      {kind === "reviews_received" && (
        <textarea value={reviewText} onChange={(e) => setReviewText(e.target.value)} rows={5} placeholder={"Paste the reviews here. 'Reviewer 1' headings and numbered points become a point-by-point response note with a checkbox per point."} className="mb-2 w-full resize-y rounded-lg border border-stone-200 bg-stone-50 px-3 py-2 text-xs leading-relaxed placeholder:text-stone-400 focus:border-indigo-400 focus:outline-none dark:border-stone-800 dark:bg-stone-950/40 dark:text-stone-200" aria-label="Reviews received" data-testid="reviews-text" />
      )}
      <form onSubmit={(e) => { e.preventDefault(); add.mutate(); }} className="flex flex-wrap items-center gap-2 text-xs">
        <select value={kind} onChange={(e) => setKind(e.target.value)} className="rounded-md border border-stone-200 bg-white px-2 py-1 dark:border-stone-700 dark:bg-stone-800" aria-label="Event kind">{EVENT_KINDS.map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>
        <input type="date" value={date} onChange={(e) => setDate(e.target.value)} className="rounded-md border border-stone-200 bg-white px-2 py-1 dark:border-stone-700 dark:bg-stone-800" aria-label="Event date" />
        <input value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="notes (optional)" className="min-w-0 flex-1 rounded-md border border-stone-200 bg-white px-2 py-1 dark:border-stone-700 dark:bg-stone-800" aria-label="Event notes" />
        <button type="submit" disabled={add.isPending} className="inline-flex items-center gap-1 rounded-md bg-indigo-600 px-2 py-1 font-medium text-white hover:bg-indigo-700 disabled:opacity-40">{add.isPending ? <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" /> : <Plus className="h-3 w-3" aria-hidden="true" />}Log</button>
      </form>
    </section>
  );
}
