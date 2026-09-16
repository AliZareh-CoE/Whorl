/** Library v2 — the workbench (Observatory). Facets | list | detail, drop-anything import,
 *  keyboard navigation, bulk actions, metadata recovery. Everything here is also in the API
 *  (/references/, /facets/, /bulk/, /import/, /import-zotero/, /find-metadata/) and MCP. */
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import {
  Bookmark, BookOpen, Check, ChevronDown, Copy, CopyCheck, Download, Highlighter, LayoutGrid, LayoutList, Link2, MessageSquareWarning, Pencil, ShieldAlert, ShieldCheck, ArrowUpCircle, Radar, Rss, Quote, Tag as TagIcon, ExternalLink, FileDown, FileText, FolderPlus, Loader2, NotebookPen, Plus, Search, Sparkles, Telescope, Trash2, Upload, Wand2, X, VolumeX } from "lucide-react";
import { api, csrfToken, petReact } from "../api";
import { confirmDialog, errorDialog, promptDialog } from "../../components/Dialog";
import { useMenu, type MenuItem } from "../../components/Menu";
import { isDesktop, pickFolder } from "../external";
import PdfReader, { HL_COLORS, type Highlight } from "./library/PdfReader";
import { Skeleton } from "../../components/Skeleton";
import { ErrorState } from "../../components/ErrorState";

type Author = { family?: string; given?: string };
const PDF_SOURCES: Record<string, string> = { arxiv: "arXiv", unpaywall: "Unpaywall", s2: "Semantic Scholar", openalex: "OpenAlex" };
type ProjLink = { slug: string; name: string; color: string; reading_status: string; priority: string; started_at?: string | null; finished_at?: string | null };
type Progress = { page: number | null; pages: number | null; percent: number | null; last_read_at: string | null };
type ReadingNowRow = { id: number; title: string; bibtex_key: string; year: number | null; pdf: string | null; page: number; pages: number | null; percent: number | null; last_read_at: string };
const inProgress = (p?: Progress | null) => Boolean(p && p.page != null && p.page > 1 && (p.percent ?? 0) < 100);
const pageLabel = (p: { page: number | null; pages: number | null }) => `p. ${p.page}${p.pages ? ` of ${p.pages}` : ""}`;
const dayLabel = (iso: string) => new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
// #537: the softer Crossref notices on the same watch — an expression of concern or a correction
type Notice = { kind: string; notice: string; date: string | null };
const noticeWord = (n: Notice) => (n.kind === "expression_of_concern" ? "expression of concern" : "correction");
const noticeLabel = (ns: Notice[]) => (ns.some((n) => n.kind === "expression_of_concern") ? "concern" : "corrected");
const noticeTitle = (ns: Notice[]) => `Crossref lists ${ns.map((n) => `${n.kind === "expression_of_concern" ? "an" : "a"} ${noticeWord(n)}${n.date ? ` (${n.date})` : ""}`).join(", ")} — read it before citing the result`;
type Ref = {
  id: number; bibtex_key: string; title: string; authors: Author[]; year: number | null; venue: string;
  abstract: string; doi: string | null; arxiv_id: string; url: string; pdf: string | null;
  entry_type: string; citation_count: number | null; extra: Record<string, unknown>; projects: ProjLink[];
  tags: string[];
  pdf_match: boolean | null; text_status: string;
  progress: Progress;
  retraction_kind: string; retraction_notice: string; retraction_date: string | null; retraction_checked_at: string | null;
  notices: Notice[];
  preprint: boolean; published_doi: string; published_venue: string; published_checked_at: string | null; cited_by_checked_at: string | null;
  created_at: string;
};
type ReadingNote = { project_reference_id: number; project: string; project_name: string; reading_status: string; notes: string };
type SavedView = { id: number; name: string; params: Partial<Filters>; position: number };
type Page<T> = { count: number; next: string | null; results: T[] };
type Facets = {
  total: number; with_pdf: number; without_pdf: number; needs_metadata: number; retracted: number; notices: number; preprints: number; published_available: number; unfiled: number;
  years: { year: number; count: number }[]; entry_types: { entry_type: string; count: number }[];
  venues: { venue: string; count: number }[]; authors: { name: string; given: string; count: number }[]; projects: { slug: string; name: string; count: number }[];
  all_projects: { slug: string; name: string; color: string }[];
  untagged: number; tags: { id: number; name: string; color: string; count: number }[]; views: SavedView[];
  duplicates: number; new_citations: number;
};
type DupMember = { id: number; title: string; year: number | null; doi: string | null; venue: string; bibtex_key: string; has_pdf: boolean; projects: string[]; tags: string[]; score: number };
type DupGroup = { keep: number; reasons: string[]; members: DupMember[] };
// #530: the citation watch's feed — a paper outside the library that cites papers in it
type CitingRow = { id: number; openalex_id: string; doi: string; title: string; authors: string[]; year: number | null; published_on: string | null; venue: string; cited_by_count: number | null; cites: { id: number; bibtex_key: string; title: string }[]; first_seen_at: string; dismissed_at: string | null; addable: boolean; url: string };
type CitingFeed = { count: number; results: CitingRow[]; status: { new: number; dismissed: number; watched: number; unchecked: number; last_checked_at: string | null } };
// #531: journal / arXiv feeds followed inside the Library
type FeedRow = { id: number; url: string; title: string; site_url: string; project: string | null; position: number; new: number; items: number; mute: string[]; muted: number; muted_total: number; last_fetched_at: string | null; last_ok_at: string | null; last_error: string };
type FeedItemRow = { id: number; feed: { id: number; title: string }; guid: string; title: string; authors: string[]; summary: string; link: string; doi: string; arxiv_id: string; published_on: string | null; first_seen_at: string; dismissed_at: string | null; muted_at: string | null; muted_by: string; in_library: number | null; addable: boolean; url: string };
type FeedItems = { count: number; results: FeedItemRow[]; status: { feeds: number; new: number; dismissed: number; muted: number; errors: number; last_fetched_at: string | null } };
type DiscoverRow = {
  openalex_id: string; doi: string; title: string; year: number | null; venue: string; authors: string[];
  more_authors: number; citations: number | null; in_library: boolean; library_id: number | null; addable: boolean;
};
type ImportResult = { title: string; reference_id: number | null; created: boolean; source: string; error: string; needs_metadata: boolean };
type ImportSummary = { created: number; existing: number; failed: number; results: ImportResult[] };
type Filters = {
  q: string; year: string; year_min: string; year_max: string; entry_type: string; venue: string; author: string; has_pdf: string; needs_metadata: string; retracted: string; notices: string; preprints: string; published_available: string;
  project: string; unfiled: string; reading_status: string; tag: string; untagged: string; sort: string;
};

const EMPTY: Filters = { q: "", year: "", year_min: "", year_max: "", entry_type: "", venue: "", author: "", has_pdf: "", needs_metadata: "", retracted: "", notices: "", preprints: "", published_available: "", project: "", unfiled: "", reading_status: "", tag: "", untagged: "", sort: "added" };
const STYLES: [string, string][] = [["apa", "APA 7"], ["mla", "MLA 9"], ["chicago", "Chicago"], ["harvard", "Harvard"], ["vancouver", "Vancouver"], ["ieee", "IEEE"]];
function readStyle(): string { try { return localStorage.getItem("atlas-cite-style") || "apa"; } catch { return "apa"; } }
type Citation = { style: string; label: string; text: string; html: string; intext: string };
const STATUS_LABEL: Record<string, string> = { to_read: "To read", skimmed: "Skimmed", read: "Read", annotated: "Annotated" };
const panel = "rounded-2xl border border-stone-200 bg-white dark:border-stone-800 dark:bg-stone-900";
const railH = "mb-1.5 text-[10px] font-semibold uppercase tracking-[0.14em] text-stone-400 dark:text-stone-500";
const chip = (on: boolean) =>
  `flex w-full items-center justify-between rounded-md px-2 py-1 text-left text-xs transition-colors ${
    on ? "bg-indigo-50 text-indigo-700 dark:bg-indigo-500/20 dark:text-indigo-200" : "text-stone-600 hover:bg-stone-100 dark:text-stone-300 dark:hover:bg-stone-800"
  }`;

// Tag colours (#381): eight calm swatches, chosen from the rail; chips carry a tinted
// background + a dot so the name stays readable in both themes.
const TAG_PALETTE: { name: string; hex: string }[] = [
  { name: "Rose", hex: "#f43f5e" }, { name: "Amber", hex: "#f59e0b" }, { name: "Lime", hex: "#84cc16" }, { name: "Teal", hex: "#14b8a6" },
  { name: "Sky", hex: "#0ea5e9" }, { name: "Indigo", hex: "#6366f1" }, { name: "Violet", hex: "#a855f7" }, { name: "Pink", hex: "#ec4899" },
];
type TagColors = Record<string, string>;
function TagChip({ name, color, className = "", children }: { name: string; color?: string; className?: string; children?: React.ReactNode }) {
  return (
    <span data-testid="tag-chip" data-color={color || ""} style={color ? { background: `${color}33` } : undefined}
          className={`inline-flex items-center gap-1 rounded-full px-1.5 py-0.5 text-stone-600 dark:text-stone-200 ${color ? "" : "bg-stone-100 dark:bg-stone-800"} ${className}`}>
      {color && <span aria-hidden="true" className="h-1.5 w-1.5 shrink-0 rounded-full" style={{ background: color }} />}
      {name}{children}
    </span>
  );
}

// #525: export in every format colleagues use — the same rows as the view or the selection.
const EXPORT_FORMATS: [string, string, string][] = [
  ["bib", ".bib", "BibTeX — LaTeX, JabRef, and most tools"],
  ["ris", ".ris", "RIS — EndNote, Mendeley, Zotero, Web of Science"],
  ["csl", ".json", "CSL-JSON — Zotero, Paperpile, pandoc --citeproc"],
  ["csv", ".csv", "CSV — a spreadsheet with authors, year, venue, DOI, tags, projects"],
];
function ExportLinks({ query, what, className = "" }: { query: string; what: string; className?: string }) {
  return (
    <span className={`inline-flex items-center gap-1.5 text-stone-400 ${className}`} data-testid="export-links">
      <FileDown className="h-3 w-3" aria-hidden="true" />
      <span className="hidden sm:inline">Export {what}:</span>
      {EXPORT_FORMATS.map(([fmt, label, title]) => (
        <a key={fmt} href={`/api/v1/references/export/?${query}${query ? "&" : ""}fmt=${fmt}`} target="_blank" rel="noreferrer" className="rounded-sm font-mono hover:text-indigo-600 dark:hover:text-indigo-300" title={`Open ${what} as ${title}`}>{label}</a>
      ))}
    </span>
  );
}

function authorsLine(r: Ref, max = 3): string {
  const names = (r.authors ?? []).map((a) => a.family || a.given || "").filter(Boolean);
  const shown = names.slice(0, max).join(", ");
  return names.length > max ? `${shown} +${names.length - max}` : shown;
}

function useDebounced<T>(value: T, ms: number): T {
  const [v, setV] = useState(value);
  useEffect(() => { const t = setTimeout(() => setV(value), ms); return () => clearTimeout(t); }, [value, ms]);
  return v;
}

function toQuery(f: Filters, page: number): string {
  const p = new URLSearchParams();
  (Object.keys(f) as (keyof Filters)[]).forEach((k) => { if (f[k]) p.set(k, f[k]); });
  if (page > 1) p.set("page", String(page));
  return p.toString();
}
// #526: every view has an address. The address bar carries the workbench's filters (a clean
// library is a clean /library), and any /library?… link — the sidebar, ⌘K, a note, the brief,
// Claude's browse_library — sets them on arrival. Same keys as the API's list filters.
function viewQuery(f: Filters): string {
  const p = new URLSearchParams();
  (Object.keys(EMPTY) as (keyof Filters)[]).forEach((k) => { if (f[k] && !(k === "sort" && f[k] === "added")) p.set(k, f[k]); });
  return p.toString();
}
// #532: the modes have addresses too — /library?feeds=1[&feed=<id>][&seen=1][&fq=<words>],
// /library?citing=1[&reference=<id>][&seen=1], /library?duplicates=1 — so a feed, the citation
// watch or the duplicates workbench can be linked from a note, the brief, ⌘K or Claude, and the
// back button leaves the mode the way it leaves a filter. One mode at a time: feeds > citing >
// duplicates when an address names more than one.
type Mode =
  | { kind: "list" }
  | { kind: "feeds"; feed: number | null; seen: boolean; muted: boolean; fq: string }
  | { kind: "citing"; reference: number | null; seen: boolean }
  | { kind: "duplicates" };
const LIST_MODE: Mode = { kind: "list" };
function modeFromUrl(search: string): Mode {
  try {
    const p = new URLSearchParams(search);
    const id = (k: string) => { const v = Number(p.get(k)); return Number.isInteger(v) && v > 0 ? v : null; };
    if (p.get("feeds") === "1") return { kind: "feeds", feed: id("feed"), seen: p.get("seen") === "1", muted: p.get("muted") === "1", fq: (p.get("fq") ?? "").slice(0, 200) };
    if (p.get("citing") === "1") return { kind: "citing", reference: id("reference"), seen: p.get("seen") === "1" };
    if (p.get("duplicates") === "1") return { kind: "duplicates" };
  } catch { /* no URL access */ }
  return LIST_MODE;
}
function addressOf(f: Filters, m: Mode): string {
  const p = new URLSearchParams(viewQuery(f));
  if (m.kind === "feeds") { p.set("feeds", "1"); if (m.feed) p.set("feed", String(m.feed)); if (m.seen) p.set("seen", "1"); if (m.muted) p.set("muted", "1"); if (m.fq) p.set("fq", m.fq); }
  else if (m.kind === "citing") { p.set("citing", "1"); if (m.reference) p.set("reference", String(m.reference)); if (m.seen) p.set("seen", "1"); }
  else if (m.kind === "duplicates") p.set("duplicates", "1");
  return p.toString();
}
function fromUrl(search: string): Filters {
  const picked: Partial<Filters> = {};
  try {
    const p = new URLSearchParams(search);
    (Object.keys(EMPTY) as (keyof Filters)[]).forEach((k) => { const v = p.get(k); if (v) picked[k] = v.slice(0, 200); });
  } catch { /* no URL access */ }
  return { ...EMPTY, ...picked };
}
function chipLabel(k: keyof Filters, v: string): string {
  if (k === "author") return `by ${v}`;
  if (k === "year_min") return `from ${v}`;
  if (k === "year_max") return `to ${v}`;
  if (k === "retracted") return "retracted";
  if (k === "notices") return "with notices";
  if (k === "preprints") return "preprints";
  if (k === "published_available") return "published version available";
  if (k === "reading_status") return `reading status: ${STATUS_LABEL[v] ?? v}`;
  return `${k.replace("_", " ")}: ${v}`;
}

async function postForm<T>(path: string, form: FormData): Promise<T> {
  const response = await fetch(`/api/v1${path}`, { method: "POST", body: form, headers: { "X-CSRFToken": csrfToken(), Accept: "application/json" }, credentials: "same-origin" });
  if (!response.ok) throw new Error(`${response.status} on ${path}`);
  return response.json();
}

