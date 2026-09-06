/** Library v2 — the workbench (Observatory). Facets | list | detail, drop-anything import,
 *  keyboard navigation, bulk actions, metadata recovery. Everything here is also in the API
 *  (/references/, /facets/, /bulk/, /import/, /import-zotero/, /find-metadata/) and MCP. */
import { useInfiniteQuery, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  BookOpen, Check, ChevronDown, Download, FileText, FolderPlus, Loader2, Search, Sparkles, Trash2, Upload, Wand2, X,
} from "lucide-react";
import { api, csrfToken, petReact } from "../api";
import { Skeleton } from "../../components/Skeleton";
import { ErrorState } from "../../components/ErrorState";

type Author = { family?: string; given?: string };
type ProjLink = { slug: string; name: string; color: string; reading_status: string; priority: string };
type Ref = {
  id: number; bibtex_key: string; title: string; authors: Author[]; year: number | null; venue: string;
  abstract: string; doi: string | null; arxiv_id: string; url: string; pdf: string | null;
  entry_type: string; citation_count: number | null; extra: Record<string, unknown>; projects: ProjLink[];
  created_at: string;
};
type Page<T> = { count: number; next: string | null; results: T[] };
type Facets = {
  total: number; with_pdf: number; without_pdf: number; needs_metadata: number; unfiled: number;
  years: { year: number; count: number }[]; entry_types: { entry_type: string; count: number }[];
  venues: { venue: string; count: number }[]; projects: { slug: string; name: string; count: number }[];
  all_projects: { slug: string; name: string; color: string }[];
};
type ImportResult = { title: string; reference_id: number | null; created: boolean; source: string; error: string; needs_metadata: boolean };
type ImportSummary = { created: number; existing: number; failed: number; results: ImportResult[] };
type Filters = {
  q: string; year: string; entry_type: string; venue: string; has_pdf: string; needs_metadata: string;
  project: string; unfiled: string; reading_status: string; sort: string;
};

const EMPTY: Filters = { q: "", year: "", entry_type: "", venue: "", has_pdf: "", needs_metadata: "", project: "", unfiled: "", reading_status: "", sort: "added" };
const STATUS_LABEL: Record<string, string> = { to_read: "To read", skimmed: "Skimmed", read: "Read", annotated: "Annotated" };
const panel = "rounded-2xl border border-stone-200 bg-white dark:border-stone-800 dark:bg-stone-900";
const railH = "mb-1.5 text-[10px] font-semibold uppercase tracking-[0.14em] text-stone-400 dark:text-stone-500";
const chip = (on: boolean) =>
  `flex w-full items-center justify-between rounded-md px-2 py-1 text-left text-xs transition-colors ${
    on ? "bg-indigo-50 text-indigo-700 dark:bg-indigo-500/20 dark:text-indigo-200" : "text-stone-600 hover:bg-stone-100 dark:text-stone-300 dark:hover:bg-stone-800"
  }`;

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

async function postForm<T>(path: string, form: FormData): Promise<T> {
  const response = await fetch(`/api/v1${path}`, { method: "POST", body: form, headers: { "X-CSRFToken": csrfToken(), Accept: "application/json" }, credentials: "same-origin" });
  if (!response.ok) throw new Error(`${response.status} on ${path}`);
  return response.json();
}

