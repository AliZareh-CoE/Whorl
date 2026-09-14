/** Notes v2 (Observatory) — the notes workbench: list | editor with live preview | link panel.
 *  [[ autocompletes note titles, @ autocompletes cite keys of papers filed in the project (and
 *  attaches them to the note), autosave, backlinks / unresolved / mentions, unwritten stubs.
 *  Everything here is also in the API (/notes/, /links/, /suggest/, /unwritten/, /preview/) and MCP.
 *  #502: renaming a note rewrites every [[old title]] in the project (the save reply's `relinked`
 *  says how many); "Mentions without a link" get a Link button each and "Link all".
 *  #503: "Around this note" — a small 2D force graph of the note's two-hop neighbourhood (notes and
 *  cited papers) in the link rail; click a node to open it. GET /notes/{id}/graph/?depth=.
 *  #504: #tags written in the body are collected on save; the rail lists them with counts and filters
 *  the list (?tag=), the editor header shows the note's tags, `#` autocompletes them. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { ArrowUpRight, BookOpen, CalendarDays, FileDown, FlaskConical, Plus, Search, Sparkles, Square, Trash2, Users, Volume2 } from "lucide-react";
import { api, petReact } from "../api";
import { confirmDialog } from "../../components/Dialog";
import { Skeleton } from "../../components/Skeleton";
import { ErrorState } from "../../components/ErrorState";
import MarkdownEditor from "../notes/MarkdownEditor";
import { listenTo, speakable, type Listener } from "../listen";

type Backlink = { id: number; title: string };
type RefSummary = { id: number; bibtex_key: string; title: string; year: number | null };
type Relinked = { links: number; notes: number; decisions: number; experiments: number; captures: number } | null;
type Note = { id: number; title: string; body: string; backlinks: Backlink[]; references_detail: RefSummary[]; updated_at: string; relinked?: Relinked; tags?: string[] };
type TagCount = { tag: string; count: number };
type Page<T> = { count: number; results: T[] };
type Links = { outgoing: Backlink[]; backlinks: Backlink[]; references: RefSummary[]; unresolved: string[]; unresolved_keys: string[]; mentions: Backlink[] };
type Suggestion = { id: number; label: string; sublabel: string };
type GNode = { id: string; type: "reference" | "note"; label: string; title: string; group: string; size: number; hops: number; app_url?: string; x?: number; y?: number };
type GLink = { source: string | { id: string }; target: string | { id: string }; kind: string };
type LocalGraphData = { note: { id: number; title: string }; depth: number; nodes: GNode[]; links: GLink[]; stats: { notes: number; references: number; links: number } };
declare global { interface Window { ForceGraph?: any } }
const FORCE_GRAPH_2D = "/static/vendor/forcegraph/force-graph.min.js";
function loadScript(src: string): Promise<void> {
  return new Promise((resolve, reject) => {
    if (document.querySelector(`script[src="${src}"]`)) return resolve();
    const el = document.createElement("script"); el.src = src; el.onload = () => resolve(); el.onerror = reject; document.head.appendChild(el);
  });
}
const NODE_COLORS: Record<string, string> = { to_read: "#f59e0b", skimmed: "#a5b4fc", read: "#7c6cff", annotated: "#34d399", note: "#2dd4bf" };
const LINK_COLORS: Record<string, string> = { citation: "#7c6cff", "note-link": "#2dd4bf", "note-citation": "#c084fc" };
const isDark = () => document.documentElement.classList.contains("dark");
const endId = (e: string | { id: string }) => (typeof e === "string" ? e : e.id);

const panel = "rounded-2xl border border-stone-200 bg-white dark:border-stone-800 dark:bg-stone-900";
const railH = "mb-1.5 text-[10px] font-semibold uppercase tracking-[0.14em] text-stone-400 dark:text-stone-500";

function useDebounced<T>(value: T, ms: number): T {
  const [v, setV] = useState(value);
  useEffect(() => { const t = setTimeout(() => setV(value), ms); return () => clearTimeout(t); }, [value, ms]);
  return v;
}
function ago(iso: string): string {
  const d = (Date.now() - new Date(iso).getTime()) / 60000;
  if (d < 1) return "just now"; if (d < 60) return `${Math.round(d)} min`; if (d < 1440) return `${Math.round(d / 60)} h`; return `${Math.round(d / 1440)} d`;
}

export default function NotesWorkbench() {
  const { slug, id } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const isNew = window.location.pathname.endsWith("/notes/new");
  const selectedId = id ? Number(id) : null;
  const [q, setQ] = useState("");
  const dq = useDebounced(q, 200);
  const [tag, setTag] = useState("");
  const list = useQuery({ queryKey: ["notes", slug, dq, tag], queryFn: () => api<Page<Note>>(`/notes/?project=${slug}&page_size=200${dq ? `&q=${encodeURIComponent(dq)}` : ""}${tag ? `&tag=${encodeURIComponent(tag)}` : ""}`) });
  const tagCounts = useQuery({ queryKey: ["note-tags", slug], queryFn: () => api<{ tags: TagCount[] }>(`/notes/tags/?project=${slug}`) });
  const unwritten = useQuery({ queryKey: ["notes-unwritten", slug], queryFn: () => api<{ titles: string[] }>(`/notes/unwritten/?project=${slug}`) });
  const notes = list.data?.results ?? [];
  const create = useMutation({
    mutationFn: (title: string) => api<Note>("/notes/", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ project: slug, title, body: "" }) }),
    onSuccess: (n) => { petReact("note"); queryClient.invalidateQueries({ queryKey: ["notes"] }); queryClient.invalidateQueries({ queryKey: ["notes-unwritten", slug] }); navigate(`/projects/${slug}/notes/${n.id}`); },
  });
  const remove = useMutation({
    mutationFn: (nid: number) => api(`/notes/${nid}/`, { method: "DELETE" }),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["notes"] }); queryClient.invalidateQueries({ queryKey: ["notes-unwritten", slug] }); queryClient.invalidateQueries({ queryKey: ["graph", slug] }); navigate(`/projects/${slug}/notes`); },
  });

  const fromTemplate = useMutation({
    mutationFn: (body: { kind: string; reference?: number }) => api<Note>("/notes/from-template/", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ project: slug, ...body }) }),
    onSuccess: (n) => { petReact("note"); queryClient.invalidateQueries({ queryKey: ["notes"] }); navigate(`/projects/${slug}/notes/${n.id}`); },
  });
  if (list.error) return <ErrorState message="Couldn't load notes." onRetry={() => list.refetch()} />;
  return (
    <div>
      <nav className="mb-4 text-sm text-stone-500 dark:text-stone-400">
        <Link to="/projects" className="hover:underline">Projects</Link> / <Link to={`/projects/${slug}`} className="hover:underline">{slug}</Link> / Notes
      </nav>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <h1 className="font-display text-3xl font-bold tracking-tight dark:text-stone-100">Notes {list.data && <span className="text-gradient">· {list.data.count}</span>}</h1>
        <p className="text-sm text-stone-400">the project's thinking space — <span className="font-mono text-indigo-500">[[links]]</span> between notes, <span className="font-mono text-indigo-500">@keys</span> to cite papers</p>
        <Link to={`/projects/${slug}/notes/new`} className="ml-auto inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700"><Plus className="h-4 w-4" aria-hidden="true" />New note</Link>
      </div>
      <div className="grid gap-4 lg:grid-cols-[16rem_minmax(0,1fr)]">
        <aside className={`${panel} rise flex max-h-[calc(100vh-11rem)] flex-col overflow-hidden`} style={{ ["--i" as string]: 0 }}>
          <div className="relative border-b border-stone-100 p-2 dark:border-stone-800">
            <Search className="pointer-events-none absolute left-4 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-stone-400" aria-hidden="true" />
            <input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Search notes…" className="w-full rounded-lg border border-stone-200 bg-white py-1.5 pl-7 pr-2 text-sm placeholder:text-stone-400 focus:border-indigo-400 focus:outline-none dark:border-stone-700 dark:bg-stone-800" aria-label="Search notes" />
          </div>
          {(tagCounts.data?.tags.length ?? 0) > 0 && (
            <div className="flex flex-wrap gap-1 border-b border-stone-100 px-2 py-1.5 dark:border-stone-800" data-testid="tag-rail">
              {tagCounts.data!.tags.map((t) => (
                <button key={t.tag} type="button" onClick={() => setTag(tag === t.tag ? "" : t.tag)} className={`rounded-full px-1.5 py-0.5 text-[10px] transition-colors ${tag === t.tag ? "bg-indigo-600 text-white" : "bg-stone-100 text-stone-500 hover:bg-indigo-500/10 hover:text-indigo-600 dark:bg-stone-800 dark:text-stone-400 dark:hover:text-indigo-300"}`} aria-pressed={tag === t.tag} title={`${t.count} note${t.count === 1 ? "" : "s"}`} data-testid="tag-chip">#{t.tag} <span className="opacity-70">{t.count}</span></button>
              ))}
            </div>
          )}
          <div className="flex-1 overflow-auto">
            {list.isLoading && <div className="space-y-2 p-3">{Array.from({ length: 6 }).map((_, i) => <Skeleton key={i} className="h-8 w-full" />)}</div>}
            {notes.length === 0 && !list.isLoading && <p className="p-4 text-xs text-stone-400">{tag ? `No notes tagged #${tag}.` : dq ? "No notes match." : "No notes yet — write the first one."}</p>}
            <ul className="divide-y divide-stone-100 dark:divide-stone-800">
              {notes.map((n) => (
                <li key={n.id}>
                  <Link to={`/projects/${slug}/notes/${n.id}`} className={`block px-3 py-2 transition-colors ${selectedId === n.id ? "bg-indigo-50 dark:bg-indigo-500/10" : "hover:bg-stone-50 dark:hover:bg-stone-800/60"}`} data-testid="note-row">
                    <p className="truncate text-sm font-medium text-stone-900 dark:text-stone-100">{n.title}</p>
                    <p className="mt-0.5 flex items-center gap-2 text-[11px] text-stone-400"><span className="truncate">{(n.body || "").trim().split("\n")[0].slice(0, 60) || "empty"}</span><span className="ml-auto shrink-0 tabular-nums">{ago(n.updated_at)}</span></p>
                  </Link>
                </li>
              ))}
            </ul>
            {(unwritten.data?.titles.length ?? 0) > 0 && (
              <div className="border-t border-stone-100 p-3 dark:border-stone-800" data-testid="unwritten">
                <p className={railH}><Sparkles className="mr-1 inline h-3 w-3" aria-hidden="true" />Linked but unwritten</p>
                <ul className="space-y-1">
                  {unwritten.data!.titles.map((t) => (
                    <li key={t}><button type="button" onClick={() => create.mutate(t)} className="flex w-full items-center gap-1 truncate text-left text-xs text-stone-500 hover:text-indigo-600 dark:text-stone-400 dark:hover:text-indigo-300" title="Create this note"><Plus className="h-3 w-3 shrink-0" aria-hidden="true" /><span className="truncate">{t}</span></button></li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </aside>
        {isNew ? (
          <NewNote slug={slug!} onCreate={(t) => create.mutate(t)} pending={create.isPending || fromTemplate.isPending} onTemplate={(kind, reference) => fromTemplate.mutate({ kind, reference })} />
        ) : selectedId ? (
          <Editor key={selectedId} slug={slug!} id={selectedId} onDelete={() => remove.mutate(selectedId)} onCreateStub={(t) => create.mutate(t)} />
        ) : (
          <div className={`${panel} rise flex min-h-[50vh] flex-col items-center justify-center p-10 text-center`} style={{ ["--i" as string]: 1 }}>
            <BookOpen className="mb-2 h-7 w-7 text-indigo-400" aria-hidden="true" />
            <p className="font-medium text-stone-700 dark:text-stone-100">{notes.length ? "Pick a note, or start a new one." : "Write the first note."}</p>
            <p className="mx-auto mt-1 max-w-md text-sm text-stone-400">Type <span className="font-mono">[[</span> to link another note and <span className="font-mono">@</span> to cite a paper from this project's literature. Links become the knowledge graph.</p>
            <Link to={`/projects/${slug}/notes/new`} className="mt-4 inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700"><Plus className="h-4 w-4" aria-hidden="true" />New note</Link>
          </div>
        )}
      </div>
    </div>
  );
}
export { NotesWorkbench as NotesList, NotesWorkbench as NoteEditor };

function NewNote({ slug, onCreate, pending, onTemplate }: { slug: string; onCreate: (title: string) => void; pending: boolean; onTemplate: (kind: string, reference?: number) => void }) {
  const [title, setTitle] = useState(() => new URLSearchParams(window.location.search).get("title") ?? "");
  const [paperQ, setPaperQ] = useState("");
  const dpq = useDebounced(paperQ, 150);
  const papers = useQuery({ queryKey: ["note-suggest", slug, "reference", dpq], queryFn: () => api<Suggestion[]>(`/notes/suggest/?project=${slug}&kind=reference&q=${encodeURIComponent(dpq)}`), enabled: paperQ.length > 0 });
  const tpl = "flex items-start gap-3 rounded-xl border border-stone-200 p-3 text-left transition-colors hover:border-indigo-300 hover:bg-indigo-50/40 disabled:opacity-50 dark:border-stone-800 dark:hover:border-indigo-500/50 dark:hover:bg-indigo-500/10";
  return (
    <div className={`${panel} rise p-6`} style={{ ["--i" as string]: 1 }} data-testid="new-note">
      <form onSubmit={(e) => { e.preventDefault(); if (title.trim()) onCreate(title.trim()); }}>
        <p className={railH}>New note in {slug}</p>
        <input autoFocus value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Title — e.g. Load theory: open questions" className="font-display w-full bg-transparent text-2xl font-semibold text-stone-900 placeholder:text-stone-300 focus:outline-none dark:text-stone-100 dark:placeholder:text-stone-600" aria-label="New note title" />
        <p className="mt-2 text-xs text-stone-400">Enter creates a blank note. Titles are unique per project; [[Title]] elsewhere links here.</p>
        <button type="submit" disabled={pending || !title.trim()} className="mt-3 rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-40">Create note</button>
      </form>
      <p className={`${railH} mt-6`}>Or start from a template</p>
      <div className="grid gap-2 sm:grid-cols-2" data-testid="templates">
        <div className={`${tpl} flex-col`}>
          <span className="flex items-center gap-2 text-sm font-medium text-stone-800 dark:text-stone-100"><BookOpen className="h-4 w-4 text-indigo-500" aria-hidden="true" />Literature note</span>
          <span className="text-xs text-stone-400">One paper: claims, method, limitations, relevance — its highlights come along.</span>
          <input value={paperQ} onChange={(e) => setPaperQ(e.target.value)} placeholder="Type a cite key or title…" className="mt-1 w-full rounded-md border border-stone-200 bg-white px-2 py-1 text-xs focus:border-indigo-400 focus:outline-none dark:border-stone-700 dark:bg-stone-800" aria-label="Paper for the literature note" />
          {paperQ && (
            <ul className="mt-1 max-h-32 w-full overflow-auto text-xs">
              {(papers.data ?? []).map((r) => <li key={r.id}><button type="button" disabled={pending} onClick={() => onTemplate("literature", r.id)} className="block w-full truncate rounded px-1.5 py-1 text-left hover:bg-indigo-500/10"><span className="font-mono text-indigo-500">@{r.label}</span> <span className="text-stone-500">{r.sublabel}</span></button></li>)}
              {papers.data && papers.data.length === 0 && <li className="px-1.5 py-1 text-stone-400">No paper in this project matches.</li>}
            </ul>
          )}
        </div>
        <button type="button" disabled={pending} onClick={() => onTemplate("daily")} className={tpl}><CalendarDays className="mt-0.5 h-4 w-4 shrink-0 text-indigo-500" aria-hidden="true" /><span><span className="block text-sm font-medium text-stone-800 dark:text-stone-100">Daily note</span><span className="text-xs text-stone-400">Today's page: this week's focus as checkboxes, a log, captures. One per day.</span></span></button>
        <button type="button" disabled={pending} onClick={() => onTemplate("meeting")} className={tpl}><Users className="mt-0.5 h-4 w-4 shrink-0 text-indigo-500" aria-hidden="true" /><span><span className="block text-sm font-medium text-stone-800 dark:text-stone-100">Meeting</span><span className="text-xs text-stone-400">Attendees, agenda, decisions, actions.</span></span></button>
        <button type="button" disabled={pending} onClick={() => onTemplate("experiment")} className={tpl}><FlaskConical className="mt-0.5 h-4 w-4 shrink-0 text-indigo-500" aria-hidden="true" /><span><span className="block text-sm font-medium text-stone-800 dark:text-stone-100">Experiment</span><span className="text-xs text-stone-400">Hypothesis, setup, observations, result, next step.</span></span></button>
      </div>
    </div>
  );
}

/* #503: the note's neighbourhood as a small live force graph — the note ringed in the middle,
   notes teal, papers coloured by reading status, arrows for direction; click opens the node. */
