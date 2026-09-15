/** Library v2 — the workbench (Observatory). Facets | list | detail, drop-anything import,
 *  keyboard navigation, bulk actions, metadata recovery. Everything here is also in the API
 *  (/references/, /facets/, /bulk/, /import/, /import-zotero/, /find-metadata/) and MCP. */
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import {
  Bookmark, BookOpen, Check, ChevronDown, Copy, CopyCheck, Download, Highlighter, LayoutGrid, LayoutList, Link2, Pencil, ShieldAlert, ShieldCheck, ArrowUpCircle, Quote, Tag as TagIcon, ExternalLink, FileDown, FileText, FolderPlus, Loader2, NotebookPen, Plus, Search, Sparkles, Telescope, Trash2, Upload, Wand2, X,
} from "lucide-react";
import { api, csrfToken, petReact } from "../api";
import { confirmDialog, errorDialog, promptDialog } from "../../components/Dialog";
import { useMenu, type MenuItem } from "../../components/Menu";
import { isDesktop, pickFolder } from "../external";
import PdfReader, { HL_COLORS, type Highlight } from "./library/PdfReader";
import { Skeleton } from "../../components/Skeleton";
import { ErrorState } from "../../components/ErrorState";

type Author = { family?: string; given?: string };
type ProjLink = { slug: string; name: string; color: string; reading_status: string; priority: string; started_at?: string | null; finished_at?: string | null };
type Progress = { page: number | null; pages: number | null; percent: number | null; last_read_at: string | null };
type ReadingNowRow = { id: number; title: string; bibtex_key: string; year: number | null; pdf: string | null; page: number; pages: number | null; percent: number | null; last_read_at: string };
const inProgress = (p?: Progress | null) => Boolean(p && p.page != null && p.page > 1 && (p.percent ?? 0) < 100);
const pageLabel = (p: { page: number | null; pages: number | null }) => `p. ${p.page}${p.pages ? ` of ${p.pages}` : ""}`;
const dayLabel = (iso: string) => new Date(iso).toLocaleDateString(undefined, { month: "short", day: "numeric" });
type Ref = {
  id: number; bibtex_key: string; title: string; authors: Author[]; year: number | null; venue: string;
  abstract: string; doi: string | null; arxiv_id: string; url: string; pdf: string | null;
  entry_type: string; citation_count: number | null; extra: Record<string, unknown>; projects: ProjLink[];
  tags: string[];
  pdf_match: boolean | null; text_status: string;
  progress: Progress;
  retraction_kind: string; retraction_notice: string; retraction_date: string | null; retraction_checked_at: string | null;
  preprint: boolean; published_doi: string; published_venue: string; published_checked_at: string | null;
  created_at: string;
};
type ReadingNote = { project_reference_id: number; project: string; project_name: string; reading_status: string; notes: string };
type SavedView = { id: number; name: string; params: Partial<Filters>; position: number };
type Page<T> = { count: number; next: string | null; results: T[] };
type Facets = {
  total: number; with_pdf: number; without_pdf: number; needs_metadata: number; retracted: number; preprints: number; published_available: number; unfiled: number;
  years: { year: number; count: number }[]; entry_types: { entry_type: string; count: number }[];
  venues: { venue: string; count: number }[]; authors: { name: string; given: string; count: number }[]; projects: { slug: string; name: string; count: number }[];
  all_projects: { slug: string; name: string; color: string }[];
  untagged: number; tags: { id: number; name: string; color: string; count: number }[]; views: SavedView[];
  duplicates: number;
};
type DupMember = { id: number; title: string; year: number | null; doi: string | null; venue: string; bibtex_key: string; has_pdf: boolean; projects: string[]; tags: string[]; score: number };
type DupGroup = { keep: number; reasons: string[]; members: DupMember[] };
type DiscoverRow = {
  openalex_id: string; doi: string; title: string; year: number | null; venue: string; authors: string[];
  more_authors: number; citations: number | null; in_library: boolean; library_id: number | null; addable: boolean;
};
type ImportResult = { title: string; reference_id: number | null; created: boolean; source: string; error: string; needs_metadata: boolean };
type ImportSummary = { created: number; existing: number; failed: number; results: ImportResult[] };
type Filters = {
  q: string; year: string; year_min: string; year_max: string; entry_type: string; venue: string; author: string; has_pdf: string; needs_metadata: string; retracted: string; preprints: string; published_available: string;
  project: string; unfiled: string; reading_status: string; tag: string; untagged: string; sort: string;
};