export default function Library() {
  const queryClient = useQueryClient();
  const [filters, setFilters] = useState<Filters>(EMPTY);
  const [qInput, setQInput] = useState("");
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
  const [doiError, setDoiError] = useState("");
  const [bulkProject, setBulkProject] = useState("");
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
  const findMeta = useMutation({
    mutationFn: (id: number) => api<Ref>(`/references/${id}/find-metadata/`, { method: "POST" }),
    onSuccess: () => { invalidate(); flash("Metadata found and applied."); },
    onError: () => flash("No confident metadata match — try adding the DOI by hand."),
  });

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

  // keyboard: j/k move · enter open · x select · o pdf · esc clear
  const toggleSelect = useCallback((id: number) => setSelected((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; }), []);
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const tag = (e.target as HTMLElement).tagName;
      if (["INPUT", "TEXTAREA", "SELECT"].includes(tag) || e.metaKey || e.ctrlKey || e.altKey) return;
      if (!rows.length) return;
      if (e.key === "j" || e.key === "ArrowDown") { e.preventDefault(); setCursor((c) => Math.min(rows.length - 1, c + 1)); }
      else if (e.key === "k" || e.key === "ArrowUp") { e.preventDefault(); setCursor((c) => Math.max(0, c - 1)); }
      else if (e.key === "Enter") { setDetailId(rows[cursor]?.id ?? null); }
      else if (e.key === "x") { const id = rows[cursor]?.id; if (id) toggleSelect(id); }
      else if (e.key === "o") { const r = rows[cursor]; if (r?.pdf) window.open(`/library/${r.id}/read/`, "_blank"); }
      else if (e.key === "Escape") { setSelected(new Set()); setDetailId(null); }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [rows, cursor, toggleSelect]);
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
              <input value={doi} onChange={(e) => setDoi(e.target.value)} placeholder="Add by DOI or arXiv…" className="w-56 rounded-lg border border-stone-300 bg-white px-3 py-1.5 text-sm placeholder:text-stone-400 focus:border-indigo-500 focus:outline-none dark:border-stone-700 dark:bg-stone-800" />
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
      <div className="grid gap-4 lg:grid-cols-[13.5rem_minmax(0,1fr)_22rem]">
        {/* rail */}
        <aside className={`${panel} rise h-fit p-3 lg:sticky lg:top-6`}>
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
            </>
          )}
        </aside>

        {/* list */}
        <section className={`${panel} rise flex min-h-[60vh] flex-col overflow-hidden`} style={{ ["--i" as string]: 1 }}>
          <div className="flex flex-wrap items-center gap-2 border-b border-stone-100 px-3 py-2 text-xs dark:border-stone-800">
            <label className="flex items-center gap-1.5 text-stone-500"><input type="checkbox" checked={allSelectedOnPage} onChange={() => setSelected(allSelectedOnPage ? new Set() : new Set(rows.map((r) => r.id)))} className="accent-indigo-500" />{total} result{total === 1 ? "" : "s"}</label>
            {activeChips.map((k) => (
              <button key={k} type="button" onClick={() => set({ [k]: "" } as Partial<Filters>)} className="inline-flex items-center gap-1 rounded-full bg-indigo-500/10 px-2 py-0.5 text-indigo-700 dark:text-indigo-200">{k.replace("_", " ")}: {k === "reading_status" ? STATUS_LABEL[filters[k]] : filters[k]}<X className="h-3 w-3" aria-hidden="true" /></button>
            ))}
            {activeChips.length > 0 && <button type="button" onClick={() => setFilters({ ...EMPTY, sort: filters.sort })} className="text-stone-400 hover:underline">clear</button>}
            <span className="ml-auto hidden text-stone-400 lg:inline">j/k move · enter open · x select · o pdf</span>
          </div>
          <div ref={listRef} className="flex-1 divide-y divide-stone-100 overflow-auto dark:divide-stone-800">
            {list.isLoading && Array.from({ length: 8 }).map((_, i) => <div key={i} className="px-4 py-3"><Skeleton className="mb-1.5 h-4 w-2/3" /><Skeleton className="h-3 w-1/3" /></div>)}
            {rows.map((r, i) => {
              const needs = Boolean(r.extra?.needs_metadata);
              const active = i === cursor;
              return (
                <div key={r.id} data-row={i} onClick={() => { setCursor(i); setDetailId(r.id); }} className={`group flex cursor-pointer items-start gap-3 px-3 py-2.5 transition-colors ${detailId === r.id ? "bg-indigo-50 dark:bg-indigo-500/10" : active ? "bg-stone-50 dark:bg-stone-800/60" : "hover:bg-stone-50 dark:hover:bg-stone-800/40"}`}>
                  <input type="checkbox" checked={selected.has(r.id)} onClick={(e) => e.stopPropagation()} onChange={() => toggleSelect(r.id)} className="mt-1 accent-indigo-500" aria-label={`Select ${r.title}`} />
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium text-stone-900 dark:text-stone-100">{r.title}</p>
                    <p className="mt-0.5 flex items-center gap-1.5 truncate text-xs text-stone-400 dark:text-stone-400">
                      <span className="truncate">{[authorsLine(r), r.year, r.venue].filter(Boolean).join(" · ") || (needs ? "from a PDF · no metadata yet" : "no details yet")}</span>
                    </p>
                  </div>
                  <div className="flex shrink-0 items-center gap-1.5 pt-0.5">
                    {r.projects.map((p) => <span key={p.slug} title={`${p.name} · ${STATUS_LABEL[p.reading_status] ?? p.reading_status}`} className="h-2 w-2 rounded-full" style={{ background: p.color }} />)}
                    {needs && <span className="rounded-full bg-amber-500/10 px-1.5 py-0.5 text-[10px] font-medium text-amber-600 dark:text-amber-300">needs metadata</span>}
                    {r.pdf && <span className="rounded-full bg-indigo-500/10 px-1.5 py-0.5 text-[10px] font-medium text-indigo-600 dark:text-indigo-300">PDF</span>}
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
              <button type="button" disabled={bulk.isPending} onClick={() => bulk.mutate({ ids: [...selected], action: "find_metadata" })} className="inline-flex items-center gap-1 rounded-md border border-stone-300 px-2 py-1 text-stone-600 hover:border-indigo-300 dark:border-stone-700 dark:text-stone-300"><Wand2 className="h-3 w-3" aria-hidden="true" />Find metadata</button>
              <button type="button" disabled={bulk.isPending} onClick={() => { if (confirm(`Delete ${selected.size} reference(s) from the library? Their project links and PDFs go too.`)) bulk.mutate({ ids: [...selected], action: "delete" }); }} className="inline-flex items-center gap-1 rounded-md border border-red-300/60 px-2 py-1 text-red-600 hover:bg-red-500/10 dark:text-red-300"><Trash2 className="h-3 w-3" aria-hidden="true" />Delete</button>
              <button type="button" onClick={() => setSelected(new Set())} className="ml-auto text-stone-400 hover:underline">clear</button>
            </div>
          )}
        </section>

        {/* detail */}
        <aside className={`${panel} rise h-fit p-5 lg:sticky lg:top-6`} style={{ ["--i" as string]: 2 }}>
          {!detail ? (
            <div className="py-10 text-center text-sm text-stone-400">
              <Sparkles className="mx-auto mb-2 h-6 w-6 text-indigo-300" aria-hidden="true" />
              Select a paper to see its abstract, links, and related work.
            </div>
          ) : (
            <DetailPane r={detail} onFindMeta={() => findMeta.mutate(detail.id)} finding={findMeta.isPending} projects={f?.all_projects ?? []} onLink={(slug) => bulk.mutate({ ids: [detail.id], action: "link", project: slug })} />
          )}
        </aside>
      </div>
      {toast && <div className="glow-accent fixed bottom-5 right-5 z-50 rounded-xl bg-stone-900 px-4 py-2.5 text-sm text-stone-100 dark:bg-stone-800">{toast}</div>}
    </div>
  );
}