export default function Library() {
  const queryClient = useQueryClient();
  const navigate = useNavigate();
  const location = useLocation();
  const [filters, setFilters] = useState<Filters>(() => fromUrl(window.location.search));
  const [qInput, setQInput] = useState(() => fromUrl(window.location.search).q);
  const q = useDebounced(qInput, 220);
  const effective = useMemo(() => ({ ...filters, q }), [filters, q]);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [cursor, setCursor] = useState(0);
  const [detailId, setDetailId] = useState<number | null>(null);
  const [importOpen, setImportOpen] = useState(false);
  const [dragging, setDragging] = useState(false);
  const [pasted, setPasted] = useState("");
  const [importProject, setImportProject] = useState("");
  const [lastImport, setLastImport] = useState<ImportSummary | null>(null);
  const [importError, setImportError] = useState("");
  const [doi, setDoi] = useState("");
  const doiRef = useRef<HTMLInputElement>(null);
  useEffect(() => { if (new URLSearchParams(window.location.search).get("add") !== null) doiRef.current?.focus(); }, []); // #432: ⌘K "Add a paper"
  const [doiError, setDoiError] = useState("");
  const [bulkProject, setBulkProject] = useState("");
  const [citeStyle, setCiteStyleState] = useState<string>(readStyle);
  const [viewName, setViewName] = useState<string | null>(null);
  // #532: the modes start from the address too (see modeFromUrl); one mode is open at a time
  const mode0 = useRef(modeFromUrl(window.location.search)).current;
  const [dupMode, setDupMode] = useState(mode0.kind === "duplicates");
  // #530: the New citations feed (a mode like Duplicates), optionally narrowed to one paper
  const [citeMode, setCiteMode] = useState(mode0.kind === "citing");
  const [citeRef, setCiteRef] = useState<number | null>(mode0.kind === "citing" ? mode0.reference : null);
  const [showDismissed, setShowDismissed] = useState(mode0.kind === "citing" && mode0.seen);
  const openCiting = (ref: number | null) => { setCiteRef(ref); setShowDismissed(false); setDupMode(false); setFeedMode(false); setCiteMode(true); };
  // #531: the Feeds list (a mode like New citations), optionally narrowed to one feed
  const [feedMode, setFeedMode] = useState(mode0.kind === "feeds");
  const [feedId, setFeedId] = useState<number | null>(mode0.kind === "feeds" ? mode0.feed : null);
  const [showSeenFeed, setShowSeenFeed] = useState(mode0.kind === "feeds" && mode0.seen);
  // #543: the entries a feed's mute list hid, listed on request
  const [showMutedFeed, setShowMutedFeed] = useState(mode0.kind === "feeds" && mode0.muted);
  const [muteInput, setMuteInput] = useState("");
  const [feedQInput, setFeedQInput] = useState(mode0.kind === "feeds" ? mode0.fq : "");
  const feedQ = useDebounced(feedQInput, 220);
  // #532: what the address bar should say for the open mode (a feed id the rail does not know
  // — unfollowed, or someone else's — drops the narrow once the feeds arrive, not the mode)
  const mode: Mode = useMemo<Mode>(() => {
    if (feedMode) return { kind: "feeds", feed: feedId, seen: showSeenFeed, muted: showMutedFeed && !showSeenFeed, fq: feedQ };
    if (citeMode) return { kind: "citing", reference: citeRef, seen: showDismissed };
    if (dupMode) return { kind: "duplicates" };
    return LIST_MODE;
  }, [feedMode, feedId, showSeenFeed, showMutedFeed, feedQ, citeMode, citeRef, showDismissed, dupMode]);
  const applyMode = (m: Mode) => {
    setFeedMode(m.kind === "feeds"); setCiteMode(m.kind === "citing"); setDupMode(m.kind === "duplicates");
    setFeedId(m.kind === "feeds" ? m.feed : null); setShowSeenFeed(m.kind === "feeds" && m.seen); setShowMutedFeed(m.kind === "feeds" && m.muted); setFeedQInput(m.kind === "feeds" ? m.fq : "");
    setCiteRef(m.kind === "citing" ? m.reference : null); setShowDismissed(m.kind === "citing" && m.seen);
  };
  const [feedFormOpen, setFeedFormOpen] = useState(false);
  const [feedUrl, setFeedUrl] = useState("");
  const [feedError, setFeedError] = useState("");
  const openFeeds = (id: number | null) => { setFeedId(id); setShowSeenFeed(false); setShowMutedFeed(false); setDupMode(false); setCiteMode(false); setFeedMode(true); };
  const [readerId, setReaderId] = useState<number | null>(null);
  // Cards view (#397, Observatory): the same rows as cover-style cards; remembered per browser
  const [view, setView] = useState<"list" | "cards">(() => { try { return localStorage.getItem("atlas-library-view") === "cards" ? "cards" : "list"; } catch { return "list"; } });
  const switchView = (v: "list" | "cards") => { setView(v); try { localStorage.setItem("atlas-library-view", v); } catch { /* private mode */ } };
  const [hlProject, setHlProject] = useState("");
  const [jump, setJump] = useState<{ page: number; nonce: number } | null>(null);
  const [readerFind, setReaderFind] = useState("");
  // #523: the papers you are in the middle of, for the rail's "Continue reading"
  const readingNow = useQuery({ queryKey: ["reading-now"], queryFn: () => api<ReadingNowRow[]>("/references/reading-now/?limit=3"), staleTime: 60_000 });
  // #523: closing the reader drops its cached position and refreshes the bars once the last
  // page report has landed (the reader flushes it on unmount)
  const closeReader = () => { setReaderId(null); queryClient.removeQueries({ queryKey: ["progress"] }); window.setTimeout(() => { invalidate(); queryClient.invalidateQueries({ queryKey: ["reading-now"] }); }, 800); };
  const openReader = (r: Ref, find?: string) => { setReaderFind(find ?? (r.pdf_match && effective.q ? effective.q : "")); setDetailId(r.id); setReaderId(r.id); setHlProject((prev) => (r.projects.some((p) => p.slug === prev) ? prev : r.projects.length === 1 ? r.projects[0].slug : prev)); };
  const [keepChoice, setKeepChoice] = useState<Record<number, number>>({});
  const dups = useQuery({ queryKey: ["library-duplicates"], queryFn: () => api<{ groups: DupGroup[] }>("/references/duplicates/"), enabled: dupMode });
  const citingFeed = useQuery({
    queryKey: ["new-citations", showDismissed, citeRef, filters.project],
    queryFn: () => api<CitingFeed>(`/references/new-citations/?limit=200${showDismissed ? "&dismissed=1" : ""}${citeRef ? `&reference=${citeRef}` : ""}${filters.project && !citeRef ? `&project=${encodeURIComponent(filters.project)}` : ""}`),
    enabled: citeMode,
  });
  const feedsList = useQuery({ queryKey: ["feeds"], queryFn: () => api<Page<FeedRow>>("/feeds/?page_size=200").then((p) => p.results), staleTime: 30_000 });
  const feedItems = useQuery({
    queryKey: ["feed-items", feedId, showSeenFeed, showMutedFeed, feedQ, filters.project],
    queryFn: () => api<FeedItems>(`/feeds/items/?limit=200${showSeenFeed ? "&dismissed=1" : showMutedFeed ? "&muted=1" : ""}${feedId ? `&feed=${feedId}` : ""}${feedQ ? `&q=${encodeURIComponent(feedQ)}` : ""}${filters.project && !feedId ? `&project=${encodeURIComponent(filters.project)}` : ""}`),
    enabled: feedMode,
  });
  const refreshFeedQueries = () => { queryClient.invalidateQueries({ queryKey: ["feeds"] }); queryClient.invalidateQueries({ queryKey: ["feed-items"] }); };
  const followFeed = useMutation({
    // a plain fetch so the server's refusal reason ("that host is private", "answered 404",
    // "did not answer with a feed") can be shown in place instead of a bare status
    mutationFn: async (url: string) => {
      const response = await fetch("/api/v1/feeds/", { method: "POST", credentials: "same-origin", headers: { Accept: "application/json", "Content-Type": "application/json", "X-CSRFToken": csrfToken() }, body: JSON.stringify(filters.project ? { url, project: filters.project } : { url }) });
      if (!response.ok) {
        let reason = "";
        try { const body = (await response.json()) as { url?: string[]; detail?: string }; reason = body.url?.[0] ?? body.detail ?? ""; } catch { /* no body */ }
        throw new Error(reason || `The server answered ${response.status}.`);
      }
      return (await response.json()) as FeedRow;
    },
    onSuccess: (f) => { setFeedError(""); setFeedUrl(""); setFeedFormOpen(false); refreshFeedQueries(); openFeeds(f.id); flash(`Following “${f.title}” · ${f.new} new entr${f.new === 1 ? "y" : "ies"}.`); },
    onError: (e: Error) => setFeedError(e.message.charAt(0).toUpperCase() + e.message.slice(1) + (e.message.endsWith(".") ? "" : ".")),
  });
  // #543: the feed's mute list — PATCH replaces it; the server re-reads the stored entries
  const setFeedMute = useMutation({
    mutationFn: ({ id, mute }: { id: number; mute: string[] }) => api<FeedRow>(`/feeds/${id}/`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ mute }) }),
    onSuccess: (row, { mute }) => { refreshFeedQueries(); setMuteInput(""); flash(mute.length ? `Muting ${mute.length} term${mute.length === 1 ? "" : "s"} · ${row.muted} entr${row.muted === 1 ? "y" : "ies"} hidden.` : "Mute list cleared."); },
    onError: () => flash("Could not change the mute list (2–60 characters per term, at most 50)."),
  });
  const unfollowFeed = useMutation({
    mutationFn: (id: number) => api<void>(`/feeds/${id}/`, { method: "DELETE" }),
    onSuccess: () => { setFeedId(null); refreshFeedQueries(); flash("Stopped following the feed."); },
    onError: () => flash("Could not remove the feed."),
  });
  const refreshFeeds = useMutation({
    mutationFn: (ids: number[] | null) => api<{ feeds: number; new: number; seen: number; unchanged: number; errors: number; stopped: boolean; muted?: number }>("/feeds/refresh/", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(ids ? { ids } : { hours: 1, limit: 20 }) }),
    onSuccess: (out, ids) => {
      refreshFeedQueries();
      if (!ids && out.feeds === 0) { flash("Every feed was fetched in the last hour."); return; }
      flash(`Fetched ${out.feeds} feed${out.feeds === 1 ? "" : "s"} · ${out.new} new entr${out.new === 1 ? "y" : "ies"}${out.muted ? ` · ${out.muted} muted` : ""}${out.errors ? ` · ${out.errors} did not answer` : ""}.`);
    },
    onError: () => flash("Could not refresh the feeds."),
  });
  const addFeedItem = useMutation({
    mutationFn: (row: FeedItemRow) => api<Ref>("/feeds/items/add/", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(filters.project ? { id: row.id, project: filters.project } : { id: row.id }) }),
    onSuccess: (r) => { invalidate(); refreshFeedQueries(); petReact("paper"); flash(`Added “${r.title.slice(0, 60)}” to the library.`); },
    onError: () => flash("Could not add the paper — its identifier did not resolve."),
  });
  const dismissFeedItems = useMutation({
    mutationFn: ({ ids, undo }: { ids: number[]; undo?: boolean }) => api<{ changed: number }>("/feeds/items/dismiss/", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(undo ? { ids, undo: true } : { ids }) }),
    onSuccess: (out, { undo }) => { refreshFeedQueries(); flash(undo ? `Put ${out.changed} back.` : `Marked ${out.changed} as seen.`); },
    onError: () => flash("Could not update the feed."),
  });
  const highlights = useQuery({ queryKey: ["highlights", detailId], queryFn: () => api<Page<Highlight>>(`/highlights/?reference=${detailId}&page_size=200`).then((p) => p.results), enabled: detailId !== null });
  const readingNotes = useQuery({ queryKey: ["reading-notes", detailId], queryFn: () => api<ReadingNote[]>(`/references/${detailId}/reading-notes/`), enabled: detailId !== null });
  const addHighlight = useMutation({
    mutationFn: (h: { reference: number; text: string; page: number | null; color: string; project: string | null; rects?: { x: number; y: number; w: number; h: number }[] }) => api<Highlight>("/highlights/", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(h) }),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["highlights"] }); queryClient.invalidateQueries({ queryKey: ["reading-notes"] }); invalidate(); flash("Highlight saved."); },
    onError: () => flash("Could not save the highlight."),
  });
  const editHighlight = useMutation({
    mutationFn: ({ id, ...patch }: { id: number; comment?: string; color?: string }) => api<Highlight>(`/highlights/${id}/`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(patch) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["highlights"] }),
  });
  const removeHighlight = useMutation({
    mutationFn: (id: number) => api<void>(`/highlights/${id}/`, { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["highlights"] }),
  });
  const saveNotes = useMutation({
    mutationFn: ({ id, notes }: { id: number; notes: string }) => api<unknown>(`/project-references/${id}/`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ notes }) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["reading-notes"] }),
  });
  const indexText = useMutation({
    mutationFn: (id: number) => api<{ page_count: number; char_count: number; error: string }>(`/references/${id}/index-text/`, { method: "POST" }),
    onSuccess: (out) => { invalidate(); flash(out.error ? out.error : `Read ${out.page_count} page${out.page_count === 1 ? "" : "s"} into searchable text.`); },
    onError: () => flash("Could not read the PDF text."),
  });
  const litNote = useMutation({
    mutationFn: ({ reference, project }: { reference: number; project: string }) => api<{ id: number }>("/notes/from-template/", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ project, kind: "literature", reference }) }),
    onSuccess: (n, vars) => { petReact("note"); navigate(`/projects/${vars.project}/notes/${n.id}`); },
    onError: () => flash("Could not create the note."),
  });
  // Find PDF (#386): per row from the menu, with a "looking…" pill while it runs and a quiet
  // "no PDF found" pill afterwards (the outcome is kept in extra.oa_pdf by the server).
  const [pdfLookups, setPdfLookups] = useState<Set<number>>(new Set());
  const fetchPdf = useMutation({
    mutationFn: (id: number) => api<{ outcome: string; attached: boolean; pdf: string | null; source: string | null; arxiv_id: string }>(`/references/${id}/fetch-pdf/`, { method: "POST" }),
    onMutate: (id) => setPdfLookups((s) => new Set(s).add(id)),
    onSuccess: (out) => { invalidate(); flash(out.outcome); },
    onError: () => flash("The PDF lookup failed."),
    onSettled: (_o, _e, id) => setPdfLookups((s) => { const n = new Set(s); n.delete(id); return n; }),
  });
  const merge = useMutation({
    mutationFn: (body: { keep: number; merge: number[] }) => api<{ kept: number; merged: number[] }>("/references/merge/", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
    onSuccess: (out) => { invalidate(); queryClient.invalidateQueries({ queryKey: ["library-duplicates"] }); setDetailId(out.kept); flash(`Merged ${out.merged.length} duplicate(s) — links, tags, notes and PDFs kept.`); },
  });
  const [bulkTag, setBulkTag] = useState("");
  const saveView = useMutation({
    mutationFn: (name: string) => api<SavedView>("/library-views/", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name, params: { ...effective, sort: filters.sort } }) }),
    onSuccess: (v) => { setViewName(null); queryClient.invalidateQueries({ queryKey: ["library-facets"] }); flash(`Saved view “${v.name}”.`); },
  });
  // Drag to reorder the smart views (#400): the rail order is the SavedView position
  const [viewDrag, setViewDrag] = useState<{ id: number; over: number | null } | null>(null);
  const reorderViews = useMutation({
    mutationFn: (ids: number[]) => api("/library-views/reorder/", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ ids }) }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["library-facets"] }),
    onError: (e) => void errorDialog("Couldn't reorder the views", e),
  });
  const deleteView = useMutation({
    mutationFn: (id: number) => api(`/library-views/${id}/`, { method: "DELETE" }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["library-facets"] }),
  });
  const setCiteStyle = (v: string) => { setCiteStyleState(v); try { localStorage.setItem("atlas-cite-style", v); } catch { /* private mode */ } };
  const [toast, setToast] = useState("");
  const listRef = useRef<HTMLDivElement>(null);

  const facets = useQuery({ queryKey: ["library-facets"], queryFn: () => api<Facets>("/references/facets/") });
  const list = useInfiniteQuery({
    queryKey: ["library", effective],
    queryFn: ({ pageParam }) => api<Page<Ref>>(`/references/?${toQuery(effective, pageParam as number)}`),
    initialPageParam: 1,
    getNextPageParam: (last, pages) => (last.next ? pages.length + 1 : undefined),
  });
  const rows = useMemo(() => list.data?.pages.flatMap((p) => p.results) ?? [], [list.data]);
  const reader = useMemo(() => rows.find((r) => r.id === readerId) ?? null, [rows, readerId]);
  // Comment markers in the reader's margin (#396): the paper's comments, anchored by page
  const readerComments = useQuery({ queryKey: ["comments", "reference", String(readerId)], queryFn: () => api<{ comments: { id: number; body: string; line: number | null }[] }>(`/comments/reference/${readerId}/`), enabled: readerId !== null });
  const addPageComment = useMutation({
    mutationFn: ({ id, body, page }: { id: number; body: string; page: number }) => api(`/comments/reference/${id}/`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ body, line: page }) }),
    onSuccess: (_o, vars) => { queryClient.invalidateQueries({ queryKey: ["comments", "reference", String(vars.id)] }); flash(`Comment saved on p.${vars.page}`); },
    onError: (e) => void errorDialog("Couldn't save the comment", e),
  });
  const commentOnPage = async (page: number) => {
    if (!reader) return;
    const existing = (readerComments.data?.comments ?? []).filter((c) => c.line === page);
    const body = await promptDialog({ title: `Comment on page ${page}`, multiline: true, placeholder: "A thought, a caveat, a to-do for this page…", confirmLabel: "Save comment", body: existing.length ? <ul className="mb-2 max-h-40 space-y-1 overflow-auto text-xs text-stone-500">{existing.map((c) => <li key={c.id}>· {c.body}</li>)}</ul> : undefined });
    if (body && body.trim()) addPageComment.mutate({ id: reader.id, body: body.trim(), page });
  };
  // deep link: /library?q=<key>&read=<id> opens the reader on that paper once the rows arrive
  const readParam = useRef<number | null>((() => { try { const v = new URLSearchParams(window.location.search).get("read"); return v ? Number(v) : null; } catch { return null; } })());
  useEffect(() => {
    const id = readParam.current;
    if (id === null || rows.length === 0) return;
    const row = rows.find((r) => r.id === id);
    if (row?.pdf) { readParam.current = null; openReader(row); }
    else if (row) { readParam.current = null; setDetailId(row.id); }
  }, [rows, location.search]); // eslint-disable-line react-hooks/exhaustive-deps
  // #526: the URL follows the filters (replace, so the back button leaves the page, not the
  // filter history), and an address that is not the one we wrote — the sidebar's /library, a
  // link from ⌘K, a note, the brief or Claude — resets the filters, q, and the read/add asks.
  const lastWritten = useRef<string | null>(null);
  useEffect(() => {
    const current = location.search.replace(/^\?/, "");
    if (lastWritten.current === null) { lastWritten.current = addressOf(fromUrl(location.search), modeFromUrl(location.search)); return; } // the mount: state came from this address
    if (current === lastWritten.current) return;
    const next = fromUrl(location.search);
    const nextMode = modeFromUrl(location.search);
    lastWritten.current = addressOf(next, nextMode);
    try {
      const p = new URLSearchParams(location.search);
      const r = p.get("read"); if (r) readParam.current = Number(r);
      if (p.get("add") !== null) doiRef.current?.focus();
    } catch { /* no URL access */ }
    setFilters(next); setQInput(next.q); applyMode(nextMode);
  }, [location.search]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (qInput !== q || feedQInput !== feedQ) return; // let the debounce settle so a keystroke is not a route change
    const qs = addressOf(effective, mode);
    if (qs === lastWritten.current) return;
    lastWritten.current = qs;
    navigate(qs ? `/library?${qs}` : "/library", { replace: true });
  }, [effective, qInput, q, mode, feedQInput, feedQ]); // eslint-disable-line react-hooks/exhaustive-deps
  // #532: a narrow to a feed the rail does not list (unfollowed, or a link from another
  // library) widens to every feed; the address follows.
  useEffect(() => {
    if (feedMode && feedId !== null && feedsList.data && !feedsList.data.some((f) => f.id === feedId)) setFeedId(null);
  }, [feedMode, feedId, feedsList.data]);
  // #526/#532: the link to this view — filters and the open mode, the same text as the address bar
  const copyLink = async () => { const qs = addressOf(effective, mode); await navigator.clipboard?.writeText(`${window.location.origin}/library${qs ? `?${qs}` : ""}`); flash("Copied a link to this view."); };
  const modeCopyLink = <button type="button" data-testid="mode-copy-link" onClick={copyLink} className="inline-flex items-center gap-1 text-stone-400 hover:text-indigo-600 dark:hover:text-indigo-300" title="Copy a link to this view — paste it in a note, a message, or hand it to Claude"><Link2 className="h-3 w-3" aria-hidden="true" />Copy link</button>;
  const total = list.data?.pages[0]?.count ?? 0;
  const detail = rows.find((r) => r.id === detailId) ?? null;

  const invalidate = () => {
    queryClient.invalidateQueries({ queryKey: ["library"] });
    queryClient.invalidateQueries({ queryKey: ["library-facets"] });
  };
  const flash = (msg: string) => { setToast(msg); setTimeout(() => setToast(""), 3500); };

  // --- imports ---------------------------------------------------------------------------
  const importFiles = useMutation({
    mutationFn: async ({ files, text }: { files: File[]; text: string }) => {
      const form = new FormData();
      files.forEach((f) => form.append("files", f));
      if (text.trim()) form.append("text", text);
      if (importProject) form.append("project", importProject);
      return postForm<ImportSummary>("/references/import/", form);
    },
    onSuccess: (s) => {
      setLastImport(s); setImportError(""); setPasted(""); invalidate();
      if (s.created) petReact("paper");
      flash(`Imported ${s.created} new · ${s.existing} already here${s.failed ? ` · ${s.failed} failed` : ""}`);
    },
    onError: (e) => setImportError(String((e as Error).message ?? e)),
  });
  const importZotero = useMutation({
    mutationFn: async () => {
      const response = await fetch("/api/v1/references/import-zotero/", {
        method: "POST", headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken(), Accept: "application/json" },
        credentials: "same-origin", body: JSON.stringify(importProject ? { project: importProject } : {}),
      });
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail ?? `${response.status}`);
      return body as ImportSummary;
    },
    onSuccess: (s) => { setLastImport(s); setImportError(""); setImportOpen(true); invalidate(); if (s.created) petReact("paper"); flash(`Zotero: ${s.created} new · ${s.existing} already here`); },
    onError: (e) => { setImportOpen(true); setImportError(String((e as Error).message ?? e)); },
  });
  const addByDoi = useMutation({
    mutationFn: () => api<Ref>("/references/by-doi/", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ doi }) }),
    onSuccess: (r) => { setDoi(""); setDoiError(""); invalidate(); setDetailId(r.id); petReact("paper"); },
    onError: (e) => setDoiError(String((e as Error).message ?? e)),
  });
  const bulk = useMutation({
    mutationFn: (body: { ids: number[]; action: string; project?: string; value?: string }) =>
      api<{ affected: number; errors: string[] }>("/references/bulk/", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
    onSuccess: (out, vars) => {
      invalidate();
      if (vars.action === "delete") { setSelected(new Set()); setDetailId(null); }
      flash(`${vars.action.replace("_", " ")}: ${out.affected} affected${out.errors.length ? ` · ${out.errors.length} error(s)` : ""}`);
    },
  });
  // CRUD sweep 2026-09-06: one paper's actions on right-click, without selecting it first
  const menu = useMenu();
  const rowItems = (r: Ref): MenuItem[] => [
    { label: "Open", icon: <BookOpen className="h-3.5 w-3.5" />, onSelect: () => setDetailId(r.id) },
    { label: "Read & highlight", icon: <Highlighter className="h-3.5 w-3.5" />, disabled: !r.pdf, onSelect: () => openReader(r) },
    { label: "Reference page", icon: <ExternalLink className="h-3.5 w-3.5" />, onSelect: () => navigate(`/references/${r.id}`) },
    "-",
    { label: "Find metadata", icon: <Sparkles className="h-3.5 w-3.5" />, onSelect: () => findMeta.mutate(r.id) },
    { label: r.pdf ? "PDF attached" : pdfLookups.has(r.id) ? "Looking for a PDF…" : "Find PDF", icon: <FileDown className="h-3.5 w-3.5" />, disabled: Boolean(r.pdf) || pdfLookups.has(r.id) || !(r.doi || r.arxiv_id), hint: !r.pdf && !(r.doi || r.arxiv_id) ? "needs a DOI" : undefined, onSelect: () => fetchPdf.mutate(r.id) },
    { label: "Copy \\cite{key}", icon: <Copy className="h-3.5 w-3.5" />, onSelect: () => void navigator.clipboard?.writeText(`\\cite{${r.bibtex_key}}`) },
    "-",
    { label: "Delete from library…", icon: <Trash2 className="h-3.5 w-3.5" />, danger: true, onSelect: async () => { if (await confirmDialog({ title: `Delete “${r.title.slice(0, 70)}${r.title.length > 70 ? "…" : ""}”?`, body: "Its project links, highlights and PDF go too.", danger: true, confirmLabel: "Delete" })) bulk.mutate({ ids: [r.id], action: "delete" }); } },
  ];
  const findMeta = useMutation({
    mutationFn: (id: number) => api<Ref>(`/references/${id}/find-metadata/`, { method: "POST" }),
    onSuccess: () => { invalidate(); flash("Metadata found and applied."); },
    onError: () => flash("No confident metadata match — try adding the DOI by hand."),
  });
  // #527: the retraction watch — ask Crossref about chosen papers or the stale ones (≤ 50 here;
  // the nightly sweep does the rest). Offline, the stored verdicts stay as they were.
  // #544: the PDF sweep — the four-source finder over the papers without a PDF; the rail's
  // status line comes from the same endpoint's GET
  const pdfSweep = useQuery({ queryKey: ["pdf-sweep-status"], queryFn: () => api<{ status: { missing: number; lookable: number; unchecked: number; found_30d: number; last_checked_at: string | null } }>("/references/find-pdfs/"), staleTime: 60_000 });
  const findPdfs = useMutation({
    mutationFn: () => api<{ checked: number; attached: { bibtex_key: string; source: string }[]; not_found: number; errors: number; stopped: string }>("/references/find-pdfs/", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ stale: true, limit: 10 }) }),
    onSuccess: (out) => {
      invalidate(); queryClient.invalidateQueries({ queryKey: ["pdf-sweep-status"] });
      const bySource = Object.entries(out.attached.reduce<Record<string, number>>((m, r) => { m[r.source] = (m[r.source] ?? 0) + 1; return m; }, {})).map(([k, n]) => `${PDF_SOURCES[k] ?? k}${n > 1 ? ` ×${n}` : ""}`).join(", ");
      if (out.checked === 0) flash(out.stopped === "offline" ? "No source answered — offline?" : "Every paper without a PDF was looked at in the last 30 days.");
      else flash(`Found ${out.attached.length} of ${out.checked}${bySource ? ` · ${bySource}` : ""}${out.stopped === "offline" ? " · stopped: no source answering" : out.stopped === "budget" ? " · stopped at the time budget" : ""}.`);
    },
    onError: () => flash("The PDF sweep failed."),
  });
  const checkRetractions = useMutation({
    mutationFn: (ids: number[] | null) => api<{ checked: number; retracted: { bibtex_key: string }[]; noticed: { bibtex_key: string }[]; errors: number; skipped: number }>("/references/check-retractions/", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(ids ? { ids } : { stale: true, limit: 50 }) }),
    onSuccess: (out, ids) => {
      invalidate(); queryClient.invalidateQueries({ queryKey: ["library-facets"] });
      if (!ids && out.checked === 0 && out.errors === 0) { flash("Every paper with a DOI was checked in the last 30 days."); return; }
      flash(`Checked ${out.checked} paper${out.checked === 1 ? "" : "s"} · ${out.retracted.length} retracted${out.noticed?.length ? ` · ${out.noticed.length} with a notice` : ""}${out.errors ? ` · ${out.errors} could not be checked` : ""}${out.skipped ? ` · ${out.skipped} without a DOI` : ""}.`);
    },
    onError: () => flash("Could not reach Crossref."),
  });
  // #529: the preprint watch — ask arXiv / Semantic Scholar whether chosen preprints (or the
  // stale ones) have a published version; a found DOI is never cleared by a later miss.
  const checkPreprints = useMutation({
    mutationFn: (ids: number[] | null) => api<{ checked: number; published: { bibtex_key: string }[]; errors: number; skipped: number }>("/references/check-published/", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(ids ? { ids } : { stale: true, limit: 50 }) }),
    onSuccess: (out, ids) => {
      invalidate(); queryClient.invalidateQueries({ queryKey: ["library-facets"] });
      if (!ids && out.checked === 0 && out.errors === 0) { flash("Every preprint was checked in the last 30 days."); return; }
      flash(`Checked ${out.checked} preprint${out.checked === 1 ? "" : "s"} · ${out.published.length} with a published version${out.errors ? ` · ${out.errors} could not be checked` : ""}.`);
    },
    onError: () => flash("Could not reach arXiv or Semantic Scholar."),
  });
  // #530: the citation watch — ask OpenAlex now, add a citing paper by its DOI, mark rows seen
  const refreshCiting = () => { queryClient.invalidateQueries({ queryKey: ["new-citations"] }); queryClient.invalidateQueries({ queryKey: ["new-citations-of"] }); queryClient.invalidateQueries({ queryKey: ["library-facets"] }); };
  const checkCitations = useMutation({
    mutationFn: (ids: number[] | null) => api<{ checked: number; new: CitingRow[]; seen: number; errors: number; skipped: number; stopped: boolean }>("/references/new-citations/check/", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(ids ? { ids } : { stale: true, limit: 50 }) }),
    onSuccess: (out, ids) => {
      invalidate(); refreshCiting();
      if (!ids && out.checked === 0 && out.errors === 0) { flash("Every paper was checked in the last 7 days."); return; }
      if (out.checked === 0 && out.errors > 0) { flash("OpenAlex did not answer (offline, or its daily budget is spent) — the stored feed is unchanged."); return; }
      flash(`Checked ${out.checked} paper${out.checked === 1 ? "" : "s"} · ${out.new.length} new citing paper${out.new.length === 1 ? "" : "s"}${out.errors ? ` · ${out.errors} could not be checked` : ""}.`);
    },
    onError: () => flash("Could not reach OpenAlex."),
  });
  const dismissCiting = useMutation({
    mutationFn: ({ ids, undo }: { ids: number[]; undo?: boolean }) => api<{ changed: number }>("/references/new-citations/dismiss/", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(undo ? { ids, undo: true } : { ids }) }),
    onSuccess: (out, { undo }) => { refreshCiting(); flash(undo ? `Put ${out.changed} back in the feed.` : `Marked ${out.changed} as seen.`); },
    onError: () => flash("Could not update the feed."),
  });
  const addCiting = useMutation({
    mutationFn: (row: CitingRow) => api<Ref>("/references/by-doi/", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(filters.project ? { doi: row.doi, project: filters.project } : { doi: row.doi }) }),
    onSuccess: (r) => { invalidate(); refreshCiting(); petReact("paper"); flash(`Added “${r.title.slice(0, 60)}” to the library${filters.project ? " and this project" : ""}.`); },
    onError: () => flash("Could not add the paper — its DOI did not resolve."),
  });
  const upgradePreprint = useMutation({
    mutationFn: (id: number) => api<Ref & { upgrade: { metadata: string } }>(`/references/${id}/upgrade/`, { method: "POST", headers: { "Content-Type": "application/json" }, body: "{}" }),
    onSuccess: (r) => { invalidate(); queryClient.invalidateQueries({ queryKey: ["library-facets"] }); flash(r.upgrade?.metadata === "partial" ? "Now cites the published version — DOI and venue applied; metadata will fill in when online. The cite key is unchanged." : "Now cites the published version — the cite key is unchanged."); },
    onError: (e) => flash(/409/.test(String(e)) ? "The published version is already in your library — merge the two instead." : "Could not upgrade the reference."),
  });
  // Tags (#381): colour, rename and delete from the rail; the facets carry each tag's colour
  const tagColors: TagColors = useMemo(() => Object.fromEntries((facets.data?.tags ?? []).map((t) => [t.name, t.color])), [facets.data?.tags]);
  const patchTag = useMutation({
    mutationFn: ({ id, ...patch }: { id: number; name?: string; color?: string }) =>
      api(`/library-tags/${id}/`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(patch) }),
    onSuccess: (_out, vars) => { invalidate(); if (vars.name && filters.tag) set({ tag: vars.name }); },
    onError: (e) => void errorDialog("Couldn't update the tag", e),
  });
  const deleteTag = useMutation({
    mutationFn: (id: number) => api(`/library-tags/${id}/`, { method: "DELETE" }),
    onSuccess: () => { invalidate(); if (filters.tag) set({ tag: "" }); },
    onError: (e) => void errorDialog("Couldn't delete the tag", e),
  });
  const tagItems = (t: { id: number; name: string; color: string; count: number }): MenuItem[] => [
    { label: "Rename…", icon: <Pencil className="h-3.5 w-3.5" />, onSelect: async () => { const name = await promptDialog({ title: "Rename tag", initial: t.name, confirmLabel: "Rename", validate: (v) => (v.trim() ? null : "A tag needs a name.") }); if (name && name.trim() !== t.name) patchTag.mutate({ id: t.id, name: name.trim() }); } },
    { label: "Delete tag…", icon: <Trash2 className="h-3.5 w-3.5" />, danger: true, onSelect: async () => { if (await confirmDialog({ title: `Delete the tag “${t.name}”?`, body: `It comes off ${t.count} paper${t.count === 1 ? "" : "s"}; the papers stay.`, danger: true, confirmLabel: "Delete tag" })) deleteTag.mutate(t.id); } },
    "-",
    ...TAG_PALETTE.map((c) => ({ label: c.name, hint: t.color === c.hex ? "current" : undefined, icon: <span className="inline-block h-3 w-3 rounded-full" style={{ background: c.hex }} aria-hidden="true" />, onSelect: () => patchTag.mutate({ id: t.id, color: c.hex }) })),
    { label: "No colour", disabled: !t.color, icon: <span className="inline-block h-3 w-3 rounded-full border border-stone-400" aria-hidden="true" />, onSelect: () => patchTag.mutate({ id: t.id, color: "" }) },
  ];

  // whole-page drop zone
  useEffect(() => {
    let depth = 0;
    const enter = (e: DragEvent) => { if (e.dataTransfer?.types.includes("Files")) { depth++; setDragging(true); } };
    const leave = () => { depth = Math.max(0, depth - 1); if (depth === 0) setDragging(false); };
    const over = (e: DragEvent) => { if (e.dataTransfer?.types.includes("Files")) e.preventDefault(); };
    const drop = (e: DragEvent) => {
      depth = 0; setDragging(false);
      const files = Array.from(e.dataTransfer?.files ?? []);
      if (!files.length) return;
      e.preventDefault(); setImportOpen(true);
      importFiles.mutate({ files, text: "" });
    };
    window.addEventListener("dragenter", enter); window.addEventListener("dragleave", leave);
    window.addEventListener("dragover", over); window.addEventListener("drop", drop);
    return () => { window.removeEventListener("dragenter", enter); window.removeEventListener("dragleave", leave); window.removeEventListener("dragover", over); window.removeEventListener("drop", drop); };
  }, [importFiles]);

  // keyboard: j/k move · enter open · x select · X / shift-click range · ⌘A all · o pdf · esc clear
  const toggleSelect = useCallback((id: number) => setSelected((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; }), []);
  // #433 (backlog #60): ranges — the last row you toggled is the anchor; shift-click or shift-x
  // selects everything between it and the row you are on; ⌘A/Ctrl+A selects the whole view.
  const anchorRef = useRef<number | null>(null);
  const selectRange = useCallback((to: number) => {
    const from = anchorRef.current ?? to;
    const [a, b] = from <= to ? [from, to] : [to, from];
    setSelected((s) => { const n = new Set(s); rows.slice(a, b + 1).forEach((r) => n.add(r.id)); return n; });
  }, [rows]);
  const onCheck = useCallback((i: number, id: number, shift: boolean) => { if (shift) selectRange(i); else { anchorRef.current = i; toggleSelect(id); } }, [selectRange, toggleSelect]);
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const el = e.target as HTMLInputElement;
      const typing = el.tagName === "TEXTAREA" || el.tagName === "SELECT" || (el.tagName === "INPUT" && el.type !== "checkbox") || el.isContentEditable;
      if (typing || e.altKey) return; // a focused checkbox still answers to j/k, x, Esc
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "a" && rows.length && !readerId) { e.preventDefault(); setSelected(new Set(rows.map((r) => r.id))); return; }
      if (e.metaKey || e.ctrlKey) return;
      if (!rows.length) return;
      if (e.key === "j" || e.key === "ArrowDown") { e.preventDefault(); setCursor((c) => Math.min(rows.length - 1, c + 1)); }
      else if (e.key === "k" || e.key === "ArrowUp") { e.preventDefault(); setCursor((c) => Math.max(0, c - 1)); }
      else if (e.key === "Enter") { setDetailId(rows[cursor]?.id ?? null); }
      else if (e.key === "X") { selectRange(cursor); }
      else if (e.key === "x") { const id = rows[cursor]?.id; if (id) { anchorRef.current = cursor; toggleSelect(id); } }
      else if (e.key === "o") { const r = rows[cursor]; if (r?.pdf) openReader(r); }
      else if (e.key === "Escape") { if (readerId) closeReader(); else { setSelected(new Set()); setDetailId(null); } }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [rows, cursor, readerId, toggleSelect, selectRange]);
  useEffect(() => { listRef.current?.querySelector<HTMLElement>(`[data-row="${cursor}"]`)?.scrollIntoView({ block: "nearest" }); }, [cursor]);
  useEffect(() => { setCursor(0); }, [effective]);

  const set = (patch: Partial<Filters>) => setFilters((f) => ({ ...f, ...patch }));
  const toggle = (key: keyof Filters, value: string) => set({ [key]: filters[key] === value ? "" : value } as Partial<Filters>);
  const activeChips = (Object.keys(filters) as (keyof Filters)[]).filter((k) => k !== "sort" && k !== "q" && filters[k]);
  const f = facets.data;
  const maxYear = Math.max(1, ...(f?.years.map((y) => y.count) ?? [1]));
  const allSelectedOnPage = rows.length > 0 && rows.every((r) => selected.has(r.id));

  if (list.isError) return <ErrorState message="Couldn't load the library." onRetry={() => list.refetch()} />;

  return (
    <div className="relative">
      {dragging && (
        <div className="pointer-events-none fixed inset-0 z-40 flex items-center justify-center bg-stone-950/70 backdrop-blur-sm">
          <div className="hairline-gradient glow-accent rounded-3xl bg-stone-900 px-10 py-8 text-center">
            <Upload className="mx-auto mb-3 h-8 w-8 text-indigo-300" aria-hidden="true" />
            <p className="font-display text-xl font-semibold text-stone-100">Drop to import</p>
            <p className="mt-1 text-sm text-stone-300">PDFs, .bib, .ris, or CSL .json — any mix, any number.</p>
          </div>
        </div>
      )}

      {/* header */}
      <div className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="font-display text-3xl font-bold tracking-tight dark:text-stone-100">Library</h1>
          <p className="mt-1 text-sm text-stone-500 dark:text-stone-300">
            {f ? `${f.total} references · ${f.with_pdf} with PDF · ${f.unfiled} unfiled` : "Loading…"}
            {f && f.needs_metadata > 0 && (
              <button type="button" onClick={() => set({ needs_metadata: filters.needs_metadata ? "" : "true" })} className="ml-2 rounded-full bg-amber-500/10 px-2 py-0.5 text-xs text-amber-700 hover:bg-amber-500/20 dark:text-amber-300">
                {f.needs_metadata} need metadata
              </button>
            )}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <form className="flex items-start gap-1.5" onSubmit={(e) => { e.preventDefault(); if (doi.trim()) addByDoi.mutate(); }}>
            <div>
              <input ref={doiRef} value={doi} onChange={(e) => setDoi(e.target.value)} placeholder="Add by DOI or arXiv…" className="w-56 rounded-lg border border-stone-300 bg-white px-3 py-1.5 text-sm placeholder:text-stone-400 focus:border-indigo-500 focus:outline-none dark:border-stone-700 dark:bg-stone-800" />
              {doiError && <p className="mt-1 text-xs text-red-500">{doiError}</p>}
            </div>
            <button type="submit" disabled={addByDoi.isPending} className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50">{addByDoi.isPending ? "…" : "Add"}</button>
          </form>
          <button type="button" onClick={() => setImportOpen((v) => !v)} className={`inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-sm transition-colors ${importOpen ? "border-indigo-400 text-indigo-700 dark:text-indigo-200" : "border-stone-300 text-stone-600 hover:border-indigo-300 dark:border-stone-700 dark:text-stone-300"}`}>
            <Upload className="h-3.5 w-3.5" aria-hidden="true" />Import
          </button>
          <button type="button" onClick={() => importZotero.mutate()} disabled={importZotero.isPending} className="inline-flex items-center gap-1.5 rounded-lg border border-stone-300 px-3 py-1.5 text-sm text-stone-600 transition-colors hover:border-indigo-300 disabled:opacity-50 dark:border-stone-700 dark:text-stone-300" title="Pull your whole library from the Zotero running on this computer">
            {importZotero.isPending ? <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" /> : <Download className="h-3.5 w-3.5" aria-hidden="true" />}Import from Zotero
          </button>
        </div>
      </div>

      {/* import panel */}
      {importOpen && (
        <section className={`${panel} rise mb-4 p-5`}>
          <div className="grid gap-4 lg:grid-cols-[1fr_1fr_14rem]">
            <label className="flex cursor-pointer flex-col items-center justify-center rounded-xl border border-dashed border-stone-300 px-4 py-6 text-center text-sm text-stone-500 transition-colors hover:border-indigo-400 dark:border-stone-700 dark:text-stone-300">
              <FileText className="mb-2 h-6 w-6 text-indigo-400" aria-hidden="true" />
              <span className="font-medium text-stone-700 dark:text-stone-100">Drop files anywhere, or click to choose</span>
              <span className="mt-1 text-xs">PDFs (DOI read off page one) · .bib · .ris · CSL .json</span>
              <input type="file" multiple accept=".pdf,.bib,.ris,.json,.bibtex,application/pdf" className="hidden" onChange={(e) => { const files = Array.from(e.target.files ?? []); if (files.length) importFiles.mutate({ files, text: "" }); e.target.value = ""; }} />
            </label>
            <div className="flex flex-col">
              <textarea value={pasted} onChange={(e) => setPasted(e.target.value)} placeholder={"Or paste BibTeX / RIS / CSL-JSON here…"} className="min-h-24 flex-1 rounded-xl border border-stone-300 bg-white px-3 py-2 font-mono text-xs placeholder:text-stone-400 focus:border-indigo-500 focus:outline-none dark:border-stone-700 dark:bg-stone-800" />
              <button type="button" disabled={!pasted.trim() || importFiles.isPending} onClick={() => importFiles.mutate({ files: [], text: pasted })} className="mt-2 self-end rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50">
                {importFiles.isPending ? "Importing…" : "Import pasted"}
              </button>
            </div>
            <div className="text-sm">
              <label className={railH}>Link imports to</label>
              <select value={importProject} onChange={(e) => setImportProject(e.target.value)} className="w-full rounded-lg border border-stone-300 bg-white px-2 py-1.5 text-sm dark:border-stone-700 dark:bg-stone-800">
                <option value="">— just the library —</option>
                {f?.all_projects.map((p) => <option key={p.slug} value={p.slug}>{p.name}</option>)}
              </select>
              <p className="mt-3 text-xs text-stone-400">Everything is deduplicated by DOI, arXiv id, or title + year, so re-importing is always safe.</p>
            </div>
          </div>
          {importError && <p className="mt-3 rounded-lg bg-red-500/10 px-3 py-2 text-sm text-red-600 dark:text-red-300">{importError}</p>}
          {importFiles.isPending && <p className="mt-3 flex items-center gap-2 text-sm text-stone-500"><Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />Reading files, fetching metadata…</p>}
          {lastImport && (
            <div className="mt-4">
              <p className="text-xs font-semibold uppercase tracking-wide text-stone-400">Last import · {lastImport.created} new · {lastImport.existing} existing · {lastImport.failed} failed</p>
              <ul className="mt-2 max-h-40 space-y-0.5 overflow-auto text-sm">
                {lastImport.results.map((r, i) => (
                  <li key={i} className="flex items-center gap-2">
                    {r.error ? <X className="h-3.5 w-3.5 text-red-400" aria-hidden="true" /> : <Check className={`h-3.5 w-3.5 ${r.created ? "text-emerald-400" : "text-stone-400"}`} aria-hidden="true" />}
                    {r.reference_id ? <button type="button" onClick={() => setDetailId(r.reference_id)} className="truncate hover:underline dark:text-stone-100">{r.title}</button> : <span className="truncate">{r.title}</span>}
                    <span className="shrink-0 text-xs text-stone-400">{r.error ? r.error : r.created ? `new · ${r.source}` : "already in library"}{r.needs_metadata ? " · needs metadata" : ""}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}
        </section>
      )}

      {/* workbench */}
      <div className={`grid gap-4 ${readerId ? "lg:grid-cols-[minmax(0,1fr)_22rem]" : "lg:grid-cols-[13.5rem_minmax(0,1fr)_22rem]"}`}>
        {/* rail */}
        {!readerId && (<aside className={`${panel} rise h-fit p-3 lg:sticky lg:top-6`}>
          <div className="relative mb-3">
            <Search className="pointer-events-none absolute left-2.5 top-2 h-3.5 w-3.5 text-stone-400" aria-hidden="true" />
            <input type="search" value={qInput} onChange={(e) => setQInput(e.target.value)} placeholder="Title, author, venue, DOI…" className="w-full rounded-lg border border-stone-300 bg-white py-1.5 pl-8 pr-2 text-sm placeholder:text-stone-400 focus:border-indigo-500 focus:outline-none dark:border-stone-700 dark:bg-stone-800" />
          </div>
          <div className="mb-3">
            <p className={railH}>Sort</p>
            <select value={filters.sort} onChange={(e) => set({ sort: e.target.value })} className="w-full rounded-lg border border-stone-300 bg-white px-2 py-1 text-xs dark:border-stone-700 dark:bg-stone-800">
              <option value="added">Newest added</option><option value="-added">Oldest added</option>
              <option value="year">Year ↓</option><option value="-year">Year ↑</option>
              <option value="title">Title A–Z</option><option value="citations">Most cited</option>
            </select>
          </div>
          {f && (
            <>
              {(readingNow.data?.length ?? 0) > 0 && (
                <div className="mb-3" data-testid="continue-reading">
                  <p className={railH}>Continue reading</p>
                  <ul className="space-y-1.5">
                    {readingNow.data!.map((p) => (
                      <li key={p.id}>
                        <button type="button" onClick={() => { const row = rows.find((r) => r.id === p.id); if (row?.pdf) openReader(row); else { readParam.current = p.id; set({ q: p.bibtex_key }); } }} className="w-full text-left" title={`Open on page ${p.page}`}>
                          <span className="block truncate text-xs text-stone-700 hover:text-indigo-700 dark:text-stone-200 dark:hover:text-indigo-300">{p.title}</span>
                          <span className="mt-0.5 flex items-center gap-2">
                            <span className="h-0.5 flex-1 overflow-hidden rounded-full bg-stone-200 dark:bg-stone-700"><span className="block h-0.5 rounded-full bg-indigo-500" style={{ width: `${p.percent ?? 50}%` }} /></span>
                            <span className="text-[10px] tabular-nums text-stone-400">{pageLabel(p)}</span>
                          </span>
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
              <div className="mb-3">
                <div className="mb-1.5 flex items-center justify-between">
                  <p className={`${railH} mb-0`}>Smart views</p>
                  {viewName === null && (activeChips.length > 0 || q) && (
                    <button type="button" onClick={() => setViewName("")} className="text-[10px] text-indigo-500 hover:underline" title="Save the current filters as a view">+ save</button>
                  )}
                </div>
                {viewName !== null && (
                  <form onSubmit={(e) => { e.preventDefault(); if (viewName.trim()) saveView.mutate(viewName.trim()); }} className="mb-1 flex gap-1">
                    <input autoFocus value={viewName} onChange={(e) => setViewName(e.target.value)} placeholder="Name this view…" className="min-w-0 flex-1 rounded-md border border-stone-300 bg-white px-2 py-1 text-xs dark:border-stone-700 dark:bg-stone-800" onKeyDown={(e) => { if (e.key === "Escape") setViewName(null); }} />
                    <button type="submit" className="rounded-md bg-indigo-600 px-2 text-xs text-white">Save</button>
                  </form>
                )}
                {f.views.length === 0 && viewName === null && <p className="px-2 text-[11px] text-stone-400">Filter, then “+ save” to keep it here.</p>}
                {f.views.map((v) => {
                  const active = JSON.stringify({ ...EMPTY, ...v.params, q: (v.params.q ?? "") }) === JSON.stringify({ ...effective, sort: filters.sort });
                  return (
                    <div key={v.id} className={`group/view relative flex items-center ${viewDrag?.id === v.id ? "opacity-40" : ""}`} draggable data-testid="smart-view"
                         onDragStart={(e) => { e.dataTransfer.effectAllowed = "move"; setViewDrag({ id: v.id, over: null }); }}
                         onDragOver={(e) => { if (!viewDrag) return; e.preventDefault(); if (viewDrag.over !== v.id) setViewDrag({ ...viewDrag, over: v.id }); }}
                         onDrop={(e) => { e.preventDefault(); if (!viewDrag || viewDrag.id === v.id) { setViewDrag(null); return; } const ids = f.views.map((x) => x.id); const from = ids.indexOf(viewDrag.id); const to = ids.indexOf(v.id); ids.splice(from, 1); ids.splice(to, 0, viewDrag.id); reorderViews.mutate(ids); setViewDrag(null); }}
                         onDragEnd={() => setViewDrag(null)}>
                      {viewDrag?.over === v.id && viewDrag.id !== v.id && <span aria-hidden="true" className="pointer-events-none absolute left-1 right-1 top-0 h-0.5 rounded-full bg-indigo-500" />}
                      <button type="button" className={chip(active)} onClick={() => { setFilters({ ...EMPTY, ...v.params }); setQInput(v.params.q ?? ""); }} title="Drag to reorder">
                        <span className="flex min-w-0 items-center gap-1.5"><Bookmark className="h-3 w-3 shrink-0 text-indigo-400" aria-hidden="true" /><span className="truncate">{v.name}</span></span>
                      </button>
                      <button type="button" onClick={() => deleteView.mutate(v.id)} className="ml-0.5 shrink-0 text-stone-300 opacity-0 hover:text-red-500 group-hover/view:opacity-100" aria-label={`Delete view ${v.name}`}><X className="h-3 w-3" aria-hidden="true" /></button>
                    </div>
                  );
                })}
              </div>
              <div className="mb-3">
                <p className={railH}>Tags</p>
                {f.tags.length === 0 && <p className="px-2 text-[11px] text-stone-400">No tags yet — select papers and use “Tag”.</p>}
                {f.tags.slice(0, 12).map((t) => (
                  <button key={t.name} type="button" data-testid="rail-tag" className={chip(filters.tag === t.name)} onClick={() => set({ tag: filters.tag === t.name ? "" : t.name, untagged: "" })} onContextMenu={(e) => menu.open(e, tagItems(t))} title="Right-click for colour, rename, delete">
                    <span className="flex min-w-0 items-center gap-1.5"><TagIcon className="h-3 w-3 shrink-0" style={{ color: t.color || "#8b7cff" }} aria-hidden="true" /><span className="truncate">{t.name}</span></span>
                    <span className="tabular-nums text-stone-400">{t.count}</span>
                  </button>
                ))}
                {f.untagged > 0 && <button type="button" className={chip(filters.untagged === "true")} onClick={() => set({ untagged: filters.untagged ? "" : "true", tag: "" })}><span>Untagged</span><span className="tabular-nums text-stone-400">{f.untagged}</span></button>}
              </div>
              <WatchFolderBlock projects={f.all_projects ?? []} onImported={() => { invalidate(); }} flash={flash} />
              <div className="mb-3">
                <p className={railH}>Projects</p>
                <button type="button" className={chip(filters.unfiled === "true")} onClick={() => set({ unfiled: filters.unfiled ? "" : "true", project: "" })}><span>Unfiled</span><span className="tabular-nums text-stone-400">{f.unfiled}</span></button>
                {f.projects.map((p) => {
                  const color = f.all_projects.find((x) => x.slug === p.slug)?.color ?? "#8b7cff";
                  return (
                    <button key={p.slug} type="button" className={chip(filters.project === p.slug)} onClick={() => set({ project: filters.project === p.slug ? "" : p.slug, unfiled: "", reading_status: "" })}>
                      <span className="flex min-w-0 items-center gap-1.5"><span className="h-2 w-2 shrink-0 rounded-full" style={{ background: color }} /><span className="truncate">{p.name}</span></span>
                      <span className="tabular-nums text-stone-400">{p.count}</span>
                    </button>
                  );
                })}
              </div>
              {filters.project && (
                <div className="mb-3">
                  <p className={railH}>Reading status</p>
                  {Object.entries(STATUS_LABEL).map(([k, label]) => (
                    <button key={k} type="button" className={chip(filters.reading_status === k)} onClick={() => toggle("reading_status", k)}><span>{label}</span></button>
                  ))}
                </div>
              )}
              <div className="mb-3">
                <p className={railH}>Years</p>
                <div className="flex h-12 items-end gap-px">
                  {f.years.map((y) => (
                    <button key={y.year} type="button" title={`${y.year}: ${y.count}`} onClick={() => toggle("year", String(y.year))} className="group flex-1 rounded-t-sm transition-colors" style={{ height: `${Math.max(12, (y.count / maxYear) * 100)}%`, background: filters.year === String(y.year) ? "#8b7cff" : "rgba(139,124,255,0.35)" }} />
                  ))}
                </div>
                <div className="mt-1 flex justify-between text-[10px] text-stone-400"><span>{f.years[0]?.year ?? ""}</span><span>{filters.year || ""}</span><span>{f.years[f.years.length - 1]?.year ?? ""}</span></div>
              </div>
              <div className="mb-3">
                <p className={railH}>Files</p>
                <button type="button" className={chip(filters.has_pdf === "true")} onClick={() => toggle("has_pdf", "true")}><span>Has PDF</span><span className="tabular-nums text-stone-400">{f.with_pdf}</span></button>
                <button type="button" className={chip(filters.has_pdf === "false")} onClick={() => toggle("has_pdf", "false")}><span>No PDF</span><span className="tabular-nums text-stone-400">{f.without_pdf}</span></button>
                <button type="button" className={chip(filters.needs_metadata === "true")} onClick={() => toggle("needs_metadata", "true")}><span>Needs metadata</span><span className="tabular-nums text-stone-400">{f.needs_metadata}</span></button>
                <button type="button" data-testid="rail-retracted" className={chip(filters.retracted === "true")} onClick={() => toggle("retracted", "true")} title="Papers Crossref lists a retraction, withdrawal or removal notice for — checked nightly"><span className="flex items-center gap-1.5"><ShieldAlert className={`h-3 w-3 ${f.retracted ? "text-rose-500" : ""}`} aria-hidden="true" />Retracted</span><span className={`tabular-nums ${f.retracted ? "font-semibold text-rose-500" : "text-stone-400"}`}>{f.retracted}</span></button>
                <button type="button" data-testid="rail-notices" className={chip(filters.notices === "true")} onClick={() => toggle("notices", "true")} title="Papers Crossref lists an expression of concern or a correction for — not retracted, but read the notice before citing the result"><span className="flex items-center gap-1.5"><MessageSquareWarning className={`h-3 w-3 ${f.notices ? "text-amber-500" : ""}`} aria-hidden="true" />With notices</span><span className={`tabular-nums ${f.notices ? "font-semibold text-amber-600 dark:text-amber-400" : "text-stone-400"}`}>{f.notices}</span></button>
                <button type="button" data-testid="check-retractions" disabled={checkRetractions.isPending} onClick={() => checkRetractions.mutate(null)} className="mt-0.5 flex w-full items-center gap-1.5 rounded-md px-2 py-1 text-left text-[11px] text-stone-400 hover:bg-stone-100 hover:text-stone-600 disabled:opacity-60 dark:hover:bg-stone-800 dark:hover:text-stone-200" title="Ask Crossref about the papers not checked in the last 30 days (up to 50 now; the rest run nightly)">{checkRetractions.isPending ? <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" /> : <ShieldCheck className="h-3 w-3" aria-hidden="true" />}{checkRetractions.isPending ? "Asking Crossref…" : "Check retractions now"}</button>
                {(f.without_pdf > 0 || (pdfSweep.data?.status.found_30d ?? 0) > 0) && (
                  <>
                    <button type="button" data-testid="find-pdfs" disabled={findPdfs.isPending} onClick={() => findPdfs.mutate()} className="mt-0.5 flex w-full items-center gap-1.5 rounded-md px-2 py-1 text-left text-[11px] text-stone-400 hover:bg-stone-100 hover:text-stone-600 disabled:opacity-60 dark:hover:bg-stone-800 dark:hover:text-stone-200" title="Look for free PDFs — arXiv, Unpaywall, Semantic Scholar, OpenAlex — for the papers without one, not looked at in 30 days (up to 10 now; the rest run nightly)">{findPdfs.isPending ? <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" /> : <FileDown className="h-3 w-3" aria-hidden="true" />}{findPdfs.isPending ? "Looking for PDFs…" : "Find PDFs now"}</button>
                    {pdfSweep.data && <p data-testid="pdf-sweep-status" className="px-2 pb-1 text-[10px] leading-snug text-stone-400">{[pdfSweep.data.status.lookable ? `${pdfSweep.data.status.lookable} lookable` : null, pdfSweep.data.status.unchecked ? `${pdfSweep.data.status.unchecked} never looked at` : null, pdfSweep.data.status.found_30d ? `${pdfSweep.data.status.found_30d} found this month` : null, pdfSweep.data.status.last_checked_at ? `last looked ${new Date(pdfSweep.data.status.last_checked_at).toLocaleDateString()}` : null].filter(Boolean).join(" · ") || "nothing to look for"}</p>}
                  </>
                )}
                <button type="button" data-testid="rail-preprints" className={chip(filters.preprints === "true")} onClick={() => toggle("preprints", "true")} title="arXiv papers without a publisher DOI of their own"><span className="flex items-center gap-1.5"><FileText className="h-3 w-3" aria-hidden="true" />Preprints</span><span className="tabular-nums text-stone-400">{f.preprints}</span></button>
                <button type="button" data-testid="rail-published" className={chip(filters.published_available === "true")} onClick={() => toggle("published_available", "true")} title="Preprints whose published version the preprint watch found — upgrade them from the detail pane"><span className="flex items-center gap-1.5"><ArrowUpCircle className={`h-3 w-3 ${f.published_available ? "text-amber-500" : ""}`} aria-hidden="true" />Published version</span><span className={`tabular-nums ${f.published_available ? "font-semibold text-amber-500" : "text-stone-400"}`}>{f.published_available}</span></button>
                <button type="button" data-testid="check-preprints" disabled={checkPreprints.isPending} onClick={() => checkPreprints.mutate(null)} className="mt-0.5 flex w-full items-center gap-1.5 rounded-md px-2 py-1 text-left text-[11px] text-stone-400 hover:bg-stone-100 hover:text-stone-600 disabled:opacity-60 dark:hover:bg-stone-800 dark:hover:text-stone-200" title="Ask arXiv and Semantic Scholar about the preprints not checked in the last 30 days (up to 50 now; the rest run nightly)">{checkPreprints.isPending ? <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" /> : <ArrowUpCircle className="h-3 w-3" aria-hidden="true" />}{checkPreprints.isPending ? "Asking arXiv…" : "Check preprints now"}</button>
                <button type="button" className={chip(dupMode)} onClick={() => { setFeedMode(false); setDupMode((v) => !v); }} title="Papers that look like the same work imported twice"><span className="flex items-center gap-1.5"><CopyCheck className="h-3 w-3" aria-hidden="true" />Duplicates</span><span className={`tabular-nums ${f.duplicates ? "text-amber-500" : "text-stone-400"}`}>{f.duplicates}</span></button>
                <button type="button" data-testid="rail-new-citations" className={chip(citeMode)} onClick={() => (citeMode ? setCiteMode(false) : openCiting(null))} title="Papers outside the library that cite papers in it — found by the weekly OpenAlex sweep"><span className="flex items-center gap-1.5"><Radar className={`h-3 w-3 ${f.new_citations ? "text-sky-500" : ""}`} aria-hidden="true" />New citations</span><span className={`tabular-nums ${f.new_citations ? "font-semibold text-sky-500" : "text-stone-400"}`}>{f.new_citations}</span></button>
                <button type="button" data-testid="check-citations" disabled={checkCitations.isPending} onClick={() => checkCitations.mutate(null)} className="mt-0.5 flex w-full items-center gap-1.5 rounded-md px-2 py-1 text-left text-[11px] text-stone-400 hover:bg-stone-100 hover:text-stone-600 disabled:opacity-60 dark:hover:bg-stone-800 dark:hover:text-stone-200" title="Ask OpenAlex who newly cites the papers not checked in the last 7 days (up to 50 now; the rest run nightly)">{checkCitations.isPending ? <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" /> : <Radar className="h-3 w-3" aria-hidden="true" />}{checkCitations.isPending ? "Asking OpenAlex…" : "Check citations now"}</button>
              </div>
              {/* #531: the feeds the researcher follows — an arXiv category, a journal — with their
                  unread counts; the list opens as a mode like New citations. */}
              <div className="mb-3" data-testid="feeds-rail">
                <p className={railH}>Feeds</p>
                <button type="button" data-testid="rail-feeds-all" className={chip(feedMode && feedId === null)} onClick={() => (feedMode && feedId === null ? setFeedMode(false) : openFeeds(null))} title="New entries from every feed you follow, newest first"><span className="flex items-center gap-1.5"><Rss className={`h-3 w-3 ${(feedsList.data ?? []).some((f) => f.new) ? "text-emerald-500" : ""}`} aria-hidden="true" />All feeds</span><span className={`tabular-nums ${(feedsList.data ?? []).some((f) => f.new) ? "font-semibold text-emerald-500" : "text-stone-400"}`}>{(feedsList.data ?? []).reduce((n, f) => n + f.new, 0)}</span></button>
                {(feedsList.data ?? []).map((f) => (
                  <button key={f.id} type="button" data-testid="rail-feed" className={chip(feedMode && feedId === f.id)} onClick={() => (feedMode && feedId === f.id ? setFeedMode(false) : openFeeds(f.id))} title={f.last_error ? `${f.url} — ${f.last_error}` : f.url}>
                    <span className="flex min-w-0 items-center gap-1.5">{f.last_error && <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-amber-500" aria-label="the last fetch failed" />}<span className="truncate">{f.title}</span></span>
                    <span className={`tabular-nums ${f.new ? "text-emerald-500" : "text-stone-400"}`}>{f.new}</span>
                  </button>
                ))}
                {feedFormOpen ? (
                  <form className="mt-1 flex items-center gap-1" onSubmit={(e) => { e.preventDefault(); if (feedUrl.trim()) followFeed.mutate(feedUrl.trim()); }}>
                    <input data-testid="feed-url" autoFocus value={feedUrl} onChange={(e) => setFeedUrl(e.target.value)} placeholder="Feed or journal address" className="min-w-0 flex-1 rounded-md border border-stone-300 bg-transparent px-2 py-1 text-xs outline-none focus:border-indigo-400 dark:border-stone-700" />
                    <button type="submit" disabled={followFeed.isPending || !feedUrl.trim()} className="rounded-md bg-indigo-600 px-2 py-1 text-xs font-medium text-white hover:bg-indigo-700 disabled:opacity-50">{followFeed.isPending ? <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" /> : "Follow"}</button>
                    <button type="button" onClick={() => { setFeedFormOpen(false); setFeedError(""); }} className="text-stone-400 hover:text-stone-600" aria-label="Cancel"><X className="h-3 w-3" aria-hidden="true" /></button>
                  </form>
                ) : (
                  <button type="button" data-testid="add-feed" onClick={() => setFeedFormOpen(true)} className="mt-0.5 flex w-full items-center gap-1.5 rounded-md px-2 py-1 text-left text-[11px] text-stone-400 hover:bg-stone-100 hover:text-stone-600 dark:hover:bg-stone-800 dark:hover:text-stone-200" title="An arXiv category (https://rss.arxiv.org/atom/q-bio.NC), a journal's RSS address, or the journal's home page"><Plus className="h-3 w-3" aria-hidden="true" />Follow a feed{filters.project ? " for this project" : ""}</button>
                )}
                {feedError && <p data-testid="feed-error" className="mt-1 px-2 text-[11px] text-rose-500">{feedError}</p>}
                {(feedsList.data ?? []).length > 0 && <button type="button" data-testid="refresh-feeds" disabled={refreshFeeds.isPending} onClick={() => refreshFeeds.mutate(null)} className="mt-0.5 flex w-full items-center gap-1.5 rounded-md px-2 py-1 text-left text-[11px] text-stone-400 hover:bg-stone-100 hover:text-stone-600 disabled:opacity-60 dark:hover:bg-stone-800 dark:hover:text-stone-200" title="Fetch the feeds not fetched in the last hour (the rest run every six hours)">{refreshFeeds.isPending ? <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" /> : <Rss className="h-3 w-3" aria-hidden="true" />}{refreshFeeds.isPending ? "Fetching…" : "Refresh feeds now"}</button>}
              </div>
              <div className="mb-3">
                <p className={railH}>Type</p>
                {f.entry_types.slice(0, 6).map((t) => (
                  <button key={t.entry_type} type="button" className={chip(filters.entry_type === t.entry_type)} onClick={() => toggle("entry_type", t.entry_type)}><span>{t.entry_type}</span><span className="tabular-nums text-stone-400">{t.count}</span></button>
                ))}
              </div>
              {f.venues.length > 0 && (
                <div>
                  <p className={railH}>Venues</p>
                  {f.venues.slice(0, 8).map((v) => (
                    <button key={v.venue} type="button" className={chip(filters.venue === v.venue)} onClick={() => toggle("venue", v.venue)} title={v.venue}><span className="truncate">{v.venue}</span><span className="tabular-nums text-stone-400">{v.count}</span></button>
                  ))}
                </div>
              )}
              {/* #524: the author lens — top authors by papers; a filter set from a paper's byline that
                  is not among them is shown first so the rail always says what is filtering. */}
              {(f.authors ?? []).length > 0 && (
                <div className="mt-3" data-testid="author-facet">
                  <p className={railH}>Authors</p>
                  {[
                    ...(filters.author && !(f.authors ?? []).slice(0, 8).some((a) => a.name.toLowerCase() === filters.author.toLowerCase()) ? [{ name: filters.author, given: "", count: total }] : []),
                    ...(f.authors ?? []).slice(0, 8),
                  ].map((a) => (
                    <button key={a.name} type="button" className={chip(filters.author.toLowerCase() === a.name.toLowerCase())} onClick={() => toggle("author", a.name)} title={`${[a.given, a.name].filter(Boolean).join(" ")} · ${a.count} paper${a.count === 1 ? "" : "s"}`}><span className="truncate">{a.name}</span><span className="tabular-nums text-stone-400">{a.count}</span></button>
                  ))}
                </div>
              )}
            </>
          )}
        </aside>)}

        {/* reader, duplicates workbench, or the list */}
        {readerId && reader ? (
          <PdfReader
            refId={reader.id}
            initialFind={readerFind}
            pdfUrl={reader.pdf as string}
            title={reader.title}
            highlights={highlights.data ?? []}
            projects={reader.projects.map((p) => ({ slug: p.slug, name: p.name }))}
            project={reader.projects.some((p) => p.slug === hlProject) ? hlProject : ""}
            onProject={setHlProject}
            onSave={async (h) => { await addHighlight.mutateAsync({ reference: reader.id, ...h, project: reader.projects.some((p) => p.slug === hlProject) ? hlProject : null }); }}
            onClose={closeReader}
            jump={jump}
            fullReaderHref={`/library/${reader.id}/read/`}
            comments={(readerComments.data?.comments ?? []).map((c) => ({ id: c.id, body: c.body, page: c.line }))}
            onComment={(page) => void commentOnPage(page)}
          />
        ) : feedMode ? (
          <section className={`${panel} rise flex min-h-[60vh] flex-col overflow-hidden`} style={{ ["--i" as string]: 1 }} data-testid="feeds-panel">
            {(() => {
              const feed = feedId ? (feedsList.data ?? []).find((f) => f.id === feedId) : null;
              const rows = feedItems.data?.results ?? [];
              return (
                <>
                  <div className="flex flex-wrap items-center gap-2 border-b border-stone-100 px-4 py-2.5 text-xs dark:border-stone-800">
                    <Rss className="h-3.5 w-3.5 text-emerald-500" aria-hidden="true" />
                    <span className="font-medium text-stone-700 dark:text-stone-100">{showSeenFeed ? "Seen entries" : showMutedFeed ? `Muted entries${feed ? ` · ${feed.title}` : ""}` : feed ? feed.title : "Feeds"}</span>
                    {feed && <button type="button" onClick={() => setFeedId(null)} className="inline-flex items-center gap-1 rounded-full bg-emerald-500/10 px-2 py-0.5 text-emerald-700 dark:text-emerald-200" title="Show every feed">one feed <X className="h-3 w-3" aria-hidden="true" /></button>}
                    <span className="hidden text-stone-400 sm:inline">{feed ? (feed.last_error ? `last fetch failed — ${feed.last_error}` : feed.last_ok_at ? `fetched ${new Date(feed.last_ok_at).toLocaleString()}` : "not fetched yet") : `what your feeds announced · newest first${feedItems.data?.status.last_fetched_at ? ` · fetched ${new Date(feedItems.data.status.last_fetched_at).toLocaleDateString()}` : ""}`}</span>
                    <div className="ml-auto flex flex-wrap items-center gap-2">
                      <div className="relative"><Search className="pointer-events-none absolute left-1.5 top-1.5 h-3 w-3 text-stone-400" aria-hidden="true" /><input data-testid="feed-filter" value={feedQInput} onChange={(e) => setFeedQInput(e.target.value)} placeholder="Filter titles and abstracts" className="w-44 rounded-md border border-stone-200 bg-transparent py-0.5 pl-6 pr-2 text-xs outline-none focus:border-emerald-400 dark:border-stone-700" /></div>
                      <button type="button" data-testid="feed-toggle-seen" onClick={() => { setShowMutedFeed(false); setShowSeenFeed((v) => !v); }} className="text-stone-400 hover:underline">{showSeenFeed ? "back to new" : `seen${feedItems.data ? ` (${feedItems.data.status.dismissed})` : ""}`}</button>
                      {!showSeenFeed && (showMutedFeed || (feed ? feed.muted > 0 || feed.mute.length > 0 : (feedItems.data?.status.muted ?? 0) > 0)) && <button type="button" data-testid="feed-toggle-muted" onClick={() => setShowMutedFeed((v) => !v)} className="text-stone-400 hover:underline" title="The entries the mute list hid">{showMutedFeed ? "back to new" : `muted (${feed ? feed.muted : feedItems.data?.status.muted ?? 0})`}</button>}
                      {!showSeenFeed && rows.length > 1 && <button type="button" data-testid="feed-dismiss-all" disabled={dismissFeedItems.isPending} onClick={() => dismissFeedItems.mutate({ ids: rows.map((r) => r.id) })} className="text-stone-400 hover:underline disabled:opacity-50">mark all seen</button>}
                      <button type="button" disabled={refreshFeeds.isPending} onClick={() => refreshFeeds.mutate(feed ? [feed.id] : null)} className="inline-flex items-center gap-1 rounded-md border border-stone-300 px-2 py-0.5 text-stone-600 hover:border-emerald-400 disabled:opacity-50 dark:border-stone-700 dark:text-stone-300">{refreshFeeds.isPending ? <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" /> : <Rss className="h-3 w-3" aria-hidden="true" />}Refresh now</button>
                      {feed && <button type="button" data-testid="unfollow-feed" onClick={async () => { if (await confirmDialog({ title: `Stop following “${feed.title}”?`, body: "Its entries go; papers you added stay in the library.", danger: true, confirmLabel: "Stop following" })) unfollowFeed.mutate(feed.id); }} className="text-stone-400 hover:text-rose-500" title="Stop following this feed"><Trash2 className="h-3.5 w-3.5" aria-hidden="true" /></button>}
                      {modeCopyLink}
                      <button type="button" onClick={() => setFeedMode(false)} className="text-stone-400 hover:underline">back to the list</button>
                    </div>
                  </div>
                  {feed && !showSeenFeed && (
                    <div className="flex flex-wrap items-center gap-1.5 border-b border-stone-100 px-4 py-2 text-[11px] dark:border-stone-800" data-testid="feed-mute" title="Entries whose title, abstract or authors match a term are hidden — kept, not deleted, and back the moment the term goes">
                      <VolumeX className="h-3 w-3 text-stone-400" aria-hidden="true" />
                      <span className="text-stone-400">Mute</span>
                      {feed.mute.map((term) => (
                        <span key={term} data-testid="feed-mute-term" className="inline-flex items-center gap-1 rounded-full bg-stone-100 px-2 py-0.5 text-stone-600 dark:bg-stone-800 dark:text-stone-300">
                          {term}
                          <button type="button" aria-label={`Stop muting ${term}`} disabled={setFeedMute.isPending} onClick={() => setFeedMute.mutate({ id: feed.id, mute: feed.mute.filter((t) => t !== term) })} className="text-stone-400 hover:text-rose-500"><X className="h-3 w-3" aria-hidden="true" /></button>
                        </span>
                      ))}
                      <input data-testid="feed-mute-input" value={muteInput} onChange={(e) => setMuteInput(e.target.value)} onKeyDown={(e) => { if (e.key === "Enter") { e.preventDefault(); const term = muteInput.trim(); if (term.length >= 2 && !feed.mute.some((t) => t.toLowerCase() === term.toLowerCase())) setFeedMute.mutate({ id: feed.id, mute: [...feed.mute, term] }); else if (term.length < 2) flash("A mute term needs at least two characters."); else setMuteInput(""); } }} placeholder={feed.mute.length ? "another word, phrase or author:Name" : "a word, phrase or author:Name — Enter"} maxLength={60} className="min-w-[14rem] flex-1 rounded-md border border-transparent bg-transparent px-1.5 py-0.5 text-[11px] outline-none placeholder:text-stone-400 focus:border-stone-300 dark:focus:border-stone-700" />
                      {feed.muted_total > 0 && <span className="ml-auto text-stone-400" data-testid="feed-mute-total">{feed.muted_total} hidden so far</span>}
                    </div>
                  )}
                  <div className="flex-1 overflow-auto">
                    {feedItems.isLoading && <p className="p-4 text-sm text-stone-400">Reading the feeds…</p>}
                    {feedItems.data && rows.length === 0 && (
                      <div className="px-4 py-16 text-center">
                        <Rss className="mx-auto mb-2 h-6 w-6 text-emerald-400" aria-hidden="true" />
                        <p className="text-sm font-medium text-stone-700 dark:text-stone-100">{showSeenFeed ? "Nothing marked seen yet." : showMutedFeed ? "Nothing muted." : feedQ ? "No entry matches." : feedItems.data.status.feeds === 0 ? "No feeds followed yet." : "Nothing new from your feeds."}</p>
                        <p className="mt-1 text-xs text-stone-400">{showMutedFeed ? "Add a word, a phrase or author:Name to the feed's mute list and the entries it matches land here instead of the list." : feedItems.data.status.feeds === 0 ? "Follow an arXiv category or a journal from the rail — every new paper it announces lands here, with Add and Dismiss." : "The feeds are fetched every six hours; Refresh now asks them straight away."}</p>
                      </div>
                    )}
                    <ul className="divide-y divide-stone-100 dark:divide-stone-800">
                      {rows.map((row, i) => (
                        <li key={row.id} data-testid="feed-row" className="rise flex flex-wrap items-start gap-3 px-4 py-3 sm:flex-nowrap" style={{ ["--i" as string]: Math.min(i, 12) }}>
                          <div className="min-w-0 flex-1">
                            <a href={row.url || undefined} target="_blank" rel="noreferrer" className="text-sm text-stone-900 hover:underline dark:text-stone-100">{row.title}</a>
                            <p className="mt-0.5 text-[11px] text-stone-400">{[row.authors.slice(0, 3).join(", ") + (row.authors.length > 3 ? ` +${row.authors.length - 3}` : ""), feedId ? null : row.feed.title, row.published_on ? new Date(row.published_on).toLocaleDateString() : null, row.doi ? `doi ${row.doi}` : row.arxiv_id ? `arXiv ${row.arxiv_id}` : null, row.muted_at ? `muted by “${row.muted_by}”` : null].filter(Boolean).join(" · ")}</p>
                            {row.summary && <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-stone-500 dark:text-stone-400" title={row.summary}>{row.summary}</p>}
                          </div>
                          <div className="flex shrink-0 items-center gap-1 text-[11px]">
                            {row.addable && !showSeenFeed && !showMutedFeed && <button type="button" data-testid="feed-add" disabled={addFeedItem.isPending} onClick={() => addFeedItem.mutate(row)} className="inline-flex items-center gap-1 rounded-md bg-indigo-600 px-2 py-1 font-medium text-white hover:bg-indigo-700 disabled:opacity-50" title={filters.project ? "Add to the library and this project" : feed?.project ? `Add to the library and ${feed.project}` : "Add to the library"}><Plus className="h-3 w-3" aria-hidden="true" />Add</button>}
                            {!row.addable && !showSeenFeed && !showMutedFeed && <span className="rounded-md border border-stone-200 px-2 py-1 text-stone-400 dark:border-stone-700" title="No DOI or arXiv id in the feed — open it to judge, add by hand if it matters">no id</span>}
                            {!showMutedFeed && <button type="button" data-testid="feed-dismiss" disabled={dismissFeedItems.isPending} onClick={() => dismissFeedItems.mutate({ ids: [row.id], undo: showSeenFeed })} className="rounded-md border border-stone-300 px-2 py-1 text-stone-500 hover:border-stone-400 hover:text-stone-700 disabled:opacity-50 dark:border-stone-700 dark:text-stone-300">{showSeenFeed ? "Restore" : "Dismiss"}</button>}
                          </div>
                        </li>
                      ))}
                    </ul>
                  </div>
                </>
              );
            })()}
          </section>
        ) : citeMode ? (
          <section className={`${panel} rise flex min-h-[60vh] flex-col overflow-hidden`} style={{ ["--i" as string]: 1 }} data-testid="citing-panel">
            <div className="flex flex-wrap items-center gap-2 border-b border-stone-100 px-4 py-2.5 text-xs dark:border-stone-800">
              <Radar className="h-3.5 w-3.5 text-sky-500" aria-hidden="true" />
              <span className="font-medium text-stone-700 dark:text-stone-100">{showDismissed ? "Seen citations" : "New citations"}</span>
              {citeRef && citingFeed.data?.results[0]?.cites.find((c) => c.id === citeRef) ? (
                <button type="button" onClick={() => setCiteRef(null)} className="inline-flex items-center gap-1 rounded-full bg-sky-500/10 px-2 py-0.5 text-sky-700 dark:text-sky-200" title="Show the whole feed">citing <span className="font-mono">{citingFeed.data.results[0].cites.find((c) => c.id === citeRef)!.bibtex_key}</span> <X className="h-3 w-3" aria-hidden="true" /></button>
              ) : citeRef ? (
                <button type="button" onClick={() => setCiteRef(null)} className="inline-flex items-center gap-1 rounded-full bg-sky-500/10 px-2 py-0.5 text-sky-700 dark:text-sky-200">one paper <X className="h-3 w-3" aria-hidden="true" /></button>
              ) : null}
              <span className="text-stone-400">papers outside your library that cite papers in it · newest first{citingFeed.data?.status.last_checked_at ? ` · swept ${new Date(citingFeed.data.status.last_checked_at).toLocaleDateString()}` : ""}</span>
              <div className="ml-auto flex items-center gap-2">
                <button type="button" data-testid="citing-toggle-dismissed" onClick={() => setShowDismissed((v) => !v)} className="text-stone-400 hover:underline">{showDismissed ? "back to new" : `seen${citingFeed.data ? ` (${citingFeed.data.status.dismissed})` : ""}`}</button>
                {!showDismissed && (citingFeed.data?.results.length ?? 0) > 1 && <button type="button" data-testid="citing-dismiss-all" disabled={dismissCiting.isPending} onClick={() => dismissCiting.mutate({ ids: citingFeed.data!.results.map((r) => r.id) })} className="text-stone-400 hover:underline disabled:opacity-50">mark all seen</button>}
                <button type="button" disabled={checkCitations.isPending} onClick={() => checkCitations.mutate(null)} className="inline-flex items-center gap-1 rounded-md border border-stone-300 px-2 py-0.5 text-stone-600 hover:border-sky-400 disabled:opacity-50 dark:border-stone-700 dark:text-stone-300">{checkCitations.isPending ? <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" /> : <Radar className="h-3 w-3" aria-hidden="true" />}Check now</button>
                {modeCopyLink}
                <button type="button" onClick={() => setCiteMode(false)} className="text-stone-400 hover:underline">back to the list</button>
              </div>
            </div>
            <div className="flex-1 overflow-auto">
              {citingFeed.isLoading && <p className="p-4 text-sm text-stone-400">Reading the feed…</p>}
              {citingFeed.data && citingFeed.data.results.length === 0 && (
                <div className="px-4 py-16 text-center">
                  <Radar className="mx-auto mb-2 h-6 w-6 text-sky-400" aria-hidden="true" />
                  <p className="text-sm font-medium text-stone-700 dark:text-stone-100">{showDismissed ? "Nothing marked seen yet." : citeRef ? "No new paper cites this one." : "No new citations."}</p>
                  <p className="mt-1 text-xs text-stone-400">{citingFeed.data.status.watched === 0 ? "Papers with a DOI or an OpenAlex id are watched; this library has none yet." : citingFeed.data.status.unchecked > 0 ? `${citingFeed.data.status.unchecked} paper${citingFeed.data.status.unchecked === 1 ? "" : "s"} not asked about yet — Check now asks OpenAlex.` : "The sweep asks OpenAlex weekly which new papers cite yours; anything it finds lands here."}</p>
                </div>
              )}
              <ul className="divide-y divide-stone-100 dark:divide-stone-800">
                {citingFeed.data?.results.map((row, i) => (
                  <li key={row.id} data-testid="citing-row" className="rise flex flex-wrap items-start gap-3 px-4 py-3 sm:flex-nowrap" style={{ ["--i" as string]: Math.min(i, 12) }}>
                    <div className="min-w-0 flex-1">
                      <a href={row.url} target="_blank" rel="noreferrer" className="text-sm text-stone-900 hover:underline dark:text-stone-100">{row.title}</a>
                      <p className="mt-0.5 text-[11px] text-stone-400">{[row.authors.slice(0, 3).join(", ") + (row.authors.length > 3 ? ` +${row.authors.length - 3}` : ""), row.venue, row.year, row.published_on ? `published ${new Date(row.published_on).toLocaleDateString()}` : null, row.cited_by_count ? `${row.cited_by_count} citation${row.cited_by_count === 1 ? "" : "s"}` : null].filter(Boolean).join(" · ")}</p>
                      <p className="mt-1 flex flex-wrap items-center gap-1 text-[10px]">
                        <span className="text-stone-400">cites</span>
                        {row.cites.map((c) => <button key={c.id} type="button" data-testid="citing-cites" onClick={() => { setCiteMode(false); setDetailId(c.id); }} title={c.title} className="rounded-full bg-sky-500/10 px-1.5 py-0.5 font-mono text-sky-700 hover:bg-sky-500/20 dark:text-sky-200">{c.bibtex_key}</button>)}
                        <span className="ml-1 text-stone-400">· seen {new Date(row.first_seen_at).toLocaleDateString()}</span>
                      </p>
                    </div>
                    <div className="flex shrink-0 items-center gap-1 text-[11px]">
                      {row.addable && !showDismissed && <button type="button" data-testid="citing-add" disabled={addCiting.isPending} onClick={() => addCiting.mutate(row)} className="inline-flex items-center gap-1 rounded-md bg-indigo-600 px-2 py-1 font-medium text-white hover:bg-indigo-700 disabled:opacity-50" title={filters.project ? "Add to the library and this project" : "Add to the library"}><Plus className="h-3 w-3" aria-hidden="true" />Add</button>}
                      {!row.addable && !showDismissed && <span className="rounded-md border border-stone-200 px-2 py-1 text-stone-400 dark:border-stone-700" title="No DOI — open it to judge, add by hand if it matters">no DOI</span>}
                      <button type="button" data-testid="citing-dismiss" disabled={dismissCiting.isPending} onClick={() => dismissCiting.mutate({ ids: [row.id], undo: showDismissed })} className="rounded-md border border-stone-300 px-2 py-1 text-stone-500 hover:border-stone-400 hover:text-stone-700 disabled:opacity-50 dark:border-stone-700 dark:text-stone-300">{showDismissed ? "Restore" : "Dismiss"}</button>
                    </div>
                  </li>
                ))}
              </ul>
            </div>
          </section>
        ) : dupMode ? (
          <section className={`${panel} rise flex min-h-[60vh] flex-col overflow-hidden`} style={{ ["--i" as string]: 1 }} data-testid="dup-panel">
            <div className="flex items-center gap-2 border-b border-stone-100 px-4 py-2.5 text-xs dark:border-stone-800">
              <CopyCheck className="h-3.5 w-3.5 text-amber-500" aria-hidden="true" />
              <span className="font-medium text-stone-700 dark:text-stone-100">Duplicates</span>
              <span className="text-stone-400">same DOI or arXiv id, or near-identical titles · the most complete record is pre-selected to keep</span>
              <span className="ml-auto">{modeCopyLink}</span>
              <button type="button" onClick={() => setDupMode(false)} className="text-stone-400 hover:underline">back to the list</button>
            </div>
            <div className="flex-1 space-y-4 overflow-auto p-4">
              {dups.isLoading && <p className="text-sm text-stone-400">Scanning the library…</p>}
              {dups.data && dups.data.groups.length === 0 && (
                <div className="px-4 py-16 text-center">
                  <Check className="mx-auto mb-2 h-6 w-6 text-emerald-400" aria-hidden="true" />
                  <p className="text-sm font-medium text-stone-700 dark:text-stone-100">No duplicates found.</p>
                  <p className="mt-1 text-xs text-stone-400">Imports are deduplicated on the way in; this catches the near-misses.</p>
                </div>
              )}
              {dups.data?.groups.map((g, gi) => {
                const keep = keepChoice[gi] ?? g.keep;
                return (
                  <div key={g.members.map((m) => m.id).join("-")} className="rounded-xl border border-stone-200 dark:border-stone-800">
                    <div className="flex items-center gap-2 border-b border-stone-100 px-3 py-1.5 text-[11px] text-stone-400 dark:border-stone-800">
                      <span>{g.members.length} records · matched by {g.reasons.join(" + ")}</span>
                      <button type="button" disabled={merge.isPending} onClick={() => merge.mutate({ keep, merge: g.members.map((m) => m.id).filter((id) => id !== keep) })} className="ml-auto inline-flex items-center gap-1 rounded-md bg-indigo-600 px-2 py-0.5 font-medium text-white hover:bg-indigo-700 disabled:opacity-50"><CopyCheck className="h-3 w-3" aria-hidden="true" />Merge into the selected</button>
                    </div>
                    <ul className="divide-y divide-stone-100 dark:divide-stone-800">
                      {g.members.map((m) => (
                        <li key={m.id} className={`flex items-start gap-3 px-3 py-2 ${keep === m.id ? "bg-indigo-50 dark:bg-indigo-500/10" : ""}`}>
                          <input type="radio" name={`keep-${gi}`} checked={keep === m.id} onChange={() => setKeepChoice((c) => ({ ...c, [gi]: m.id }))} className="mt-1 accent-indigo-500" aria-label={`Keep ${m.title}`} />
                          <div className="min-w-0 flex-1">
                            <p className="truncate text-sm text-stone-900 dark:text-stone-100">{m.title}</p>
                            <p className="truncate text-[11px] text-stone-400">{[m.year, m.venue, m.doi ? `doi ${m.doi}` : "no DOI", m.bibtex_key].filter(Boolean).join(" · ")}</p>
                            <p className="mt-0.5 flex flex-wrap gap-1 text-[10px]">
                              {m.has_pdf && <span className="rounded-full bg-indigo-500/10 px-1.5 py-0.5 text-indigo-600 dark:text-indigo-300">PDF</span>}
                              {m.projects.map((p) => <span key={p} className="rounded-full bg-stone-100 px-1.5 py-0.5 text-stone-500 dark:bg-stone-800 dark:text-stone-300">{p}</span>)}
                              {m.tags.map((t) => <TagChip key={t} name={t} color={tagColors[t]} />)}
                            </p>
                          </div>
                          <span className="shrink-0 text-[10px] tabular-nums text-stone-400" title="completeness score">{m.score}</span>
                        </li>
                      ))}
                    </ul>
                  </div>
                );
              })}
            </div>
          </section>
        ) : (
        <section className={`${panel} rise flex min-h-[60vh] flex-col overflow-hidden`} style={{ ["--i" as string]: 1 }}>
          <div className="flex flex-wrap items-center gap-2 border-b border-stone-100 px-3 py-2 text-xs dark:border-stone-800">
            <label className="flex items-center gap-1.5 text-stone-500"><input type="checkbox" checked={allSelectedOnPage} onChange={() => setSelected(allSelectedOnPage ? new Set() : new Set(rows.map((r) => r.id)))} className="accent-indigo-500" />{total} result{total === 1 ? "" : "s"}</label>
            {activeChips.map((k) => (
              <button key={k} type="button" onClick={() => set({ [k]: "" } as Partial<Filters>)} className="inline-flex items-center gap-1 rounded-full bg-indigo-500/10 px-2 py-0.5 text-indigo-700 dark:text-indigo-200">{chipLabel(k, filters[k])}<X className="h-3 w-3" aria-hidden="true" /></button>
            ))}
            {activeChips.length > 0 && <button type="button" onClick={() => setFilters({ ...EMPTY, sort: filters.sort })} className="text-stone-400 hover:underline">clear</button>}
            <Link to={`/library/read?${toQuery(effective, 1)}`} className="ml-auto inline-flex items-center gap-1 text-stone-400 hover:text-indigo-600 dark:hover:text-indigo-300" title="Read this view as a flow — one paper at a time, status keys, notes" data-testid="read-these">Read these →</Link>
            <ExportLinks query={toQuery(effective, 1)} what="this view" className="ml-3" />
            <button type="button" data-testid="copy-link" onClick={copyLink} className="inline-flex items-center gap-1 text-stone-400 hover:text-indigo-600 dark:hover:text-indigo-300" title="Copy a link to this view — paste it in a note, a message, or hand it to Claude"><Link2 className="h-3 w-3" aria-hidden="true" />Copy link</button>
            <span className="hidden text-stone-400 lg:inline">· j/k move · enter open · x select · shift-x / shift-click range · ⌘A all · o pdf</span>
            <span className="ml-1 inline-flex overflow-hidden rounded-md border border-stone-200 dark:border-stone-700" role="tablist" aria-label="Library view">
              <button type="button" role="tab" aria-selected={view === "list"} onClick={() => switchView("list")} className={`px-1.5 py-0.5 ${view === "list" ? "bg-indigo-500/15 text-indigo-600 dark:text-indigo-200" : "text-stone-400 hover:text-stone-600 dark:hover:text-stone-200"}`} title="List" data-testid="view-list"><LayoutList className="h-3.5 w-3.5" aria-hidden="true" /></button>
              <button type="button" role="tab" aria-selected={view === "cards"} onClick={() => switchView("cards")} className={`px-1.5 py-0.5 ${view === "cards" ? "bg-indigo-500/15 text-indigo-600 dark:text-indigo-200" : "text-stone-400 hover:text-stone-600 dark:hover:text-stone-200"}`} title="Cards" data-testid="view-cards"><LayoutGrid className="h-3.5 w-3.5" aria-hidden="true" /></button>
            </span>
          </div>
          <div ref={listRef} className={`flex-1 overflow-auto ${view === "cards" ? "grid auto-rows-max grid-cols-1 gap-3 p-3 sm:grid-cols-2 2xl:grid-cols-3" : "divide-y divide-stone-100 dark:divide-stone-800"}`}>
            {list.isLoading && Array.from({ length: 8 }).map((_, i) => <div key={i} className="px-4 py-3"><Skeleton className="mb-1.5 h-4 w-2/3" /><Skeleton className="h-3 w-1/3" /></div>)}
            {rows.map((r, i) => {
              const needs = Boolean(r.extra?.needs_metadata);
              const active = i === cursor;
              if (view === "cards") {
                const status = r.projects[0]?.reading_status;
                const band = r.projects[0]?.color || "#7c6cff";
                return (
                  <div key={r.id} data-row={i} data-testid="library-card" onClick={() => { setCursor(i); setDetailId(r.id); }} onContextMenu={(e) => { setCursor(i); menu.open(e, rowItems(r)); }}
                       className={`group relative flex cursor-pointer flex-col overflow-hidden rounded-xl border bg-white transition-colors dark:bg-stone-900 ${detailId === r.id ? "border-indigo-400 shadow-[0_0_0_1px_rgba(124,108,255,0.4)]" : active ? "border-stone-300 dark:border-stone-600" : "border-stone-200 hover:border-stone-300 dark:border-stone-800 dark:hover:border-stone-700"}`}>
                    <div className="h-1.5 w-full" style={{ background: r.pdf ? band : `${band}66` }} aria-hidden="true" />
                    <div className="flex flex-1 flex-col gap-1.5 p-3">
                      <div className="flex items-start gap-2">
                        <input type="checkbox" checked={selected.has(r.id)} onClick={(e) => e.stopPropagation()} onChange={(e) => onCheck(i, r.id, (e.nativeEvent as MouseEvent).shiftKey)} className="mt-1 accent-indigo-500" aria-label={`Select ${r.title}`} />
                        <p className="line-clamp-3 text-sm font-medium leading-snug text-stone-900 dark:text-stone-100">{r.title}</p>
                      </div>
                      <p className="line-clamp-1 text-xs text-stone-500 dark:text-stone-400">{authorsLine(r, 4) || (needs ? "from a PDF · no metadata yet" : "no authors")}</p>
                      <p className="mt-auto flex flex-wrap items-center gap-1.5 pt-1 text-[10px] text-stone-400">
                        {r.year && <span className="font-mono">{r.year}</span>}
                        {r.venue && <span className="truncate italic">{r.venue}</span>}
                        {status && <span className="rounded-full bg-stone-100 px-1.5 py-0.5 dark:bg-stone-800">{STATUS_LABEL[status] ?? status}</span>}
                        {r.pdf && <span className="rounded-full bg-indigo-500/10 px-1.5 py-0.5 font-medium text-indigo-600 dark:text-indigo-300">PDF</span>}
                        {inProgress(r.progress) && <span className="rounded-full bg-indigo-500/10 px-1.5 py-0.5 tabular-nums text-indigo-600 dark:text-indigo-300" data-testid="card-progress" title="Where the reader left off">{pageLabel(r.progress)}</span>}
                        {!r.retraction_kind && r.notices?.length > 0 && <span data-testid="notice-chip" className="rounded-full bg-amber-500/15 px-1.5 py-0.5 font-semibold uppercase tracking-wide text-amber-700 dark:text-amber-300" title={noticeTitle(r.notices)}>{noticeLabel(r.notices)}</span>}
                        {r.retraction_kind && <span data-testid="retracted-chip" className="rounded-full bg-rose-500/15 px-1.5 py-0.5 font-semibold uppercase tracking-wide text-rose-600 dark:text-rose-300" title={`Crossref lists a ${r.retraction_kind} notice${r.retraction_date ? ` (${r.retraction_date})` : ""}`}>retracted</span>}
                        {r.published_doi && <span data-testid="published-chip" className="rounded-full bg-amber-500/15 px-1.5 py-0.5 font-semibold uppercase tracking-wide text-amber-700 dark:text-amber-300" title={`Published version found${r.published_venue ? ` in ${r.published_venue}` : ""} — upgrade from the detail pane`}>published version</span>}
                        {needs && <span className="rounded-full bg-amber-500/10 px-1.5 py-0.5 font-medium text-amber-600 dark:text-amber-300">needs metadata</span>}
                        {r.tags.slice(0, 3).map((t) => <TagChip key={t} name={t} color={tagColors[t]} />)}
                        {r.citation_count != null && r.citation_count > 0 && <span className="ml-auto tabular-nums">{r.citation_count} cit.</span>}
                      </p>
                    </div>
                  </div>
                );
              }
              return (
                <div key={r.id} data-row={i} data-testid="library-row" onClick={() => { setCursor(i); setDetailId(r.id); }} onContextMenu={(e) => { setCursor(i); menu.open(e, rowItems(r)); }} className={`group flex cursor-pointer items-start gap-3 px-3 py-2.5 transition-colors ${detailId === r.id ? "bg-indigo-50 dark:bg-indigo-500/10" : active ? "bg-stone-50 dark:bg-stone-800/60" : "hover:bg-stone-50 dark:hover:bg-stone-800/40"}`}>
                  <input type="checkbox" checked={selected.has(r.id)} onClick={(e) => e.stopPropagation()} onChange={(e) => onCheck(i, r.id, (e.nativeEvent as MouseEvent).shiftKey)} className="mt-1 accent-indigo-500" aria-label={`Select ${r.title}`} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-stone-900 dark:text-stone-100">{r.title}</p>
                    <p className="mt-0.5 flex items-center gap-1.5 truncate text-xs text-stone-400 dark:text-stone-400">
                      <span className="truncate">{[authorsLine(r), r.year, r.venue].filter(Boolean).join(" · ") || (needs ? "from a PDF · no metadata yet" : "no details yet")}</span>
                    </p>
                    {inProgress(r.progress) && (
                      <div className="mt-1 flex items-center gap-2" data-testid="row-progress" title={`Reading — ${pageLabel(r.progress)}`}>
                        <div className="h-0.5 w-24 overflow-hidden rounded-full bg-stone-200 dark:bg-stone-700"><div className="h-0.5 rounded-full bg-indigo-500" style={{ width: `${r.progress.percent ?? 50}%` }} /></div>
                        <span className="text-[10px] tabular-nums text-stone-400">{pageLabel(r.progress)}</span>
                      </div>
                    )}
                  </div>
                  <div className="flex shrink-0 items-center gap-1.5 pt-0.5">
                    {r.projects.map((p) => <span key={p.slug} title={`${p.name} · ${STATUS_LABEL[p.reading_status] ?? p.reading_status}`} className="h-2 w-2 rounded-full" style={{ background: p.color }} />)}
                    {r.tags.slice(0, 3).map((t) => <TagChip key={t} name={t} color={tagColors[t]} className="text-[10px]" />)}
                    {!r.retraction_kind && r.notices?.length > 0 && <span data-testid="notice-chip" className="rounded-full bg-amber-500/15 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-700 dark:text-amber-300" title={noticeTitle(r.notices)}>{noticeLabel(r.notices)}</span>}
                    {r.retraction_kind && <span data-testid="retracted-chip" className="rounded-full bg-rose-500/15 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-rose-600 dark:text-rose-300" title={`Crossref lists a ${r.retraction_kind} notice${r.retraction_date ? ` (${r.retraction_date})` : ""}`}>retracted</span>}
                    {r.published_doi && <span data-testid="published-chip" className="rounded-full bg-amber-500/15 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-700 dark:text-amber-300" title={`Published version found${r.published_venue ? ` in ${r.published_venue}` : ""}`}>published version</span>}
                    {needs && <span className="rounded-full bg-amber-500/10 px-1.5 py-0.5 text-[10px] font-medium text-amber-600 dark:text-amber-300">needs metadata</span>}
                    {r.pdf && <span className="rounded-full bg-indigo-500/10 px-1.5 py-0.5 text-[10px] font-medium text-indigo-600 dark:text-indigo-300">PDF</span>}
                    {!r.pdf && pdfLookups.has(r.id) && <span data-testid="pdf-looking" className="inline-flex items-center gap-1 rounded-full bg-indigo-500/10 px-1.5 py-0.5 text-[10px] text-indigo-500 dark:text-indigo-300"><Loader2 className="h-2.5 w-2.5 animate-spin" aria-hidden="true" />looking…</span>}
                    {!r.pdf && !pdfLookups.has(r.id) && typeof r.extra?.oa_pdf === "string" && <span data-testid="pdf-miss" title={`${r.extra.oa_pdf} Right-click → Find PDF to try again.`} className="rounded-full bg-stone-100 px-1.5 py-0.5 text-[10px] text-stone-400 dark:bg-stone-800 dark:text-stone-500">no PDF found</span>}
                    {r.pdf_match && <span className="rounded-full bg-violet-500/15 px-1.5 py-0.5 text-[10px] font-medium text-violet-700 dark:text-violet-200" title="Your search matched inside the PDF text"><Search className="mr-0.5 inline h-2.5 w-2.5" aria-hidden="true" />in PDF</span>}
                    {r.citation_count != null && r.citation_count > 0 && <span className="text-[10px] tabular-nums text-stone-400">{r.citation_count} cit.</span>}
                  </div>
                </div>
              );
            })}
            {!list.isLoading && rows.length === 0 && (
              <div className="px-4 py-16 text-center">
                <BookOpen className="mx-auto mb-3 h-8 w-8 text-indigo-300" aria-hidden="true" />
                <p className="text-sm font-medium text-stone-600 dark:text-stone-200">{activeChips.length || q ? "Nothing matches these filters" : "Your library is empty"}</p>
                <p className="mx-auto mt-1 max-w-sm text-xs text-stone-400">{activeChips.length || q ? "Clear a filter, or import more papers." : "Drop a folder of PDFs onto this page, paste BibTeX, or pull your Zotero library — dedupe is automatic."}</p>
              </div>
            )}
            {list.hasNextPage && (
              <div className="p-3 text-center"><button type="button" onClick={() => list.fetchNextPage()} disabled={list.isFetchingNextPage} className="inline-flex items-center gap-1 rounded-lg border border-stone-300 px-3 py-1.5 text-xs text-stone-600 hover:border-indigo-300 dark:border-stone-700 dark:text-stone-300">{list.isFetchingNextPage ? <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" /> : <ChevronDown className="h-3 w-3" aria-hidden="true" />}Load more ({total - rows.length} left)</button></div>
            )}
          </div>
          {selected.size > 0 && (
            <div className="hairline-gradient flex flex-wrap items-center gap-2 border-t border-stone-100 bg-stone-50 px-3 py-2 text-xs dark:border-stone-800 dark:bg-stone-950/60">
              <span className="font-medium text-stone-700 dark:text-stone-100">{selected.size} selected</span>
              <select value={bulkProject} onChange={(e) => setBulkProject(e.target.value)} className="rounded-md border border-stone-300 bg-white px-1.5 py-1 text-xs dark:border-stone-700 dark:bg-stone-800"><option value="">project…</option>{f?.all_projects.map((p) => <option key={p.slug} value={p.slug}>{p.name}</option>)}</select>
              <button type="button" disabled={!bulkProject || bulk.isPending} onClick={() => bulk.mutate({ ids: [...selected], action: "link", project: bulkProject })} className="inline-flex items-center gap-1 rounded-md bg-indigo-600 px-2 py-1 font-medium text-white hover:bg-indigo-700 disabled:opacity-40"><FolderPlus className="h-3 w-3" aria-hidden="true" />Link</button>
              {(bulkProject || filters.project) && (
                <select defaultValue="" onChange={(e) => { if (e.target.value) { bulk.mutate({ ids: [...selected], action: "status", project: bulkProject || filters.project, value: e.target.value }); e.target.value = ""; } }} className="rounded-md border border-stone-300 bg-white px-1.5 py-1 text-xs dark:border-stone-700 dark:bg-stone-800"><option value="">mark as…</option>{Object.entries(STATUS_LABEL).map(([k, l]) => <option key={k} value={k}>{l}</option>)}</select>
              )}
              <form onSubmit={(e) => { e.preventDefault(); const t = bulkTag.trim(); if (t) { bulk.mutate({ ids: [...selected], action: "tag", value: t }); setBulkTag(""); } }} className="flex items-center gap-1">
                <input value={bulkTag} onChange={(e) => setBulkTag(e.target.value)} list="library-tag-names" placeholder="tag…" className="w-24 rounded-md border border-stone-300 bg-white px-1.5 py-1 text-xs dark:border-stone-700 dark:bg-stone-800" />
                <datalist id="library-tag-names">{f?.tags.map((t) => <option key={t.name} value={t.name} />)}</datalist>
                <button type="submit" disabled={!bulkTag.trim() || bulk.isPending} className="inline-flex items-center gap-1 rounded-md border border-stone-300 px-2 py-1 text-stone-600 hover:border-indigo-300 disabled:opacity-40 dark:border-stone-700 dark:text-stone-300"><TagIcon className="h-3 w-3" aria-hidden="true" />Tag</button>
              </form>
              <ExportLinks query={`ids=${[...selected].join(",")}`} what="the selection" className="rounded-md border border-stone-300 px-2 py-1 dark:border-stone-700" />
              <button type="button" onClick={async () => { const text = await (await fetch(`/api/v1/references/export/?ids=${[...selected].join(",")}`, { credentials: "same-origin" })).text(); await navigator.clipboard?.writeText(text); flash(`Copied BibTeX for ${selected.size} reference(s).`); }} className="inline-flex items-center gap-1 rounded-md border border-stone-300 px-2 py-1 text-stone-600 hover:border-indigo-300 dark:border-stone-700 dark:text-stone-300" title="Copy BibTeX to the clipboard"><Copy className="h-3 w-3" aria-hidden="true" />Copy BibTeX</button>
              <button type="button" onClick={async () => { const b = await api<{ text: string }>(`/references/cite/?ids=${[...selected].join(",")}&style=${citeStyle}`); await navigator.clipboard?.writeText(b.text); flash(`Copied ${selected.size} citation(s) in ${STYLES.find(([k]) => k === citeStyle)?.[1] ?? citeStyle}.`); }} className="inline-flex items-center gap-1 rounded-md border border-stone-300 px-2 py-1 text-stone-600 hover:border-indigo-300 dark:border-stone-700 dark:text-stone-300" title="Copy a formatted bibliography of the selection"><Quote className="h-3 w-3" aria-hidden="true" />Copy citations</button>
              <button type="button" disabled={bulk.isPending} onClick={() => bulk.mutate({ ids: [...selected], action: "fetch_pdf" })} className="inline-flex items-center gap-1 rounded-md border border-stone-300 px-2 py-1 text-stone-600 hover:border-indigo-300 dark:border-stone-700 dark:text-stone-300" title="Find and attach open-access PDFs"><Download className="h-3 w-3" aria-hidden="true" />Fetch OA PDFs</button>
              <button type="button" disabled={bulk.isPending} onClick={() => bulk.mutate({ ids: [...selected], action: "find_metadata" })} className="inline-flex items-center gap-1 rounded-md border border-stone-300 px-2 py-1 text-stone-600 hover:border-indigo-300 dark:border-stone-700 dark:text-stone-300"><Wand2 className="h-3 w-3" aria-hidden="true" />Find metadata</button>
              <button type="button" disabled={bulk.isPending} onClick={async () => { if (await confirmDialog({ title: `Delete ${selected.size} reference${selected.size === 1 ? "" : "s"} from the library?`, body: "Their project links, highlights and PDFs go too.", danger: true, confirmLabel: "Delete" })) bulk.mutate({ ids: [...selected], action: "delete" }); }} className="inline-flex items-center gap-1 rounded-md border border-red-300/60 px-2 py-1 text-red-600 hover:bg-red-500/10 dark:text-red-300"><Trash2 className="h-3 w-3" aria-hidden="true" />Delete</button>
              <button type="button" onClick={() => setSelected(new Set())} className="ml-auto text-stone-400 hover:underline">clear</button>
            </div>
          )}
        </section>

        )}

        {/* detail */}
        <aside className={`${panel} rise h-fit p-5 lg:sticky lg:top-6`} style={{ ["--i" as string]: 2 }}>
          {!detail ? (
            <div className="py-10 text-center text-sm text-stone-400">
              <Sparkles className="mx-auto mb-2 h-6 w-6 text-indigo-300" aria-hidden="true" />
              Select a paper to see its abstract, links, and related work.
            </div>
          ) : (
            <DetailPane r={detail} onAuthor={(family) => toggle("author", family)} authorFilter={filters.author} onFindMeta={() => findMeta.mutate(detail.id)} finding={findMeta.isPending} onCheckRetraction={() => checkRetractions.mutate([detail.id])} checkingRetraction={checkRetractions.isPending} onCheckPreprint={() => checkPreprints.mutate([detail.id])} checkingPreprint={checkPreprints.isPending} onUpgrade={() => upgradePreprint.mutate(detail.id)} upgrading={upgradePreprint.isPending} onShowCiting={() => openCiting(detail.id)} highlights={highlights.data ?? []} readingNotes={readingNotes.data ?? []} reading={readerId === detail.id} onRead={() => openReader(detail)} onJump={(page) => { openReader(detail); setJump({ page, nonce: Date.now() }); }} onEditHighlight={(id, patch) => editHighlight.mutate({ id, ...patch })} onRemoveHighlight={(id) => removeHighlight.mutate(id)} onSaveNotes={(id, notes) => saveNotes.mutate({ id, notes })} onFetchPdf={() => fetchPdf.mutate(detail.id)} fetchingPdf={fetchPdf.isPending} q={effective.q} onFind={(page, term) => { openReader(detail, term); setJump({ page, nonce: Date.now() }); }} onIndexText={() => indexText.mutate(detail.id)} onLitNote={(project) => litNote.mutate({ reference: detail.id, project })} projects={f?.all_projects ?? []} onLink={(slug) => bulk.mutate({ ids: [detail.id], action: "link", project: slug })} citeStyle={citeStyle} onStyle={setCiteStyle} onCopied={flash} allTags={f?.tags.map((t) => t.name) ?? []} tagColors={tagColors} onTag={(tag, remove) => bulk.mutate({ ids: [detail.id], action: remove ? "untag" : "tag", value: tag })} currentProject={filters.project} onAdded={(r) => { invalidate(); petReact("paper"); flash(`Added “${r.title.slice(0, 60)}” to the library${filters.project ? " and this project" : ""}.`); }} />
          )}
        </aside>
      </div>
      {menu.element}
      {toast && <div className="glow-accent fixed bottom-5 right-5 z-50 rounded-xl bg-stone-900 px-4 py-2.5 text-sm text-stone-100 dark:bg-stone-800">{toast}</div>}
    </div>
  );
}

function DetailPane({ r, onAuthor, authorFilter, onFindMeta, finding, onCheckRetraction, checkingRetraction, onCheckPreprint, checkingPreprint, onUpgrade, upgrading, onShowCiting, projects, onLink, currentProject, onAdded, citeStyle, onStyle, onCopied, allTags, tagColors, onTag, highlights, readingNotes, reading, onRead, onJump, onEditHighlight, onRemoveHighlight, onSaveNotes, onFetchPdf, fetchingPdf, q, onFind, onIndexText, onLitNote }: { r: Ref; onAuthor: (family: string) => void; authorFilter: string; allTags: string[]; tagColors: TagColors; onTag: (tag: string, remove: boolean) => void; onFindMeta: () => void; finding: boolean; onCheckRetraction: () => void; checkingRetraction: boolean; onCheckPreprint: () => void; checkingPreprint: boolean; onUpgrade: () => void; upgrading: boolean; onShowCiting: () => void; highlights: Highlight[]; readingNotes: ReadingNote[]; reading: boolean; onRead: () => void; onJump: (page: number) => void; onEditHighlight: (id: number, patch: { comment?: string; color?: string }) => void; onRemoveHighlight: (id: number) => void; onSaveNotes: (id: number, notes: string) => void; onFetchPdf: () => void; fetchingPdf: boolean; q: string; onFind: (page: number, term: string) => void; onIndexText: () => void; onLitNote: (project: string) => void; projects: { slug: string; name: string; color: string }[]; onLink: (slug: string) => void; currentProject: string; onAdded: (r: Ref) => void; citeStyle: string; onStyle: (s: string) => void; onCopied: (msg: string) => void }) {
  const [full, setFull] = useState(false);
  const [newTag, setNewTag] = useState("");
  const citation = useQuery({ queryKey: ["cite", r.id, citeStyle], queryFn: () => api<Citation>(`/references/${r.id}/cite/?style=${citeStyle}`), staleTime: 5 * 60_000 });
  const copy = async (text: string, what: string) => { await navigator.clipboard?.writeText(text); onCopied(`Copied ${what}.`); };
  const [lens, setLens] = useState<"similar" | "references" | "cited_by" | null>(null);
  const discover = useQuery({
    queryKey: ["discover", r.id, lens],
    queryFn: () => api<{ kind: string; results: DiscoverRow[]; error?: string }>(`/references/${r.id}/discover/?kind=${lens}&limit=15`),
    enabled: lens !== null,
    staleTime: 10 * 60_000,
  });
  const [added, setAdded] = useState<Record<string, number>>({});
  const add = useMutation({
    mutationFn: (doi: string) => api<Ref>("/references/by-doi/", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(currentProject ? { doi, project: currentProject } : { doi }) }),
    onSuccess: (ref, doi) => { setAdded((m) => ({ ...m, [doi]: ref.id })); onAdded(ref); },
  });
  const related = useQuery({ queryKey: ["related", r.id], queryFn: () => api<{ id: number; title: string; year: number | null; score: number }[]>(`/references/${r.id}/related/`), staleTime: 60_000 });
  const needs = Boolean(r.extra?.needs_metadata);
  const inProjects = new Set(r.projects.map((p) => p.slug));
  return (
    <div key={r.id} className="rise">
      <h2 className="font-display text-lg font-semibold leading-snug text-stone-900 dark:text-stone-100">{r.title}</h2>
      <p className="mt-1.5 text-sm text-stone-500 dark:text-stone-300">
        {(r.authors ?? []).filter((a) => a.given || a.family).length === 0 && "Unknown authors"}
        {(r.authors ?? []).filter((a) => a.given || a.family).map((a, i, all) => (
          <span key={`${a.family}-${a.given}-${i}`}>
            {a.family ? (
              <button type="button" onClick={() => onAuthor(a.family as string)} className={`rounded-sm underline decoration-dotted decoration-stone-400/70 underline-offset-2 transition-colors hover:text-indigo-600 dark:hover:text-indigo-300 ${authorFilter.toLowerCase() === a.family.toLowerCase() ? "text-indigo-600 dark:text-indigo-300" : ""}`} title={`Everything by ${a.family} in your library`} data-testid="author-link">{[a.given, a.family].filter(Boolean).join(" ")}</button>
            ) : (
              <span>{a.given}</span>
            )}
            {i < all.length - 1 ? ", " : ""}
          </span>
        ))}
      </p>
      <p className="mt-1 text-xs text-stone-400">{[r.year, r.venue, r.entry_type].filter(Boolean).join(" · ")}{r.citation_count != null ? ` · ${r.citation_count} citations` : ""}</p>
      {r.retraction_kind && (
        <div data-testid="retraction-banner" className="mt-3 rounded-xl border border-rose-400/50 bg-rose-500/10 p-3 text-xs text-rose-800 dark:text-rose-200">
          <p className="flex items-center gap-1.5 font-semibold"><ShieldAlert className="h-3.5 w-3.5" aria-hidden="true" />This paper has been {r.retraction_kind === "retraction" ? "retracted" : r.retraction_kind === "withdrawal" ? "withdrawn" : "removed"}{r.retraction_date ? ` · ${r.retraction_date}` : ""}</p>
          <p className="mt-1 text-rose-700/90 dark:text-rose-200/80">Crossref lists a {r.retraction_kind} notice{r.retraction_notice ? <>: <a href={`https://doi.org/${r.retraction_notice}`} target="_blank" rel="noreferrer" className="underline">{r.retraction_notice}</a></> : null}. Cite it only to discuss the retraction — the manuscript pre-flight flags it.</p>
          <p className="mt-1 flex items-center gap-2 text-[11px] text-rose-700/70 dark:text-rose-200/60">{r.retraction_checked_at ? `checked ${new Date(r.retraction_checked_at).toLocaleDateString()}` : "not checked yet"}<button type="button" onClick={onCheckRetraction} disabled={checkingRetraction} className="underline disabled:opacity-50">re-check</button></p>
        </div>
      )}
      {!r.retraction_kind && r.notices?.length > 0 && (
        <div data-testid="notice-banner" className="mt-3 rounded-xl border border-amber-400/50 bg-amber-500/10 p-3 text-xs text-amber-900 dark:text-amber-100">
          <p className="flex items-center gap-1.5 font-semibold"><MessageSquareWarning className="h-3.5 w-3.5" aria-hidden="true" />{r.notices.some((n) => n.kind === "expression_of_concern") ? "An expression of concern has been issued" : `This paper has been corrected${r.notices.length > 1 ? ` (${r.notices.length} notices)` : ""}`}</p>
          <ul className="mt-1 space-y-0.5 text-amber-800/90 dark:text-amber-100/80">
            {r.notices.map((n) => (
              <li key={n.notice || n.kind}>{noticeWord(n)[0].toUpperCase() + noticeWord(n).slice(1)}{n.date ? ` · ${n.date}` : ""}{n.notice ? <>: <a href={`https://doi.org/${n.notice}`} target="_blank" rel="noreferrer" className="underline">{n.notice}</a></> : null}</li>
            ))}
          </ul>
          <p className="mt-1 text-[11px] text-amber-800/70 dark:text-amber-100/60">Not a retraction — read the notice before citing the result; the manuscript pre-flight warns on it.</p>
        </div>
      )}
      {!r.retraction_kind && r.doi && (
        <p className="mt-2 flex items-center gap-1.5 text-[11px] text-stone-400" data-testid="retraction-ok"><ShieldCheck className="h-3 w-3" aria-hidden="true" />{r.retraction_checked_at ? `No retraction notice · checked ${new Date(r.retraction_checked_at).toLocaleDateString()}` : "Retraction not checked yet"} · <button type="button" onClick={onCheckRetraction} disabled={checkingRetraction} className="underline disabled:opacity-50">{checkingRetraction ? "asking…" : "check"}</button></p>
      )}
      {r.published_doi && (
        <div data-testid="published-banner" className="mt-3 rounded-xl border border-amber-400/50 bg-amber-500/10 p-3 text-xs text-amber-900 dark:text-amber-100">
          <p className="flex items-center gap-1.5 font-semibold"><ArrowUpCircle className="h-3.5 w-3.5" aria-hidden="true" />A published version exists{r.published_venue ? ` · ${r.published_venue}` : ""}{typeof r.extra?.arxiv_version === "string" && r.extra.arxiv_version ? ` · matches arXiv ${r.extra.arxiv_version}` : ""}</p>
          <p className="mt-1 text-amber-800/90 dark:text-amber-100/80">This is the arXiv preprint; the paper has since appeared as <a href={`https://doi.org/${r.published_doi}`} target="_blank" rel="noreferrer" className="underline">{r.published_doi}</a>. Upgrading makes every manuscript that cites <span className="font-mono">{r.bibtex_key}</span> cite the published version — the key stays.</p>
          <p className="mt-2 flex flex-wrap items-center gap-2">
            <button type="button" data-testid="upgrade-preprint" onClick={onUpgrade} disabled={upgrading} className="inline-flex items-center gap-1 rounded-md bg-amber-600 px-2 py-1 text-[11px] font-semibold text-white hover:bg-amber-700 disabled:opacity-60">{upgrading ? <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" /> : <ArrowUpCircle className="h-3 w-3" aria-hidden="true" />}{upgrading ? "Upgrading…" : "Use the published version"}</button>
            <span className="text-[11px] text-amber-800/70 dark:text-amber-100/60">{r.published_checked_at ? `found ${new Date(r.published_checked_at).toLocaleDateString()}` : ""}</span>
          </p>
        </div>
      )}
      {r.preprint && !r.published_doi && (
        <p className="mt-2 flex items-center gap-1.5 text-[11px] text-stone-400" data-testid="preprint-line"><FileText className="h-3 w-3" aria-hidden="true" />{r.published_checked_at ? `Preprint · no published version found · checked ${new Date(r.published_checked_at).toLocaleDateString()}` : "Preprint · published version not checked yet"} · <button type="button" onClick={onCheckPreprint} disabled={checkingPreprint} className="underline disabled:opacity-50">{checkingPreprint ? "asking…" : "check"}</button></p>
      )}
      <CitingLine r={r} onShow={onShowCiting} />
      {needs && (
        <div className="mt-3 rounded-xl border border-amber-400/40 bg-amber-500/10 p-3 text-xs text-amber-800 dark:text-amber-200">
          This paper came from a PDF without a readable DOI. <button type="button" onClick={onFindMeta} disabled={finding} className="ml-1 inline-flex items-center gap-1 rounded-md bg-amber-500/20 px-2 py-0.5 font-medium hover:bg-amber-500/30 disabled:opacity-50"><Wand2 className="h-3 w-3" aria-hidden="true" />{finding ? "Searching…" : "Find metadata"}</button>
        </div>
      )}
      {r.abstract && (
        <p className={`mt-3 text-sm leading-relaxed text-stone-600 dark:text-stone-300 ${full ? "" : "line-clamp-6"}`} onClick={() => setFull((v) => !v)}>{r.abstract}</p>
      )}
      <div className="mt-4 flex flex-wrap gap-1.5 text-xs">
        <Link to={`/references/${r.id}`} className="rounded-md bg-indigo-600 px-2.5 py-1 font-medium text-white hover:bg-indigo-700">Open</Link>
        {r.pdf ? (
          <button type="button" onClick={onRead} className={`inline-flex items-center gap-1 rounded-md border px-2.5 py-1 ${reading ? "border-indigo-400 bg-indigo-500/10 text-indigo-700 dark:text-indigo-200" : "border-stone-300 text-stone-600 hover:border-indigo-300 dark:border-stone-700 dark:text-stone-300"}`} title={inProgress(r.progress) ? `Pick up where you left off — ${pageLabel(r.progress)} (o)` : "Read and highlight here (o)"} data-testid={!reading && inProgress(r.progress) ? "resume-read" : undefined}><BookOpen className="h-3 w-3" aria-hidden="true" />{reading ? "Reading" : inProgress(r.progress) ? `Resume · ${pageLabel(r.progress)}` : "Read"}</button>
        ) : (
          <button type="button" onClick={onFetchPdf} disabled={fetchingPdf || !(r.doi || r.arxiv_id)} className="inline-flex items-center gap-1 rounded-md border border-stone-300 px-2.5 py-1 text-stone-600 hover:border-indigo-300 disabled:opacity-50 dark:border-stone-700 dark:text-stone-300" title={r.doi || r.arxiv_id ? "Look for a free PDF — arXiv, Unpaywall, Semantic Scholar, then OpenAlex" : "Needs a DOI or arXiv id to look up a PDF"}>{fetchingPdf ? <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" /> : <Download className="h-3 w-3" aria-hidden="true" />}Find PDF</button>
        )}
        {r.pdf && typeof r.extra?.oa_source === "string" && <span data-testid="pdf-source" className="inline-flex items-center self-center text-[11px] text-stone-400 dark:text-stone-500" title={typeof r.extra?.oa_pdf === "string" ? r.extra.oa_pdf : undefined}>via {PDF_SOURCES[r.extra.oa_source as string] ?? String(r.extra.oa_source)}</span>}
        {r.doi && <a href={`https://doi.org/${r.doi}`} target="_blank" rel="noreferrer" className="rounded-md border border-stone-300 px-2.5 py-1 text-stone-600 hover:border-indigo-300 dark:border-stone-700 dark:text-stone-300">DOI</a>}
        {r.url && !r.doi && <a href={r.url} target="_blank" rel="noreferrer" className="rounded-md border border-stone-300 px-2.5 py-1 text-stone-600 hover:border-indigo-300 dark:border-stone-700 dark:text-stone-300">Link</a>}
        {r.projects.length > 0 && (
          <button type="button" onClick={() => onLitNote(r.projects.some((p) => p.slug === currentProject) ? currentProject : r.projects[0].slug)} className="inline-flex items-center gap-1 rounded-md border border-stone-300 px-2.5 py-1 text-stone-600 hover:border-indigo-300 dark:border-stone-700 dark:text-stone-300" title={`Start a literature note about this paper in ${r.projects.some((p) => p.slug === currentProject) ? currentProject : r.projects[0].name} (claims, method, limitations, highlights)`}><NotebookPen className="h-3 w-3" aria-hidden="true" />Note</button>
        )}
        <button type="button" onClick={() => navigator.clipboard?.writeText(r.bibtex_key)} title="Copy cite key" className="rounded-md border border-stone-300 px-2.5 py-1 font-mono text-stone-500 hover:border-indigo-300 dark:border-stone-700 dark:text-stone-300">{r.bibtex_key}</button>
      </div>
      <div className="mt-4 flex flex-wrap items-center gap-1.5">
        {r.tags.map((t) => (
          <TagChip key={t} name={t} color={tagColors[t]} className="px-2 text-[11px]">
            <button type="button" onClick={() => onTag(t, true)} aria-label={`Remove tag ${t}`} className="ml-0.5 opacity-60 hover:opacity-100"><X className="h-3 w-3" aria-hidden="true" /></button>
          </TagChip>
        ))}
        <form onSubmit={(e) => { e.preventDefault(); const t = newTag.trim(); if (t) { onTag(t, false); setNewTag(""); } }}>
          <input value={newTag} onChange={(e) => setNewTag(e.target.value)} list="detail-tag-names" placeholder="+ tag" className="w-20 rounded-full border border-dashed border-stone-300 bg-transparent px-2 py-0.5 text-[11px] placeholder:text-stone-400 focus:w-32 focus:border-indigo-400 focus:outline-none dark:border-stone-700" />
          <datalist id="detail-tag-names">{allTags.map((t) => <option key={t} value={t} />)}</datalist>
        </form>
      </div>
      <FoundInPdf r={r} q={q} onFind={onFind} onIndexText={onIndexText} />
      <TldrBlock r={r} onJump={onJump} onIndexText={onIndexText} />
      <HighlightsBlock r={r} highlights={highlights} onJump={onJump} onEdit={onEditHighlight} onRemove={onRemoveHighlight} onCopied={onCopied} />
      <ReadingNotesBlock notes={readingNotes} onSave={onSaveNotes} />
      <div className="mt-5">
        <div className="mb-1.5 flex items-center justify-between">
          <p className={`${railH} mb-0`}><Quote className="mr-1 inline h-3 w-3" aria-hidden="true" />Cite</p>
          <select value={citeStyle} onChange={(e) => onStyle(e.target.value)} className="rounded-md border border-stone-300 bg-white px-1.5 py-0.5 text-[11px] dark:border-stone-700 dark:bg-stone-800" aria-label="Citation style">
            {STYLES.map(([k, label]) => <option key={k} value={k}>{label}</option>)}
          </select>
        </div>
        {citation.data ? (
          <div className="rounded-xl border border-stone-200 bg-stone-50 p-3 dark:border-stone-800 dark:bg-stone-950/40">
            <p className="text-xs leading-relaxed text-stone-700 dark:text-stone-200" dangerouslySetInnerHTML={{ __html: citation.data.html }} />
            <div className="mt-2 flex flex-wrap gap-1.5 text-[11px]">
              <button type="button" onClick={() => copy(citation.data!.text, `the ${citation.data!.label} citation`)} className="inline-flex items-center gap-1 rounded-md bg-indigo-600 px-2 py-0.5 font-medium text-white hover:bg-indigo-700"><Copy className="h-3 w-3" aria-hidden="true" />Copy citation</button>
              <button type="button" onClick={() => copy(citation.data!.intext, "the in-text citation")} className="rounded-md border border-stone-300 px-2 py-0.5 text-stone-600 hover:border-indigo-300 dark:border-stone-700 dark:text-stone-300" title="In-text form">{citation.data.intext}</button>
            </div>
          </div>
        ) : <p className="text-xs text-stone-400">Formatting…</p>}
      </div>
      <div className="mt-5">
        <p className={railH}>In projects</p>
        {r.projects.length === 0 && <p className="text-xs text-stone-400">Not filed in any project yet.</p>}
        <ul className="space-y-1 text-sm">
          {r.projects.map((p) => (
            <li key={p.slug} className="flex items-center gap-2"><span className="h-2 w-2 rounded-full" style={{ background: p.color }} /><Link to={`/projects/${p.slug}/literature`} className="min-w-0 flex-1 truncate hover:underline dark:text-stone-100">{p.name}</Link><span className="text-xs text-stone-400">{STATUS_LABEL[p.reading_status] ?? p.reading_status}{p.finished_at ? ` · finished ${dayLabel(p.finished_at)}` : p.started_at ? ` · started ${dayLabel(p.started_at)}` : ""}</span></li>
          ))}
        </ul>
        {projects.some((p) => !inProjects.has(p.slug)) && (
          <select defaultValue="" onChange={(e) => { if (e.target.value) { onLink(e.target.value); e.target.value = ""; } }} className="mt-2 w-full rounded-md border border-stone-300 bg-white px-2 py-1 text-xs dark:border-stone-700 dark:bg-stone-800">
            <option value="">+ file into a project…</option>
            {projects.filter((p) => !inProjects.has(p.slug)).map((p) => <option key={p.slug} value={p.slug}>{p.name}</option>)}
          </select>
        )}
      </div>
      <div className="mt-5">
        <p className={railH}><Telescope className="mr-1 inline h-3 w-3" aria-hidden="true" />Discover beyond your library</p>
        <div className="mb-2 flex gap-1 text-xs">
          {([["similar", "Similar"], ["references", "It cites"], ["cited_by", "Cited by"]] as const).map(([k, label]) => (
            <button key={k} type="button" onClick={() => setLens(k)} className={`rounded-md px-2 py-1 transition-colors ${lens === k ? "bg-indigo-500/20 text-indigo-700 dark:text-indigo-200" : "text-stone-500 hover:bg-stone-100 dark:hover:bg-stone-800"}`}>{label}</button>
          ))}
        </div>
        {lens === null && <p className="text-xs text-stone-400">Pick a lens: OpenAlex finds related work, the papers this one cites, or the papers citing it — each addable in one click{currentProject ? " into the current project" : ""}.</p>}
        {lens !== null && discover.isLoading && <p className="flex items-center gap-1.5 text-xs text-stone-400"><Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" />Asking OpenAlex…</p>}
        {lens !== null && discover.data?.error && <p className="rounded-lg bg-amber-500/10 px-2.5 py-1.5 text-xs text-amber-700 dark:text-amber-200">{discover.data.error}</p>}
        {lens !== null && discover.data && !discover.data.error && discover.data.results.length === 0 && <p className="text-xs text-stone-400">Nothing found — OpenAlex doesn't know this paper (no DOI?) or has no {lens === "cited_by" ? "citations" : lens === "references" ? "reference list" : "related works"} for it yet.</p>}
        {lens !== null && discover.data && discover.data.results.length > 0 && (
          <ul className="max-h-72 space-y-1.5 overflow-auto pr-1 text-sm">
            {discover.data.results.map((row) => {
              const libraryId = row.library_id ?? added[row.doi];
              return (
                <li key={row.openalex_id || row.doi || row.title} className="flex items-start gap-2">
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-stone-800 dark:text-stone-100" title={row.title}>{row.title}</p>
                    <p className="truncate text-[11px] text-stone-400">{[row.authors.join(", ") + (row.more_authors ? ` +${row.more_authors}` : ""), row.year, row.venue].filter(Boolean).join(" · ")}{row.citations != null ? ` · ${row.citations} cit.` : ""}</p>
                  </div>
                  {libraryId ? (
                    <Link to={`/references/${libraryId}`} className="shrink-0 rounded-md bg-stone-100 px-2 py-0.5 text-[11px] text-stone-500 dark:bg-stone-800 dark:text-stone-300" title="Already in your library">in library</Link>
                  ) : row.addable ? (
                    <button type="button" disabled={add.isPending} onClick={() => add.mutate(row.doi)} className="inline-flex shrink-0 items-center gap-0.5 rounded-md bg-indigo-600 px-2 py-0.5 text-[11px] font-medium text-white hover:bg-indigo-700 disabled:opacity-50"><Plus className="h-3 w-3" aria-hidden="true" />Add</button>
                  ) : (
                    <a href={`https://openalex.org/${row.openalex_id}`} target="_blank" rel="noreferrer" className="shrink-0 text-stone-400" title="No DOI — open on OpenAlex"><ExternalLink className="h-3.5 w-3.5" aria-hidden="true" /></a>
                  )}
                </li>
              );
            })}
          </ul>
        )}
      </div>
      <div className="mt-5">
        <p className={railH}>Related in your library</p>
        {related.data?.length ? (
          <ul className="space-y-1 text-sm">
            {related.data.slice(0, 5).map((x) => <li key={x.id}><Link to={`/references/${x.id}`} className="block truncate text-stone-700 hover:text-indigo-700 dark:text-stone-200 dark:hover:text-indigo-300" title={x.title}>{x.title}<span className="ml-1 text-xs text-stone-400">{x.year ?? ""}</span></Link></li>)}
          </ul>
        ) : <p className="text-xs text-stone-400">{related.isLoading ? "Finding…" : "Nothing similar yet."}</p>}
      </div>
    </div>
  );
}

/** tl;dr per section (#395): the paper's headings, two key sentences each, page links. */
function TldrBlock({ r, onJump, onIndexText }: { r: Ref; onJump: (page: number) => void; onIndexText: () => void }) {
  const [open, setOpen] = useState(false);
  const tldr = useQuery({ queryKey: ["tldr", r.id], queryFn: () => api<{ source: string; sections: { title: string; page: number | null; sentences: string[] }[]; reason?: string }>(`/references/${r.id}/tldr/`), enabled: open, staleTime: 10 * 60_000 });
  return (
    <div className="mt-5" data-testid="tldr-block">
      <div className="flex items-center justify-between">
        <p className={`${railH} mb-0`}><FileText className="mr-1 inline h-3 w-3" aria-hidden="true" />tl;dr</p>
        {!open && <button type="button" onClick={() => setOpen(true)} className="text-[11px] text-indigo-500 hover:underline dark:text-indigo-300" data-testid="tldr-open">Summarise{r.text_status === "indexed" ? " the PDF" : r.abstract ? " the abstract" : ""}</button>}
      </div>
      {open && tldr.isLoading && <p className="mt-1 text-xs text-stone-400">Reading…</p>}
      {open && tldr.data && tldr.data.sections.length === 0 && (
        <p className="mt-1 text-xs text-stone-400">{tldr.data.reason ?? "Nothing to summarise."}{r.pdf && r.text_status !== "indexed" && <> <button type="button" onClick={onIndexText} className="text-indigo-500 hover:underline dark:text-indigo-300">Index the PDF text</button> first.</>}</p>
      )}
      {open && tldr.data && tldr.data.sections.length > 0 && (
        <ol className="mt-1.5 space-y-2">
          {tldr.data.sections.map((s, i) => (
            <li key={i} className="text-xs leading-relaxed text-stone-600 dark:text-stone-300" data-testid="tldr-section">
              <span className="font-medium text-stone-800 dark:text-stone-100">{s.title}</span>
              {s.page && r.pdf && <button type="button" onClick={() => onJump(s.page as number)} className="ml-1.5 rounded-full bg-stone-100 px-1.5 py-0.5 text-[10px] text-stone-500 hover:text-indigo-600 dark:bg-stone-800 dark:text-stone-300" title="Open the PDF at this section">p.{s.page}</button>}
              <span className="ml-1 text-stone-400">·</span> {s.sentences.join(" ")}
            </li>
          ))}
          <li className="text-[10px] uppercase tracking-wide text-stone-400">{tldr.data.source === "pdf-text" ? "from the PDF text · extractive, local" : "from the abstract"}</li>
        </ol>
      )}
    </div>
  );
}

/** #530: how many new papers cite this one (the watch's stored feed), with a way into it. */
function CitingLine({ r, onShow }: { r: Ref; onShow: () => void }) {
  const feed = useQuery({ queryKey: ["new-citations-of", r.id], queryFn: () => api<CitingFeed>(`/references/new-citations/?reference=${r.id}&limit=1`), staleTime: 60_000 });
  const n = feed.data?.count ?? 0;
  if (!feed.data) return null;
  return (
    <p className="mt-2 flex items-center gap-1.5 text-[11px] text-stone-400" data-testid="citing-line">
      <Radar className={`h-3 w-3 ${n ? "text-sky-500" : ""}`} aria-hidden="true" />
      {n ? <button type="button" onClick={onShow} className="text-sky-700 hover:underline dark:text-sky-200">{n} new paper{n === 1 ? "" : "s"} cite{n === 1 ? "s" : ""} this — see them</button> : r.cited_by_checked_at ? `No new citing paper · checked ${new Date(r.cited_by_checked_at).toLocaleDateString()}` : "New citations not checked yet"}
    </p>
  );
}

function HighlightsBlock({ r, highlights, onJump, onEdit, onRemove, onCopied }: { r: Ref; highlights: Highlight[]; onJump: (page: number) => void; onEdit: (id: number, patch: { comment?: string; color?: string }) => void; onRemove: (id: number) => void; onCopied: (msg: string) => void }) {
  const [editing, setEditing] = useState<number | null>(null);
  const [draft, setDraft] = useState("");
  const copyAll = async () => {
    const out = await api<{ markdown: string }>(`/references/${r.id}/highlights-markdown/`);
    await navigator.clipboard?.writeText(out.markdown);
    onCopied("Copied the highlights as Markdown.");
  };
  return (
    <div className="mt-5" data-testid="highlights-block">
      <div className="mb-1.5 flex items-center justify-between">
        <p className={`${railH} mb-0`}><Highlighter className="mr-1 inline h-3 w-3" aria-hidden="true" />Highlights <span className="ml-1 normal-case tracking-normal text-stone-400">{highlights.length || ""}</span></p>
        {highlights.length > 0 && <button type="button" onClick={() => void copyAll()} className="text-[11px] text-stone-400 hover:text-indigo-600 dark:hover:text-indigo-300">copy as Markdown</button>}
      </div>
      {highlights.length === 0 ? (
        <p className="text-xs text-stone-400">{r.pdf ? "Select text while reading to highlight it. Highlights stay with the paper, and with a project's notes if you file them there." : "Attach or find a PDF, then highlight while reading."}</p>
      ) : (
        <ul className="space-y-1.5">
          {highlights.map((h) => (
            <li key={h.id} className="group rounded-lg border border-stone-200 p-2 text-xs dark:border-stone-800" style={{ borderLeft: `3px solid ${HL_COLORS[h.color] ?? HL_COLORS.yellow}` }}>
              <p className="line-clamp-3 leading-relaxed text-stone-700 dark:text-stone-200">{h.text}</p>
              {editing === h.id ? (
                <form className="mt-1.5" onSubmit={(e) => { e.preventDefault(); onEdit(h.id, { comment: draft }); setEditing(null); }}>
                  <input autoFocus value={draft} onChange={(e) => setDraft(e.target.value)} placeholder="Why does this matter?" className="w-full rounded-md border border-stone-300 bg-white px-2 py-1 text-xs dark:border-stone-700 dark:bg-stone-800" onKeyDown={(e) => { if (e.key === "Escape") setEditing(null); }} />
                </form>
              ) : h.comment ? (
                <p className="mt-1 text-[11px] italic text-stone-500 dark:text-stone-400" onClick={() => { setEditing(h.id); setDraft(h.comment); }}>{h.comment}</p>
              ) : null}
              <div className="mt-1 flex items-center gap-2 text-[10px] text-stone-400">
                {h.page ? <button type="button" onClick={() => onJump(h.page as number)} className="hover:text-indigo-600 hover:underline dark:hover:text-indigo-300">p.{h.page}</button> : <span>no page</span>}
                {h.project_name && <span className="truncate">→ {h.project_name}</span>}
                <span className="ml-auto flex items-center gap-1.5 opacity-0 transition-opacity group-hover:opacity-100">
                  {(Object.keys(HL_COLORS) as Highlight["color"][]).filter((c) => c !== h.color).map((c) => <button key={c} type="button" onClick={() => onEdit(h.id, { color: c })} className="h-2.5 w-2.5 rounded-full hover:scale-125" style={{ background: HL_COLORS[c] }} aria-label={`Recolour ${c}`} />)}
                  <button type="button" onClick={async () => { await navigator.clipboard?.writeText(`\u201c${h.text.trim()}\u201d \\cite{${r.bibtex_key}}${h.page ? ` (p.\u00a0${h.page})` : ""}`); onCopied("Copied as a LaTeX quote with \\cite{}."); }} className="hover:text-indigo-600 dark:hover:text-indigo-300" title="Copy as a quotation with \\cite{}">quote</button>
                  {!h.comment && editing !== h.id && <button type="button" onClick={() => { setEditing(h.id); setDraft(""); }} className="hover:text-indigo-600 dark:hover:text-indigo-300">comment</button>}
                  <button type="button" onClick={() => onRemove(h.id)} className="hover:text-red-500" aria-label="Delete highlight"><Trash2 className="h-3 w-3" aria-hidden="true" /></button>
                </span>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

function ReadingNotesBlock({ notes, onSave }: { notes: ReadingNote[]; onSave: (id: number, notes: string) => void }) {
  const [drafts, setDrafts] = useState<Record<number, string>>({});
  const [dirty, setDirty] = useState<Set<number>>(new Set());
  const timers = useRef<Record<number, number>>({});
  useEffect(() => { setDrafts({}); setDirty(new Set()); }, [notes.map((n) => n.project_reference_id).join(",")]); // eslint-disable-line react-hooks/exhaustive-deps
  const change = (id: number, value: string) => {
    setDrafts((d) => ({ ...d, [id]: value }));
    setDirty((s) => new Set(s).add(id));
    window.clearTimeout(timers.current[id]);
    timers.current[id] = window.setTimeout(() => { onSave(id, value); setDirty((s) => { const n = new Set(s); n.delete(id); return n; }); }, 900);
  };
  return (
    <div className="mt-5" data-testid="reading-notes-block">
      <p className={railH}><NotebookPen className="mr-1 inline h-3 w-3" aria-hidden="true" />Reading notes</p>
      {notes.length === 0 ? (
        <p className="text-xs text-stone-400">File this paper into a project to keep reading notes for it there.</p>
      ) : notes.map((n) => (
        <div key={n.project_reference_id} className="mb-2">
          <div className="mb-0.5 flex items-center justify-between text-[10px] text-stone-400"><span>{n.project_name}</span><span>{dirty.has(n.project_reference_id) ? "saving…" : STATUS_LABEL[n.reading_status] ?? n.reading_status}</span></div>
          <textarea value={drafts[n.project_reference_id] ?? n.notes} onChange={(e) => change(n.project_reference_id, e.target.value)} rows={3} placeholder="What did you take from it? Autosaves." className="w-full resize-y rounded-lg border border-stone-200 bg-stone-50 px-2 py-1.5 text-xs leading-relaxed placeholder:text-stone-400 focus:border-indigo-400 focus:outline-none dark:border-stone-800 dark:bg-stone-950/40 dark:text-stone-200" aria-label={`Reading notes for ${n.project_name}`} />
        </div>
      ))}
    </div>
  );
}

function FoundInPdf({ r, q, onFind, onIndexText }: { r: Ref; q: string; onFind: (page: number, term: string) => void; onIndexText: () => void }) {
  const active = Boolean(r.pdf && q.trim().length >= 2);
  const hits = useQuery({ queryKey: ["pdf-find", r.id, q], queryFn: () => api<{ page: number; snippet: string }[]>(`/references/${r.id}/text-search/?q=${encodeURIComponent(q)}`), enabled: active, staleTime: 60_000 });
  if (r.pdf && r.text_status !== "indexed") {
    return (
      <div className="mt-4 flex items-center justify-between gap-2 rounded-lg border border-dashed border-stone-300 px-2.5 py-1.5 text-[11px] text-stone-500 dark:border-stone-700" data-testid="text-status">
        <span>{r.text_status === "pending" ? "PDF text not read yet — it becomes searchable once indexed." : `PDF text: ${r.text_status.replace("error: ", "")}`}</span>
        <button type="button" onClick={onIndexText} className="shrink-0 rounded-md border border-stone-300 px-2 py-0.5 hover:border-indigo-300 dark:border-stone-700">{r.text_status === "pending" ? "Index now" : "Retry"}</button>
      </div>
    );
  }
  if (!active || !hits.data?.length) return null;
  return (
    <div className="mt-4" data-testid="found-in-pdf">
      <p className={railH}><Search className="mr-1 inline h-3 w-3" aria-hidden="true" />Found in the PDF · “{q}”</p>
      <ul className="space-y-1">
        {hits.data.map((h) => (
          <li key={h.page}>
            <button type="button" onClick={() => onFind(h.page, q)} className="w-full rounded-lg border border-violet-500/20 bg-violet-500/5 px-2.5 py-1.5 text-left text-[11px] leading-relaxed text-stone-600 hover:border-violet-400 dark:text-stone-300" title="Open the reader at this page">
              <span className="mr-1.5 font-medium text-violet-700 dark:text-violet-200">p.{h.page}</span>{h.snippet}
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}


/** Watched folder (#406): drop PDFs into one folder on disk and they land in the library. */
function WatchFolderBlock({ projects, onImported, flash }: { projects: { slug: string; name: string }[]; onImported: () => void; flash: (msg: string) => void }) {
  const queryClient = useQueryClient();
  type Scan = { at: string; imported: number; existing: number; failed: number; seen: number; error?: string };
  type Status = { dir: string; project: string | null; enabled: boolean; running: boolean; last_scan: string | null; last_result: Scan | null; last_import: Scan | null; interval: number };
  const status = useQuery({ queryKey: ["watch-folder"], queryFn: () => api<Status>("/watch-folder/"), refetchInterval: (q) => (q.state.data?.enabled ? 20_000 : false) });
  const [open, setOpen] = useState(false);
  const [dir, setDir] = useState("");
  const [project, setProject] = useState("");
  const save = useMutation({
    mutationFn: (body: { dir: string; project: string | null; enabled: boolean }) => api<Status>("/watch-folder/", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }),
    onSuccess: (st) => { queryClient.setQueryData(["watch-folder"], st); setOpen(false); flash(st.enabled ? `Watching ${st.dir}` : "Stopped watching"); },
    onError: (e) => void errorDialog("Couldn't set the watched folder", e),
  });
  const scan = useMutation({
    mutationFn: () => api<{ imported: number; existing: number; failed: number; seen: number; error?: string }>("/watch-folder/scan/", { method: "POST" }),
    onSuccess: (r) => { queryClient.invalidateQueries({ queryKey: ["watch-folder"] }); if (r.imported) onImported(); flash(r.error ?? `Scanned: ${r.imported} new · ${r.existing} known · ${r.failed} failed`); },
    onError: (e) => void errorDialog("Scan failed", e),
  });
  const st = status.data;
  const begin = () => { setDir(st?.dir ?? ""); setProject(st?.project ?? ""); setOpen(true); };
  const choose = async () => { const picked = await pickFolder(); if (picked) setDir(picked); };
  return (
    <div className="mb-3" data-testid="watch-folder">
      <div className="mb-1 flex items-center justify-between">
        <p className={`${railH} mb-0`}>Watch folder</p>
        {st?.enabled && <button type="button" onClick={() => scan.mutate()} disabled={scan.isPending} className="text-[10px] text-indigo-500 hover:underline disabled:opacity-50" title="Import the folder's new PDFs now">scan now</button>}
      </div>
      {!open && (
        st?.enabled ? (
          <button type="button" onClick={begin} className="w-full rounded-md px-2 py-1 text-left text-[11px] text-stone-600 hover:bg-stone-100 dark:text-stone-300 dark:hover:bg-stone-800" title={st.dir}>
            <span className="block truncate font-mono">{st.dir.split(/[\\/]/).filter(Boolean).slice(-2).join("/")}</span>
            <span className="text-stone-400">{st.running ? "watching" : "paused"}{st.project ? ` · → ${st.project}` : ""}{st.last_import ? ` · ${st.last_import.imported} new at ${st.last_import.at.slice(11, 16)}` : st.last_result?.error ? ` · ${st.last_result.error}` : ""}</span>
          </button>
        ) : (
          <button type="button" onClick={begin} className="px-2 text-[11px] text-stone-400 hover:text-indigo-600 dark:hover:text-indigo-300">Pick a folder — every PDF dropped there is imported.</button>
        )
      )}
      {open && (
        <form className="space-y-1.5 px-1" onSubmit={(e) => { e.preventDefault(); save.mutate({ dir, project: project || null, enabled: Boolean(dir.trim()) }); }}>
          <div className="flex gap-1">
            <input value={dir} onChange={(e) => setDir(e.target.value)} placeholder={isDesktop() ? "Choose a folder…" : "/path/to/folder"} className="min-w-0 flex-1 rounded-md border border-stone-300 bg-white px-1.5 py-1 font-mono text-[11px] dark:border-stone-700 dark:bg-stone-800" data-testid="watch-dir" />
            {isDesktop() && <button type="button" onClick={() => void choose()} className="rounded-md border border-stone-300 px-1.5 text-[11px] dark:border-stone-700">…</button>}
          </div>
          <select value={project} onChange={(e) => setProject(e.target.value)} className="w-full rounded-md border border-stone-300 bg-white px-1.5 py-1 text-[11px] dark:border-stone-700 dark:bg-stone-800" aria-label="File into project">
            <option value="">library only</option>
            {projects.map((p) => <option key={p.slug} value={p.slug}>→ {p.name}</option>)}
          </select>
          <div className="flex items-center gap-2">
            <button type="submit" disabled={save.isPending} className="rounded-md bg-indigo-600 px-2 py-1 text-[11px] text-white disabled:opacity-50">Watch</button>
            {st?.enabled && <button type="button" onClick={() => save.mutate({ dir: "", project: null, enabled: false })} className="text-[11px] text-stone-400 hover:text-red-500">stop</button>}
            <button type="button" onClick={() => setOpen(false)} className="ml-auto text-[11px] text-stone-400 hover:underline">cancel</button>
          </div>
        </form>
      )}
    </div>
  );
}