function LocalGraph({ slug, id }: { slug: string; id: number }) {
  const navigate = useNavigate();
  const boxRef = useRef<HTMLDivElement>(null);
  const graphRef = useRef<any>(null);
  const [depth, setDepth] = useState<1 | 2 | 3>(2);
  const [ready, setReady] = useState(false);
  const local = useQuery({ queryKey: ["note-graph", id, depth], queryFn: () => api<LocalGraphData>(`/notes/${id}/graph/?depth=${depth}`) });
  useEffect(() => { let alive = true; loadScript(FORCE_GRAPH_2D).then(() => { if (alive) setReady(true); }).catch(() => undefined); return () => { alive = false; }; }, []);
  const data = local.data;
  useEffect(() => {
    if (!ready || !data || !boxRef.current || !window.ForceGraph) return;
    const box = boxRef.current;
    const me = `note-${id}`;
    const g = graphRef.current ?? (graphRef.current = window.ForceGraph()(box));
    g.width(box.clientWidth).height(200)
      .backgroundColor(isDark() ? "#0b0e1a" : "#fafaf9")
      .graphData({ nodes: data.nodes.map((n) => ({ ...n })), links: data.links.map((l) => ({ source: endId(l.source), target: endId(l.target), kind: l.kind })) })
      .nodeId("id")
      .nodeLabel((n: GNode) => `${n.title}${n.type === "reference" ? ` · ${n.group.replace("_", " ")}` : ""}`)
      .nodeVal((n: GNode) => (n.id === me ? 6 : n.type === "reference" ? 2.5 : 3))
      .nodeCanvasObject((n: GNode & { x: number; y: number }, ctx: CanvasRenderingContext2D, scale: number) => {
        const r = n.id === me ? 5 : n.type === "reference" ? 3 : 3.5;
        ctx.beginPath(); ctx.arc(n.x, n.y, r, 0, 2 * Math.PI); ctx.fillStyle = n.type === "note" ? NODE_COLORS.note : NODE_COLORS[n.group] ?? "#94a3b8"; ctx.fill();
        if (n.id === me) { ctx.lineWidth = 1.5; ctx.strokeStyle = isDark() ? "#e0e7ff" : "#312e81"; ctx.stroke(); }
        if (scale > 1.4 || n.hops <= 1) { ctx.font = `${Math.max(3, 9 / scale)}px system-ui`; ctx.textAlign = "center"; ctx.fillStyle = isDark() ? "#cbd5e1" : "#44403c"; ctx.fillText(n.label.length > 22 ? `${n.label.slice(0, 21)}…` : n.label, n.x, n.y + r + 8 / scale); }
      })
      .linkColor((l: GLink) => (LINK_COLORS[l.kind] ?? "#94a3b8") + (isDark() ? "99" : "88"))
      .linkDirectionalArrowLength(2.5).linkDirectionalArrowRelPos(1).linkWidth(0.8)
      .onNodeClick((n: GNode) => { if (n.id === me) return; if (n.type === "note") navigate(`/projects/${slug}/notes/${n.id.replace("note-", "")}`); else if (n.app_url) navigate(n.app_url); })
      .cooldownTicks(80);
    g.d3Force("charge")?.strength(-60);
    const t = window.setTimeout(() => { try { g.zoomToFit(300, 34); } catch { /* not yet laid out */ } }, 500);
    return () => window.clearTimeout(t);
  }, [ready, data, id, slug, navigate]);
  useEffect(() => () => { try { graphRef.current?._destructor?.(); } catch { /* fine */ } graphRef.current = null; }, [id]);
  const s = data?.stats;
  return (
    <div className={`${panel} rise overflow-hidden`} style={{ ["--i" as string]: 5 }} data-testid="local-graph">
      <div className="flex items-center gap-2 px-4 pt-3">
        <p className={`${railH} mb-0`}>Around this note</p>
        <span className="ml-auto flex items-center gap-1 text-[10px] text-stone-400">
          {[1, 2, 3].map((d) => <button key={d} type="button" onClick={() => setDepth(d as 1 | 2 | 3)} className={`rounded px-1 ${depth === d ? "bg-indigo-500/15 text-indigo-600 dark:text-indigo-300" : "hover:text-stone-600 dark:hover:text-stone-200"}`} aria-pressed={depth === d} title={`${d} hop${d === 1 ? "" : "s"}`}>{d}</button>)}
        </span>
      </div>
      <div ref={boxRef} className="mt-1 h-[200px] w-full" aria-label="Local graph" />
      <p className="px-4 pb-2 text-[10px] text-stone-400">{s ? (s.notes + s.references === 0 ? "Nothing linked yet — [[link]] a note or @cite a paper." : `${s.notes} note${s.notes === 1 ? "" : "s"} · ${s.references} paper${s.references === 1 ? "" : "s"} within ${data!.depth} hop${data!.depth === 1 ? "" : "s"} · click to open`) : local.error ? "Couldn't load the graph." : "…"}</p>
    </div>
  );
}