function DetailPane({ r, onFindMeta, finding, projects, onLink }: { r: Ref; onFindMeta: () => void; finding: boolean; projects: { slug: string; name: string; color: string }[]; onLink: (slug: string) => void }) {
  const [full, setFull] = useState(false);
  const related = useQuery({ queryKey: ["related", r.id], queryFn: () => api<{ id: number; title: string; year: number | null; score: number }[]>(`/references/${r.id}/related/`), staleTime: 60_000 });
  const needs = Boolean(r.extra?.needs_metadata);
  const inProjects = new Set(r.projects.map((p) => p.slug));
  return (
    <div key={r.id} className="rise">
      <h2 className="font-display text-lg font-semibold leading-snug text-stone-900 dark:text-stone-100">{r.title}</h2>
      <p className="mt-1.5 text-sm text-stone-500 dark:text-stone-300">{(r.authors ?? []).map((a) => [a.given, a.family].filter(Boolean).join(" ")).filter(Boolean).join(", ") || "Unknown authors"}</p>
      <p className="mt-1 text-xs text-stone-400">{[r.year, r.venue, r.entry_type].filter(Boolean).join(" · ")}{r.citation_count != null ? ` · ${r.citation_count} citations` : ""}</p>
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
        {r.pdf && <a href={`/library/${r.id}/read/`} target="_blank" rel="noreferrer" className="rounded-md border border-stone-300 px-2.5 py-1 text-stone-600 hover:border-indigo-300 dark:border-stone-700 dark:text-stone-300">Read PDF</a>}
        {r.doi && <a href={`https://doi.org/${r.doi}`} target="_blank" rel="noreferrer" className="rounded-md border border-stone-300 px-2.5 py-1 text-stone-600 hover:border-indigo-300 dark:border-stone-700 dark:text-stone-300">DOI</a>}
        {r.url && !r.doi && <a href={r.url} target="_blank" rel="noreferrer" className="rounded-md border border-stone-300 px-2.5 py-1 text-stone-600 hover:border-indigo-300 dark:border-stone-700 dark:text-stone-300">Link</a>}
        <button type="button" onClick={() => navigator.clipboard?.writeText(r.bibtex_key)} title="Copy cite key" className="rounded-md border border-stone-300 px-2.5 py-1 font-mono text-stone-500 hover:border-indigo-300 dark:border-stone-700 dark:text-stone-300">{r.bibtex_key}</button>
      </div>
      <div className="mt-5">
        <p className={railH}>In projects</p>
        {r.projects.length === 0 && <p className="text-xs text-stone-400">Not filed in any project yet.</p>}
        <ul className="space-y-1 text-sm">
          {r.projects.map((p) => (
            <li key={p.slug} className="flex items-center gap-2"><span className="h-2 w-2 rounded-full" style={{ background: p.color }} /><Link to={`/projects/${p.slug}/literature`} className="min-w-0 flex-1 truncate hover:underline dark:text-stone-100">{p.name}</Link><span className="text-xs text-stone-400">{STATUS_LABEL[p.reading_status] ?? p.reading_status}</span></li>
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
