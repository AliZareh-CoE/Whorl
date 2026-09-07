/** Global search v2 (Observatory): one box, mixed results grouped by kind, each hit explained —
 *  the matching passage (for papers, the PDF page), where it lives, and a link that opens it in
 *  the app. ↑↓ moves, Enter opens. URL keeps ?q= so a search is shareable. API: /search/?q=. */
import { useQuery } from "@tanstack/react-query";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { FileText, Search as SearchIcon, Star, X } from "lucide-react";
import { api } from "../api";
import { ErrorState } from "../../components/ErrorState";

type Result = { type: string; id: number; label: string; project: string | null; project_name: string | null; url: string | null; app_url: string | null; snippet: string; page: number | null; where: string; meta: string };
const ORDER = ["reference", "note", "project", "manuscript", "decision", "phase", "milestone", "document", "hypothesis", "experiment", "protocol", "dataset", "question", "capture"];
const LABEL: Record<string, string> = { reference: "Papers", note: "Notes", project: "Projects", manuscript: "Manuscripts", decision: "Decisions", phase: "Phases", milestone: "Milestones", document: "Documents", hypothesis: "Hypotheses", experiment: "Experiments", protocol: "Protocols", dataset: "Datasets", question: "Questions", capture: "Captures" };
const TONE: Record<string, string> = { reference: "bg-indigo-500/15 text-indigo-700 dark:text-indigo-200", note: "bg-amber-500/15 text-amber-700 dark:text-amber-300", project: "bg-stone-100 text-stone-600 dark:bg-stone-800 dark:text-stone-300", manuscript: "bg-rose-500/15 text-rose-700 dark:text-rose-300", decision: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300", phase: "bg-violet-500/15 text-violet-700 dark:text-violet-300", milestone: "bg-violet-500/15 text-violet-700 dark:text-violet-300", document: "bg-sky-500/15 text-sky-700 dark:text-sky-300" };
const panel = "rounded-2xl border border-stone-200 bg-white dark:border-stone-800 dark:bg-stone-900";

// #435 (backlog #55): recent and pinned searches live in this browser (like the library view
// mode) — a convenience, not data; the search itself is the URL and the API.
const RECENTS_KEY = "atlas-search-recents", PINS_KEY = "atlas-search-pins", RECENTS_MAX = 8;
function loadList(key: string): string[] { try { const v = JSON.parse(localStorage.getItem(key) ?? "[]"); return Array.isArray(v) ? v.filter((x) => typeof x === "string") : []; } catch { return []; } }
function saveList(key: string, list: string[]) { try { localStorage.setItem(key, JSON.stringify(list)); } catch { /* private mode etc. */ } }

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
  const [recents, setRecents] = useState<string[]>(() => loadList(RECENTS_KEY));
  const [pins, setPins] = useState<string[]>(() => loadList(PINS_KEY));
  const term = dq.trim();
  useEffect(() => {
    if (!data || term.length <= 1 || !data.results.length || (data.query !== term && data.query !== dq)) return; // only searches that found something
    setRecents((r) => { const next = [term, ...r.filter((x) => x.toLowerCase() !== term.toLowerCase())].slice(0, RECENTS_MAX); saveList(RECENTS_KEY, next); return next; });
  }, [data, term, dq]);
  const pinned = pins.some((p) => p.toLowerCase() === term.toLowerCase());
  const togglePin = () => { if (!term) return; setPins((p) => { const next = pinned ? p.filter((x) => x.toLowerCase() !== term.toLowerCase()) : [...p, term]; saveList(PINS_KEY, next); return next; }); };
  const unpin = (t: string) => setPins((p) => { const next = p.filter((x) => x !== t); saveList(PINS_KEY, next); return next; });
  const clearRecents = () => { setRecents([]); saveList(RECENTS_KEY, []); };
  const runSaved = (t: string) => { setQ(t); inputRef.current?.focus(); };
  const idle = term.length <= 1;
  const recentOnly = recents.filter((r) => !pins.some((p) => p.toLowerCase() === r.toLowerCase()));
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
        {term.length > 1 && (
          <button type="button" onClick={togglePin} aria-pressed={pinned} title={pinned ? "Unpin this search" : "Pin this search"} data-testid="search-pin" className={`absolute right-3 top-1/2 -translate-y-1/2 rounded-md p-1 transition-colors ${pinned ? "text-amber-500" : "text-stone-300 hover:text-amber-500 dark:text-stone-600"}`}>
            <Star className="h-4 w-4" aria-hidden="true" fill={pinned ? "currentColor" : "none"} />
          </button>
        )}
        <input ref={inputRef} type="search" value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={onKey} placeholder="What are you looking for?" aria-label="Search" className="w-full bg-transparent py-2 pl-7 pr-9 text-base placeholder:text-stone-400 focus:outline-none dark:text-stone-100" />
      </div>
      {error && <ErrorState message="Search failed." onRetry={() => refetch()} />}
      {idle && (pins.length > 0 || recentOnly.length > 0) && (
        <div className="mb-4 space-y-2" data-testid="search-saved">
          {pins.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5 text-xs">
              <span className="mr-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-stone-400">Pinned</span>
              {pins.map((t) => (
                <span key={t} className="inline-flex items-center overflow-hidden rounded-full border border-amber-300/60 bg-amber-500/10 text-amber-800 dark:border-amber-500/40 dark:text-amber-200" data-testid="search-pinned">
                  <button type="button" onClick={() => runSaved(t)} className="px-2.5 py-1 hover:underline">{t}</button>
                  <button type="button" onClick={() => unpin(t)} aria-label={`Unpin ${t}`} className="pr-1.5 text-amber-500/70 hover:text-amber-700"><X className="h-3 w-3" aria-hidden="true" /></button>
                </span>
              ))}
            </div>
          )}
          {recentOnly.length > 0 && (
            <div className="flex flex-wrap items-center gap-1.5 text-xs">
              <span className="mr-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-stone-400">Recent</span>
              {recentOnly.map((t) => <button key={t} type="button" onClick={() => runSaved(t)} className="rounded-full border border-stone-200 px-2.5 py-1 text-stone-600 hover:border-indigo-300 hover:text-indigo-600 dark:border-stone-700 dark:text-stone-300 dark:hover:text-indigo-300" data-testid="search-recent">{t}</button>)}
              <button type="button" onClick={clearRecents} className="ml-1 text-stone-400 hover:underline">clear</button>
            </div>
          )}
        </div>
      )}
      {idle && <p className="text-sm text-stone-400">Type at least two characters. ↑↓ moves through the hits, Enter opens{term.length > 1 ? "" : "; ☆ pins a search you keep coming back to"}.</p>}
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