const EMPTY: Filters = { q: "", year: "", year_min: "", year_max: "", entry_type: "", venue: "", author: "", has_pdf: "", needs_metadata: "", retracted: "", preprints: "", published_available: "", project: "", unfiled: "", reading_status: "", tag: "", untagged: "", sort: "added" };
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
  const [dupMode, setDupMode] = useState(false);
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
    mutationFn: (id: number) => api<{ outcome: string; attached: boolean; pdf: string | null }>(`/references/${id}/fetch-pdf/`, { method: "POST" }),
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
    if (lastWritten.current === null) { lastWritten.current = viewQuery(fromUrl(location.search)); return; } // the mount: state came from this address
    if (current === lastWritten.current) return;
    const next = fromUrl(location.search);
    lastWritten.current = viewQuery(next);
    try {
      const p = new URLSearchParams(location.search);
      const r = p.get("read"); if (r) readParam.current = Number(r);
      if (p.get("add") !== null) doiRef.current?.focus();
    } catch { /* no URL access */ }
    setFilters(next); setQInput(next.q);
  }, [location.search]); // eslint-disable-line react-hooks/exhaustive-deps
  useEffect(() => {
    if (qInput !== q) return; // let the debounce settle so a keystroke is not a route change
    const qs = viewQuery(effective);
    if (qs === lastWritten.current) return;
    lastWritten.current = qs;
    navigate(qs ? `/library?${qs}` : "/library", { replace: true });
  }, [effective, qInput, q]); // eslint-disable-line react-hooks/exhaustive-deps
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
  const checkRetractions = useMutation({
    mutationFn: (ids: number[] | null) => api<{ checked: number; retracted: { bibtex_key: string }[]; errors: number; skipped: number }>("/references/check-retractions/", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(ids ? { ids } : { stale: true, limit: 50 }) }),
    onSuccess: (out, ids) => {
      invalidate(); queryClient.invalidateQueries({ queryKey: ["library-facets"] });
      if (!ids && out.checked === 0 && out.errors === 0) { flash("Every paper with a DOI was checked in the last 30 days."); return; }
      flash(`Checked ${out.checked} paper${out.checked === 1 ? "" : "s"} · ${out.retracted.length} retracted${out.errors ? ` · ${out.errors} could not be checked` : ""}${out.skipped ? ` · ${out.skipped} without a DOI` : ""}.`);
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
                <button type="button" data-testid="check-retractions" disabled={checkRetractions.isPending} onClick={() => checkRetractions.mutate(null)} className="mt-0.5 flex w-full items-center gap-1.5 rounded-md px-2 py-1 text-left text-[11px] text-stone-400 hover:bg-stone-100 hover:text-stone-600 disabled:opacity-60 dark:hover:bg-stone-800 dark:hover:text-stone-200" title="Ask Crossref about the papers not checked in the last 30 days (up to 50 now; the rest run nightly)">{checkRetractions.isPending ? <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" /> : <ShieldCheck className="h-3 w-3" aria-hidden="true" />}{checkRetractions.isPending ? "Asking Crossref…" : "Check retractions now"}</button>
                <button type="button" data-testid="rail-preprints" className={chip(filters.preprints === "true")} onClick={() => toggle("preprints", "true")} title="arXiv papers without a publisher DOI of their own"><span className="flex items-center gap-1.5"><FileText className="h-3 w-3" aria-hidden="true" />Preprints</span><span className="tabular-nums text-stone-400">{f.preprints}</span></button>
                <button type="button" data-testid="rail-published" className={chip(filters.published_available === "true")} onClick={() => toggle("published_available", "true")} title="Preprints whose published version the preprint watch found — upgrade them from the detail pane"><span className="flex items-center gap-1.5"><ArrowUpCircle className={`h-3 w-3 ${f.published_available ? "text-amber-500" : ""}`} aria-hidden="true" />Published version</span><span className={`tabular-nums ${f.published_available ? "font-semibold text-amber-500" : "text-stone-400"}`}>{f.published_available}</span></button>
                <button type="button" data-testid="check-preprints" disabled={checkPreprints.isPending} onClick={() => checkPreprints.mutate(null)} className="mt-0.5 flex w-full items-center gap-1.5 rounded-md px-2 py-1 text-left text-[11px] text-stone-400 hover:bg-stone-100 hover:text-stone-600 disabled:opacity-60 dark:hover:bg-stone-800 dark:hover:text-stone-200" title="Ask arXiv and Semantic Scholar about the preprints not checked in the last 30 days (up to 50 now; the rest run nightly)">{checkPreprints.isPending ? <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" /> : <ArrowUpCircle className="h-3 w-3" aria-hidden="true" />}{checkPreprints.isPending ? "Asking arXiv…" : "Check preprints now"}</button>
                <button type="button" className={chip(dupMode)} onClick={() => setDupMode((v) => !v)} title="Papers that look like the same work imported twice"><span className="flex items-center gap-1.5"><CopyCheck className="h-3 w-3" aria-hidden="true" />Duplicates</span><span className={`tabular-nums ${f.duplicates ? "text-amber-500" : "text-stone-400"}`}>{f.duplicates}</span></button>
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
        ) : dupMode ? (
          <section className={`${panel} rise flex min-h-[60vh] flex-col overflow-hidden`} style={{ ["--i" as string]: 1 }}>
            <div className="flex items-center gap-2 border-b border-stone-100 px-4 py-2.5 text-xs dark:border-stone-800">
              <CopyCheck className="h-3.5 w-3.5 text-amber-500" aria-hidden="true" />
              <span className="font-medium text-stone-700 dark:text-stone-100">Duplicates</span>
              <span className="text-stone-400">same DOI or arXiv id, or near-identical titles · the most complete record is pre-selected to keep</span>
              <button type="button" onClick={() => setDupMode(false)} className="ml-auto text-stone-400 hover:underline">back to the list</button>
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
            <button type="button" data-testid="copy-link" onClick={async () => { const qs = viewQuery(effective); await navigator.clipboard?.writeText(`${window.location.origin}/library${qs ? `?${qs}` : ""}`); flash("Copied a link to this view."); }} className="inline-flex items-center gap-1 text-stone-400 hover:text-indigo-600 dark:hover:text-indigo-300" title="Copy a link to this view — paste it in a note, a message, or hand it to Claude"><Link2 className="h-3 w-3" aria-hidden="true" />Copy link</button>
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
            <DetailPane r={detail} onAuthor={(family) => toggle("author", family)} authorFilter={filters.author} onFindMeta={() => findMeta.mutate(detail.id)} finding={findMeta.isPending} onCheckRetraction={() => checkRetractions.mutate([detail.id])} checkingRetraction={checkRetractions.isPending} onCheckPreprint={() => checkPreprints.mutate([detail.id])} checkingPreprint={checkPreprints.isPending} onUpgrade={() => upgradePreprint.mutate(detail.id)} upgrading={upgradePreprint.isPending} highlights={highlights.data ?? []} readingNotes={readingNotes.data ?? []} reading={readerId === detail.id} onRead={() => openReader(detail)} onJump={(page) => { openReader(detail); setJump({ page, nonce: Date.now() }); }} onEditHighlight={(id, patch) => editHighlight.mutate({ id, ...patch })} onRemoveHighlight={(id) => removeHighlight.mutate(id)} onSaveNotes={(id, notes) => saveNotes.mutate({ id, notes })} onFetchPdf={() => fetchPdf.mutate(detail.id)} fetchingPdf={fetchPdf.isPending} q={effective.q} onFind={(page, term) => { openReader(detail, term); setJump({ page, nonce: Date.now() }); }} onIndexText={() => indexText.mutate(detail.id)} onLitNote={(project) => litNote.mutate({ reference: detail.id, project })} projects={f?.all_projects ?? []} onLink={(slug) => bulk.mutate({ ids: [detail.id], action: "link", project: slug })} citeStyle={citeStyle} onStyle={setCiteStyle} onCopied={flash} allTags={f?.tags.map((t) => t.name) ?? []} tagColors={tagColors} onTag={(tag, remove) => bulk.mutate({ ids: [detail.id], action: remove ? "untag" : "tag", value: tag })} currentProject={filters.project} onAdded={(r) => { invalidate(); petReact("paper"); flash(`Added “${r.title.slice(0, 60)}” to the library${filters.project ? " and this project" : ""}.`); }} />
          )}
        </aside>
      </div>
      {menu.element}
      {toast && <div className="glow-accent fixed bottom-5 right-5 z-50 rounded-xl bg-stone-900 px-4 py-2.5 text-sm text-stone-100 dark:bg-stone-800">{toast}</div>}
    </div>
  );
}

