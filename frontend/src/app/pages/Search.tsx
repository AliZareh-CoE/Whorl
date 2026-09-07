/** Global search v2 (Observatory): one box, mixed results grouped by kind, each hit explained —
 *  the matching passage (for papers, the PDF page), where it lives, and a link that opens it in
 *  the app. ↑↓ moves, Enter opens. URL keeps ?q= so a search is shareable. API: /search/?q=. */
import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { FileText, Search as SearchIcon } from "lucide-react";
import { api } from "../api";
import { ErrorState } from "../../components/ErrorState";

type Result = { type: string; id: number; label: string; project: string | null; project_name: string | null; url: string | null; app_url: string | null; snippet: string; page: number | null; where: string; meta: string };
const ORDER = ["reference", "note", "project", "manuscript", "decision", "phase", "milestone", "document", "hypothesis", "experiment", "protocol", "dataset", "question", "capture"];
const LABEL: Record<string, string> = { reference: "Papers", note: "Notes", project: "Projects", manuscript: "Manuscripts", decision: "Decisions", phase: "Phases", milestone: "Milestones", document: "Documents", hypothesis: "Hypotheses", experiment: "Experiments", protocol: "Protocols", dataset: "Datasets", question: "Questions", capture: "Captures" };
const TONE: Record<string, string> = { reference: "bg-indigo-500/15 text-indigo-700 dark:text-indigo-200", note: "bg-amber-500/15 text-amber-700 dark:text-amber-300", project: "bg-stone-100 text-stone-600 dark:bg-stone-800 dark:text-stone-300", manuscript: "bg-rose-500/15 text-rose-700 dark:text-rose-300", decision: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300", phase: "bg-violet-500/15 text-violet-700 dark:text-violet-300", milestone: "bg-violet-500/15 text-violet-700 dark:text-violet-300", document: "bg-sky-500/15 text-sky-700 dark:text-sky-300" };
const panel = "rounded-2xl border border-stone-200 bg-white dark:border-stone-800 dark:bg-stone-900";

function useDebounced<T>(value: T, ms: number): T { const [v, setV] = useState(value); useEffect(() => { const t = setTimeout(() => setV(value), ms); return () => clearTimeout(t); }, [value, ms]); return v; }
/** Wrap the query terms in <mark> without touching the rest of the text. */
function Highlight({ text, q }: { text: string; q: string }) {
  const terms = q.split(/\s+/).map((t) => t.replace(/^["-]|"$/g, "")).filter((t) => t.length > 1);
  if (!terms.length || !text) return <>{text}</>;
  const re = new RegExp(`(${terms.map((t) => t.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")).join("|")})`, "ig");
  return <>{text.split(re).map((part, i) => (re.test(part) ? <mark key={i} className="rounded-sm bg-indigo-500/25 px-0.5 text-inherit">{part}</mark> : <span key={i}>{part}</span>))}</>;
}

export default function Search() {
  const [params, setParams] = useSearchParams();
  const navigate = useNavigate();
  const [q, setQ] = useState(params.get("q") ?? "");
  const dq = useDebounced(q, 250);
  const [cursor, setCursor] = useState(0);
  const inputRef = useRef<HTMLInputElement>(null);
  useEffect(() => { inputRef.current?.focus(); }, []);
  useEffect(() => { const next = new URLSearchParams(params); if (dq.trim()) next.set("q", dq); else next.delete("q"); setParams(next, { replace: true }); }, [dq]); // eslint-disable-line react-hooks/exhaustive-deps
  const { data, isLoading, error, refetch } = useQuery({ queryKey: ["search", dq], queryFn: () => api<{ query: string; results: Result[] }>(`/search/?q=${encodeURIComponent(dq)}`), enabled: dq.trim().length > 1, placeholderData: (p) => p });
  const groups = useMemo(() => {
    const by = new Map<string, Result[]>();
    for (const r of data?.results ?? []) by.set(r.type, [...(by.get(r.type) ?? []), r]);
    return [...by.entries()].sort((a, b) => (ORDER.indexOf(a[0]) === -1 ? 99 : ORDER.indexOf(a[0])) - (ORDER.indexOf(b[0]) === -1 ? 99 : ORDER.indexOf(b[0])));
  }, [data]);
  const flat = useMemo(() => groups.flatMap(([, rows]) => rows), [groups]);
  useEffect(() => { setCursor(0); }, [dq]);
  const open = (r: Result) => { if (r.app_url) navigate(r.app_url); else if (r.url) window.location.href = r.url; };
  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") { e.preventDefault(); setCursor((c) => Math.min(flat.length - 1, c + 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setCursor((c) => Math.max(0, c - 1)); }
    else if (e.key === "Enter" && flat[cursor]) { e.preventDefault(); open(flat[cursor]); }
  };
  return (
    <div className="mx-auto max-w-3xl">
      <h1 className="font-display mb-1 text-3xl font-bold tracking-tight dark:text-stone-100">Search {data && dq.trim().length > 1 && <span className="text-gradient">· {data.results.length} hit{data.results.length === 1 ? "" : "s"}</span>}</h1>
      <p className="mb-4 text-sm text-stone-400">Papers (title, abstract and the PDF text), notes, plans, decisions, manuscripts, documents — one box. Quote a phrase, prefix a word with - to exclude it.</p>
      <div className={`${panel} hairline-gradient rise relative mb-5 p-2 pl-4`}>
        <SearchIcon className="pointer-events-none absolute left-4 top-1/2 h-4 w-4 -translate-y-1/2 text-indigo-400" aria-hidden="true" />
        <input ref={inputRef} type="search" value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={onKey} placeholder="What are you looking for?" aria-label="Search" className="w-full bg-transparent py-2 pl-7 text-base placeholder:text-stone-400 focus:outline-none dark:text-stone-100" />
      </div>
      {error && <ErrorState message="Search failed." onRetry={() => refetch()} />}
      {dq.trim().length <= 1 && <p className="text-sm text-stone-400">Type at least two characters. ↑↓ moves through the hits, Enter opens.</p>}
      {dq.trim().length > 1 && data && data.results.length === 0 && !isLoading && (
        <div className={`${panel} rise p-10 text-center`}><p className="font-medium text-stone-700 dark:text-stone-100">Nothing matches “{dq}”.</p><p className="mt-1 text-sm text-stone-400">Typos are tolerated on titles; try a rarer word, or search inside PDFs by a phrase you remember reading.</p></div>
      )}
      <div className="space-y-4" data-testid="search-results">
        {groups.map(([type, rows], gi) => (
          <section key={type} className={`${panel} rise overflow-hidden`} style={{ ["--i" as string]: gi }}>
            <p className="flex items-baseline gap-2 border-b border-stone-100 px-4 py-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-stone-400 dark:border-stone-800"><span className={`rounded-full px-1.5 py-px ${TONE[type] ?? "bg-stone-100 text-stone-500 dark:bg-stone-800"}`}>{LABEL[type] ?? type}</span><span className="normal-case tracking-normal">{rows.length}</span></p>
            <ul className="divide-y divide-stone-100 dark:divide-stone-800">
              {rows.map((r) => {
                const idx = flat.indexOf(r);
                return (
                  <li key={`${r.type}-${r.id}`} className={`px-4 py-2.5 transition-colors ${idx === cursor ? "bg-indigo-50 dark:bg-indigo-500/10" : "hover:bg-stone-50 dark:hover:bg-stone-800/60"}`} data-testid="search-hit">
                    <div className="flex items-baseline gap-2">
                      {r.app_url ? <Link to={r.app_url} onMouseEnter={() => setCursor(idx)} className="min-w-0 flex-1 truncate text-sm font-medium text-stone-900 hover:text-indigo-700 dark:text-stone-100 dark:hover:text-indigo-300"><Highlight text={r.label} q={dq} /></Link> : <a href={r.url ?? "#"} className="min-w-0 flex-1 truncate text-sm font-medium text-stone-900 dark:text-stone-100">{r.label}</a>}
                      {r.where && <span className="inline-flex shrink-0 items-center gap-1 rounded-full bg-violet-500/15 px-1.5 py-px text-[10px] text-violet-700 dark:text-violet-200"><FileText className="h-2.5 w-2.5" aria-hidden="true" />{r.where}{r.page ? ` · p.${r.page}` : ""}</span>}
                      <span className="shrink-0 text-[11px] text-stone-400">{[r.meta, r.project_name].filter(Boolean).join(" · ")}</span>
                    </div>
                    {r.snippet && <p className="mt-0.5 line-clamp-2 text-xs leading-relaxed text-stone-500 dark:text-stone-400"><Highlight text={r.snippet} q={dq} /></p>}
                  </li>
                );
              })}
            </ul>
          </section>
        ))}
      </div>
    </div>
  );
}