function Editor({ slug, id, onDelete, onCreateStub }: { slug: string; id: number; onDelete: () => void; onCreateStub: (title: string) => void }) {
  const queryClient = useQueryClient();
  const note = useQuery({ queryKey: ["note", id], queryFn: () => api<Note>(`/notes/${id}/`) });
  const links = useQuery({ queryKey: ["note-links", id], queryFn: () => api<Links>(`/notes/${id}/links/`) });
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const bodyRef = useRef(""); bodyRef.current = body;
  const [loaded, setLoaded] = useState(false);
  const [dirty, setDirty] = useState(false);
  const [savedAt, setSavedAt] = useState<number | null>(null);
  const [exported, setExported] = useState("");
  // #412: read this note to me — chunked, prefetched playback of the markdown-stripped body
  const [listening, setListening] = useState<{ index: number; total: number } | null>(null);
  const listenerRef = useRef<Listener | null>(null);
  const stopListening = () => { listenerRef.current?.stop(); listenerRef.current = null; setListening(null); };
  useEffect(() => stopListening, [id]);
  const listen = async () => {
    if (listenerRef.current) { stopListening(); return; }
    const text = speakable(`${title}. ${bodyRef.current}`);
    if (!text) return;
    setListening({ index: 0, total: 0 });
    const l = listenTo(text, (index, total) => setListening({ index, total }));
    listenerRef.current = l;
    try { await l.done; } catch (e) { setExported(String((e as Error).message ?? e)); setTimeout(() => setExported(""), 4000); }
    finally { if (listenerRef.current === l) { listenerRef.current = null; setListening(null); } }
  };
  useEffect(() => { if (note.data && !loaded) { setTitle(note.data.title); setBody(note.data.body); setLoaded(true); } }, [note.data, loaded]);
  const debouncedBody = useDebounced(body, 500);
  const preview = useQuery({
    queryKey: ["note-preview", id, debouncedBody],
    queryFn: () => api<{ html: string }>("/notes/preview/", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ body: debouncedBody, project: slug }) }),
    enabled: loaded,
    placeholderData: (prev) => prev,
  });
  const save = useMutation({
    mutationFn: (payload: { title: string; body: string }) => api<Note>(`/notes/${id}/`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(payload) }),
    onSuccess: (saved) => {
      setDirty(false); setSavedAt(Date.now()); queryClient.invalidateQueries({ queryKey: ["notes"] }); queryClient.invalidateQueries({ queryKey: ["note-links", id] }); queryClient.invalidateQueries({ queryKey: ["notes-unwritten", slug] }); queryClient.invalidateQueries({ queryKey: ["graph", slug] }); queryClient.invalidateQueries({ queryKey: ["note-tags", slug] }); queryClient.setQueryData<Note>(["note", id], (old) => (old ? { ...old, tags: saved.tags } : old));
      // #502: a rename carried its links along — say so
      const rl = saved?.relinked;
      if (rl && rl.links > 0) { const where = [rl.notes && `${rl.notes} note${rl.notes === 1 ? "" : "s"}`, rl.decisions && `${rl.decisions} decision${rl.decisions === 1 ? "" : "s"}`, rl.experiments && `${rl.experiments} lab entr${rl.experiments === 1 ? "y" : "ies"}`, rl.captures && `${rl.captures} capture${rl.captures === 1 ? "" : "s"}`].filter(Boolean).join(", "); setExported(`Renamed — ${rl.links} link${rl.links === 1 ? "" : "s"} updated in ${where}.`); setTimeout(() => setExported(""), 5000); }
    },
  });
  const linkMentions = useMutation({
    mutationFn: (sources?: number[]) => api<{ linked: Backlink[] }>(`/notes/${id}/link-mentions/`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(sources ? { sources } : {}) }),
    onSuccess: (out) => { queryClient.invalidateQueries({ queryKey: ["note-links", id] }); queryClient.invalidateQueries({ queryKey: ["notes"] }); queryClient.invalidateQueries({ queryKey: ["graph", slug] }); setExported(out.linked.length ? `Linked from ${out.linked.map((n) => n.title).join(", ")}.` : "Nothing to link."); setTimeout(() => setExported(""), 4000); },
  });
  const timer = useRef<number>(0);
  const queueSave = useCallback((t: string, b: string) => { setDirty(true); window.clearTimeout(timer.current); timer.current = window.setTimeout(() => save.mutate({ title: t, body: b }), 1200); }, [save]);
  useEffect(() => { const onKey = (e: KeyboardEvent) => { if ((e.metaKey || e.ctrlKey) && e.key === "s") { e.preventDefault(); window.clearTimeout(timer.current); save.mutate({ title, body }); } }; window.addEventListener("keydown", onKey); return () => window.removeEventListener("keydown", onKey); }, [title, body, save]);

  const suggest = useCallback(async (kind: "note" | "reference" | "tag", q: string) => api<Suggestion[]>(`/notes/suggest/?project=${slug}&kind=${kind}&q=${encodeURIComponent(q)}`), [slug]);

  if (note.isLoading || !loaded) return <div className={`${panel} p-6`}><Skeleton className="mb-3 h-7 w-1/2" /><Skeleton className="h-64 w-full" /></div>;
  if (note.error) return <ErrorState message="Couldn't load this note." onRetry={() => note.refetch()} />;
  const L = links.data;
  return (
    <div className="grid gap-4 xl:grid-cols-[minmax(0,1fr)_17rem]">
      {exported && <div role="status" className="fixed bottom-5 right-5 z-30 rounded-xl border border-stone-200 bg-white px-4 py-2.5 text-sm shadow-lg dark:border-stone-700 dark:bg-stone-900 dark:text-stone-100">{exported}</div>}
      <div className={`${panel} rise overflow-hidden`} style={{ ["--i" as string]: 1 }} data-testid="note-editor">
        <div className="flex items-center gap-3 border-b border-stone-100 px-4 py-2 text-[11px] text-stone-400 dark:border-stone-800">
          <span className="font-mono">[[</span><span>link a note</span><span className="font-mono">@</span><span>cite a paper</span><span>· ⌘S saves</span>
          <span className="ml-auto tabular-nums" data-testid="save-state">{save.isPending ? "saving…" : dirty ? "editing…" : savedAt ? "saved" : ""}</span>
          <button type="button" onClick={() => void listen()} className={`inline-flex items-center gap-1 hover:text-indigo-600 dark:hover:text-indigo-300 ${listening ? "text-indigo-600 dark:text-indigo-300" : ""}`} title={listening ? "Stop reading" : "Read this note aloud (local voice)"} data-testid="note-listen" aria-pressed={!!listening}>
            {listening ? <Square className="h-3.5 w-3.5" aria-hidden="true" /> : <Volume2 className="h-3.5 w-3.5" aria-hidden="true" />}
            {listening ? (listening.total ? `stop · ${Math.min(listening.index + 1, listening.total)}/${listening.total}` : "stop") : "listen"}
          </button>
          <button type="button" onClick={async () => { const style = (() => { try { return localStorage.getItem("atlas-cite-style") || "apa"; } catch { return "apa"; } })(); const out = await api<{ markdown: string; references: number }>(`/notes/${id}/export/?style=${style}`); await navigator.clipboard?.writeText(out.markdown); setExported(`Copied as Markdown${out.references ? ` with ${out.references} reference${out.references === 1 ? "" : "s"} (${style.toUpperCase()})` : ""}.`); setTimeout(() => setExported(""), 3500); }} className="inline-flex items-center gap-1 hover:text-indigo-600 dark:hover:text-indigo-300" title="Copy the note as Markdown with a formatted bibliography"><FileDown className="h-3.5 w-3.5" aria-hidden="true" />export</button>
          <button type="button" onClick={async () => { if (await confirmDialog({ title: `Delete “${title}”?`, body: "Links from other notes to it become plain text.", danger: true, confirmLabel: "Delete note" })) onDelete(); }} className="inline-flex items-center gap-1 hover:text-red-500" aria-label="Delete note"><Trash2 className="h-3.5 w-3.5" aria-hidden="true" /></button>
        </div>
        <input value={title} onChange={(e) => { setTitle(e.target.value); queueSave(e.target.value, body); }} className="font-display w-full bg-transparent px-5 pt-4 text-2xl font-semibold text-stone-900 focus:outline-none dark:text-stone-100" aria-label="Note title" />
        {(note.data?.tags?.length ?? 0) > 0 && <p className="flex flex-wrap gap-1 px-5 pb-1 pt-1" data-testid="note-tags">{note.data!.tags!.map((t) => <span key={t} className="rounded-full bg-indigo-500/10 px-1.5 py-0.5 text-[10px] text-indigo-700 dark:text-indigo-300">#{t}</span>)}</p>}
        <div className="grid md:grid-cols-2">
          <div className="relative">
            <MarkdownEditor value={body} onChange={(v) => { setBody(v); queueSave(title, v); }} onSave={() => { window.clearTimeout(timer.current); save.mutate({ title, body: bodyRef.current }); }} suggest={suggest} placeholder="Write in Markdown. [[Another note]] links it; @lavie2010attention cites a paper and attaches it to this note." />
          </div>
          <div className="border-t border-stone-100 md:border-l md:border-t-0 dark:border-stone-800">
            <div className="prose prose-sm prose-stone max-w-none px-5 py-4 dark:prose-invert" data-testid="note-preview" dangerouslySetInnerHTML={{ __html: preview.data?.html ?? "" }} />
            {!body.trim() && <p className="px-5 pb-4 text-xs text-stone-400">The preview renders here as you type.</p>}
          </div>
        </div>
      </div>
      <aside className="space-y-3" data-testid="link-panel">
        <div className={`${panel} rise p-4`} style={{ ["--i" as string]: 2 }}>
          <p className={railH}>Cites</p>
          {L && L.references.length ? (
            <ul className="space-y-1 text-sm">{L.references.map((r) => <li key={r.id}><Link to={`/references/${r.id}`} className="block truncate hover:text-indigo-700 dark:text-stone-200 dark:hover:text-indigo-300" title={r.title}><span className="font-mono text-xs text-indigo-500">@{r.bibtex_key}</span> <span className="text-stone-500 dark:text-stone-400">{r.title}</span></Link></li>)}</ul>
          ) : <p className="text-xs text-stone-400">Type @ to cite a paper filed in this project.</p>}
          {L && L.unresolved_keys.length > 0 && <p className="mt-2 text-[11px] text-amber-600 dark:text-amber-300">Unknown keys: {L.unresolved_keys.map((k) => `@${k}`).join(", ")}</p>}
        </div>
        <div className={`${panel} rise p-4`} style={{ ["--i" as string]: 3 }}>
          <p className={railH}>Links out</p>
          {L && L.outgoing.length ? <ul className="space-y-1 text-sm">{L.outgoing.map((n) => <li key={n.id}><Link to={`/projects/${slug}/notes/${n.id}`} className="block truncate hover:text-indigo-700 dark:text-stone-200 dark:hover:text-indigo-300">{n.title}</Link></li>)}</ul> : <p className="text-xs text-stone-400">No [[links]] yet.</p>}
          {L && L.unresolved.length > 0 && (
            <div className="mt-2">
              <p className="text-[11px] text-stone-400">Linked but not written yet:</p>
              <ul className="mt-0.5 space-y-0.5">{L.unresolved.map((t) => <li key={t}><button type="button" onClick={() => onCreateStub(t)} className="inline-flex items-center gap-1 text-xs text-indigo-600 hover:underline dark:text-indigo-300"><Plus className="h-3 w-3" aria-hidden="true" />{t}</button></li>)}</ul>
            </div>
          )}
        </div>
        <div className={`${panel} rise p-4`} style={{ ["--i" as string]: 4 }}>
          <p className={railH}>Backlinks {L?.backlinks.length ? <span className="normal-case tracking-normal text-stone-400">{L.backlinks.length}</span> : null}</p>
          {L && L.backlinks.length ? <ul className="space-y-1 text-sm">{L.backlinks.map((n) => <li key={n.id}><Link to={`/projects/${slug}/notes/${n.id}`} className="block truncate hover:text-indigo-700 dark:text-stone-200 dark:hover:text-indigo-300">{n.title}</Link></li>)}</ul> : <p className="text-xs text-stone-400">Nothing links here yet.</p>}
          {L && L.mentions.length > 0 && (
            <div className="mt-2">
              <p className="flex items-center text-[11px] text-stone-400">Mentions without a link:{L.mentions.length > 1 && <button type="button" disabled={linkMentions.isPending} onClick={() => linkMentions.mutate(undefined)} className="ml-auto text-indigo-600 hover:underline disabled:opacity-40 dark:text-indigo-300" data-testid="link-all-mentions">Link all</button>}</p>
              <ul className="mt-0.5 space-y-0.5 text-xs">{L.mentions.map((n) => <li key={n.id} className="flex items-center gap-1"><Link to={`/projects/${slug}/notes/${n.id}`} className="inline-flex min-w-0 items-center gap-1 truncate text-stone-500 hover:text-indigo-600 dark:text-stone-400 dark:hover:text-indigo-300">{n.title}<ArrowUpRight className="h-3 w-3 shrink-0" aria-hidden="true" /></Link><button type="button" disabled={linkMentions.isPending} onClick={() => linkMentions.mutate([n.id])} className="ml-auto shrink-0 rounded border border-stone-200 px-1.5 text-[10px] text-stone-500 hover:border-indigo-300 hover:text-indigo-600 disabled:opacity-40 dark:border-stone-700 dark:text-stone-400" title="Wrap the first mention in [[ ]] so it becomes a link" data-testid="link-mention">Link</button></li>)}</ul>
            </div>
          )}
        </div>
        <LocalGraph slug={slug} id={id} />
        <p className="px-1 text-[11px] text-stone-400">Edited {note.data ? ago(note.data.updated_at) : ""} ago · <Link to={`/projects/${slug}/graph`} className="hover:underline">see the graph</Link></p>
      </aside>
    </div>
  );
}