function DetailPane({ r, onAuthor, authorFilter, onFindMeta, finding, onCheckRetraction, checkingRetraction, onCheckPreprint, checkingPreprint, onUpgrade, upgrading, projects, onLink, currentProject, onAdded, citeStyle, onStyle, onCopied, allTags, tagColors, onTag, highlights, readingNotes, reading, onRead, onJump, onEditHighlight, onRemoveHighlight, onSaveNotes, onFetchPdf, fetchingPdf, q, onFind, onIndexText, onLitNote }: { r: Ref; onAuthor: (family: string) => void; authorFilter: string; allTags: string[]; tagColors: TagColors; onTag: (tag: string, remove: boolean) => void; onFindMeta: () => void; finding: boolean; onCheckRetraction: () => void; checkingRetraction: boolean; onCheckPreprint: () => void; checkingPreprint: boolean; onUpgrade: () => void; upgrading: boolean; highlights: Highlight[]; readingNotes: ReadingNote[]; reading: boolean; onRead: () => void; onJump: (page: number) => void; onEditHighlight: (id: number, patch: { comment?: string; color?: string }) => void; onRemoveHighlight: (id: number) => void; onSaveNotes: (id: number, notes: string) => void; onFetchPdf: () => void; fetchingPdf: boolean; q: string; onFind: (page: number, term: string) => void; onIndexText: () => void; onLitNote: (project: string) => void; projects: { slug: string; name: string; color: string }[]; onLink: (slug: string) => void; currentProject: string; onAdded: (r: Ref) => void; citeStyle: string; onStyle: (s: string) => void; onCopied: (msg: string) => void }) {
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
      {!r.retraction_kind && r.doi && (
        <p className="mt-2 flex items-center gap-1.5 text-[11px] text-stone-400" data-testid="retraction-ok"><ShieldCheck className="h-3 w-3" aria-hidden="true" />{r.retraction_checked_at ? `No retraction notice · checked ${new Date(r.retraction_checked_at).toLocaleDateString()}` : "Retraction not checked yet"} · <button type="button" onClick={onCheckRetraction} disabled={checkingRetraction} className="underline disabled:opacity-50">{checkingRetraction ? "asking…" : "check"}</button></p>
      )}
      {r.published_doi && (
        <div data-testid="published-banner" className="mt-3 rounded-xl border border-amber-400/50 bg-amber-500/10 p-3 text-xs text-amber-900 dark:text-amber-100">
          <p className="flex items-center gap-1.5 font-semibold"><ArrowUpCircle className="h-3.5 w-3.5" aria-hidden="true" />A published version exists{r.published_venue ? ` · ${r.published_venue}` : ""}</p>
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
          <button type="button" onClick={onFetchPdf} disabled={fetchingPdf || !(r.doi || r.arxiv_id)} className="inline-flex items-center gap-1 rounded-md border border-stone-300 px-2.5 py-1 text-stone-600 hover:border-indigo-300 disabled:opacity-50 dark:border-stone-700 dark:text-stone-300" title={r.doi || r.arxiv_id ? "Look for an open-access PDF (arXiv, Unpaywall)" : "Needs a DOI or arXiv id to look up a PDF"}>{fetchingPdf ? <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" /> : <Download className="h-3 w-3" aria-hidden="true" />}Find PDF</button>
        )}
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
