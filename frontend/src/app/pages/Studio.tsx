/* The LaTeX studio (Owner report 2026-09-06: "the latex editor is terrible … nothing close to
 * real world standards"). A full-window, VS-Code-shaped editor that lives inside the app:
 * activity sidebar (files / outline / bibliography / history), tabbed CodeMirror 6 editor
 * (the shared `frontend/src/editor` core: LaTeX grammar, snippets, \cite completion from the
 * whole library, live cite-check), a PDF preview that re-renders after each compile, a
 * problems panel wired to the compile log, autosave with a status bar, and the shortcuts
 * people expect (⌘S save, ⌘↩ compile, ⌘B sidebar, ⌘\ preview, ⌘J problems, ⌘P quick open). */
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { EditorView, keymap } from "@codemirror/view";
import { Prec } from "@codemirror/state";
import { HighlightStyle, syntaxHighlighting } from "@codemirror/language";
import { tags as t } from "@lezer/highlight";
import {
  AlertTriangle, ArrowLeft, BookOpen, Check, ChevronLeft, ChevronRight, Download, FileText, FolderOpen, History, ListTree,
  Loader2, Minus, Package, PanelLeft, PanelRight, Play, Plus, RefreshCw, Search, Settings2, TerminalSquare, Trash2, Upload, X,
} from "lucide-react";
import { mountEditor, Split, type EditorAdapter } from "../../editor";
import { api, csrfToken } from "../api";

type MFile = { id: number; path: string; kind: string; is_main: boolean; url?: string; size?: number };
type Manuscript = { id: number; project: string; project_name: string; title: string; status: string; compile_status: string; compiled_at: string | null; files: MFile[] };
type Diag = { level: string; file: string; line: number | null; message: string };
type Compile = { status: string; diagnostics: Diag[]; compiled_at: string | null; pdf_url: string | null; log: string };
type BibRow = { link_id: number; reference_id: number; cite_key: string; bibtex_key: string; title: string; year: number | null; authors: string; venue: string };
type Candidate = { reference_id: number; key: string; title: string; authors: string; year: number | null; linked: boolean };
type Hl = { id: number; reference: number; page: number | null; text: string; comment: string; color: string };
type Revision = { id: number; label: string; labeled: boolean; created_at: string; files: string[] };
type WordCount = { words: number; headers?: number; captions?: number; math?: number };
type Settings = { keymap: "default" | "vim"; fontSize: number; spellcheck: boolean; autoCompile: boolean };
type Tab = "files" | "outline" | "bib" | "history";

const SETTINGS_KEY = "atlas-studio-settings";
const HEADING_RE = /\\(part|chapter|section|subsection|subsubsection|paragraph)\*?\{([^}]*)\}/;
const DEPTH: Record<string, number> = { part: 0, chapter: 0, section: 0, subsection: 1, subsubsection: 2, paragraph: 3 };
const PDFJS = "/static/vendor/pdfjs/pdf.min.mjs";
const PDFJS_WORKER = "/static/vendor/pdfjs/pdf.worker.min.mjs";

/** A highlighted passage as LaTeX: a quote environment with the citation and page. */
export function quoteLatex(text: string, key: string, page: number | null): string {
  return `\\begin{quote}\n  ${text.trim().replace(/\s+/g, " ")} \\citep{${key}}${page ? `, p.~${page}` : ""}\n\\end{quote}\n`;
}

function loadSettings(): Settings {
  try { return { keymap: "default", fontSize: 14, spellcheck: false, autoCompile: false, ...JSON.parse(localStorage.getItem(SETTINGS_KEY) || "{}") }; } catch { return { keymap: "default", fontSize: 14, spellcheck: false, autoCompile: false }; }
}

/** Workbench endpoints are classic JSON views: session auth + CSRF, form-encoded writes. */
async function wb<T>(url: string, form?: Record<string, string | Blob>, method = form ? "POST" : "GET"): Promise<T> {
  const body = form ? new FormData() : undefined;
  if (body && form) for (const [k, v] of Object.entries(form)) body.append(k, v);
  const res = await fetch(url, { method, body, headers: { Accept: "application/json", "X-CSRFToken": csrfToken(), "X-SPA": "1" }, credentials: "same-origin" });
  if (!res.ok) { let msg = `${res.status}`; try { msg = (await res.json()).error || msg; } catch { /* plain */ } throw new Error(msg); }
  return res.json();
}

// The editor theme reads CSS variables (assets/css/app.css `.studio`) so one theme serves
// both Observatory (dark) and Paper (light) without re-mounting.
const studioTheme = EditorView.theme({
  "&": { backgroundColor: "var(--studio-editor-bg)", color: "var(--studio-fg)", height: "100%" },
  ".cm-scroller": { fontFamily: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace", lineHeight: "1.6" },
  ".cm-content": { caretColor: "var(--studio-accent)", padding: "12px 0" },
  ".cm-cursor, .cm-dropCursor": { borderLeftColor: "var(--studio-accent)" },
  "&.cm-focused > .cm-scroller > .cm-selectionLayer .cm-selectionBackground, .cm-selectionBackground, ::selection": { backgroundColor: "var(--studio-selection) !important" },
  ".cm-activeLine": { backgroundColor: "var(--studio-active-line)" },
  ".cm-gutters": { backgroundColor: "var(--studio-editor-bg)", color: "var(--studio-gutter-fg)", borderRight: "1px solid var(--studio-line)" },
  ".cm-activeLineGutter": { backgroundColor: "var(--studio-active-line)", color: "var(--studio-fg)" },
  ".cm-tooltip": { backgroundColor: "var(--studio-panel)", border: "1px solid var(--studio-line)", color: "var(--studio-fg)" },
  ".cm-tooltip-autocomplete ul li[aria-selected]": { backgroundColor: "var(--studio-selection)", color: "var(--studio-fg)" },
  ".cm-panels": { backgroundColor: "var(--studio-panel)", color: "var(--studio-fg)", borderColor: "var(--studio-line)" },
  ".cm-searchMatch": { backgroundColor: "var(--studio-match)" },
  ".cm-lintRange-error": { backgroundImage: "none", borderBottom: "2px solid #f87171" },
  ".cm-lintRange-warning": { backgroundImage: "none", borderBottom: "2px dotted #fbbf24" },
});
const studioHighlight = syntaxHighlighting(HighlightStyle.define([
  { tag: t.keyword, color: "var(--tok-keyword)" },
  { tag: [t.controlKeyword, t.definitionKeyword, t.moduleKeyword], color: "var(--tok-keyword)", fontWeight: "600" },
  { tag: [t.name, t.function(t.name), t.macroName], color: "var(--tok-command)" },
  { tag: [t.string, t.special(t.string)], color: "var(--tok-string)" },
  { tag: t.comment, color: "var(--tok-comment)", fontStyle: "italic" },
  { tag: [t.number, t.atom, t.bool], color: "var(--tok-number)" },
  { tag: [t.bracket, t.paren, t.brace], color: "var(--tok-bracket)" },
  { tag: [t.heading, t.strong], color: "var(--tok-heading)", fontWeight: "700" },
  { tag: t.emphasis, fontStyle: "italic" },
  { tag: [t.labelName, t.propertyName, t.attributeName], color: "var(--tok-label)" },
  { tag: [t.operator, t.punctuation], color: "var(--tok-bracket)" },
  { tag: [t.literal, t.regexp, t.escape, t.special(t.name)], color: "var(--tok-math)" },
]));

const iconBtn = "inline-flex h-7 items-center gap-1.5 rounded-md px-2 text-xs st-muted transition-colors st-hover-bg st-hover-fg disabled:opacity-40";
const sideItem = "group flex w-full cursor-pointer items-center gap-1.5 rounded-md px-2 py-1 text-left text-xs transition-colors st-hover-bg";

export default function Studio() {
  const { id } = useParams();
  const mid = Number(id);
  const manuscript = useQuery({ queryKey: ["manuscript", mid], queryFn: () => api<Manuscript>(`/manuscripts/${mid}/`) });
  const m = manuscript.data;
  if (manuscript.isLoading) return <div className="studio fixed inset-0 flex items-center justify-center text-sm st-muted"><Loader2 className="mr-2 h-4 w-4 animate-spin" aria-hidden="true" />Opening the studio…</div>;
  if (!m) return <div className="studio fixed inset-0 flex flex-col items-center justify-center gap-2 text-sm st-muted"><p>This manuscript does not exist.</p><Link to="/writing" className="text-indigo-400 hover:underline">← Writing</Link></div>;
  return <StudioInner m={m} />;
}

function StudioInner({ m }: { m: Manuscript }) {
  const base = `/projects/${m.project}/writing/${m.id}/`;
  const hostRef = useRef<HTMLDivElement>(null);
  const adRef = useRef<EditorAdapter | null>(null);
  const fileInput = useRef<HTMLInputElement>(null);

  const [files, setFiles] = useState<MFile[]>(m.files);
  // the workbench list is the source of truth (it bootstraps main.tex from latex_source)
  useEffect(() => { wb<{ files: MFile[] }>(`${base}files/`).then((d) => setFiles(d.files)).catch(() => {}); }, [base]);
  const mainId = useMemo(() => files.find((f) => f.is_main)?.id ?? files[0]?.id ?? 0, [files]);
  const [activeId, setActiveId] = useState<number>(0);
  const [tabs, setTabs] = useState<number[]>([]);
  const loaded = useRef(new Set<number>());
  const dirtyRef = useRef(new Set<number>());
  const [dirty, setDirty] = useState<number[]>([]);
  const gen = useRef(new Map<number, number>());
  const timers = useRef(new Map<number, number>());
  const [saveStatus, setSaveStatus] = useState("Saved");
  const [missingCites, setMissingCites] = useState(0);
  const [ready, setReady] = useState(false);

  const [settings, setSettings] = useState<Settings>(loadSettings);
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [sidebarOpen, setSidebarOpen] = useState(true);
  const [previewOpen, setPreviewOpen] = useState(true);
  const [problemsOpen, setProblemsOpen] = useState(false);
  const [tab, setTab] = useState<Tab>("files");
  const [outline, setOutline] = useState<{ line: number; depth: number; title: string }[]>([]);
  const [ln, setLn] = useState(1);
  const [quickOpen, setQuickOpen] = useState(false);

  const [compile, setCompile] = useState<Compile>({ status: m.compile_status, diagnostics: [], compiled_at: m.compiled_at, pdf_url: null, log: "" });
  const [pdfUrl, setPdfUrl] = useState<string | null>(null);
  const pollRef = useRef<number | null>(null);
  const [words, setWords] = useState<WordCount | null>(null);
  const [flash, setFlash] = useState("");

  const pathOf = useCallback((fid: number) => files.find((f) => f.id === fid)?.path ?? "main.tex", [files]);
  const filesRef = useRef(files); filesRef.current = files;
  const activeRef = useRef(activeId); activeRef.current = activeId;
  const settingsRef = useRef(settings); settingsRef.current = settings;
  const compileRef = useRef<() => void>(() => {});
  const saveNowRef = useRef<() => void>(() => {});

  const markDirty = (fid: number, on: boolean) => { if (on) dirtyRef.current.add(fid); else dirtyRef.current.delete(fid); setDirty([...dirtyRef.current]); };

  const refreshWords = useCallback(() => { api<WordCount>(`/manuscripts/${m.id}/word-count/`).then(setWords).catch(() => {}); }, [m.id]);

  const saveFile = useCallback(async (fid: number) => {
    const ad = adRef.current; if (!ad) return;
    const content = ad.fileValue(fid);
    const g = gen.current.get(fid) || 0;
    if (fid === activeRef.current) setSaveStatus("Saving…");
    try {
      const data = await wb<{ saved: boolean; cite?: { missing_from_bib: number } }>(`${base}files/${fid}/save/`, { content });
      if ((gen.current.get(fid) || 0) === g) markDirty(fid, false);
      if (fid === activeRef.current) {
        setSaveStatus(`Saved ${new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}`);
        setMissingCites(data.cite?.missing_from_bib ?? 0);
        refreshWords();
        if (settingsRef.current.autoCompile) compileRef.current();
      }
    } catch {
      if (fid === activeRef.current) setSaveStatus("Not saved — retrying");
      window.setTimeout(() => saveFile(fid), 4000);
    }
  }, [base, refreshWords]);

  const saveAll = useCallback(async () => { await Promise.all([...dirtyRef.current].map((fid) => { window.clearTimeout(timers.current.get(fid)); return saveFile(fid); })); }, [saveFile]);
  saveNowRef.current = () => { void saveAll(); };

  const recomputeOutline = useCallback(() => {
    const ad = adRef.current; if (!ad) return;
    const rows: { line: number; depth: number; title: string }[] = [];
    for (let i = 1; i <= ad.lineCount(); i++) { const mm = HEADING_RE.exec(ad.lineText(i)); if (mm) rows.push({ line: i, depth: DEPTH[mm[1]] ?? 0, title: mm[2] || "(untitled)" }); }
    setOutline(rows);
  }, []);

  const pushDiagnostics = useCallback((diags: Diag[], fid: number) => {
    const ad = adRef.current; if (!ad) return;
    const path = filesRef.current.find((f) => f.id === fid)?.path ?? "main.tex";
    ad.setDiagnostics(diags.filter((d): d is Diag & { line: number } => !!d.line && (d.file || "main.tex") === path));
  }, []);

  const openFile = useCallback(async (fid: number) => {
    const ad = adRef.current; const f = filesRef.current.find((x) => x.id === fid);
    if (!ad || !f) return;
    if (f.kind === "asset") { if (f.url) window.open(f.url, "_blank"); return; }
    if (!loaded.current.has(fid)) {
      const data = await wb<{ content?: string }>(`${base}files/${fid}/`);
      ad.setFileValue(fid, data.content || ""); loaded.current.add(fid);
    }
    ad.switchFile(fid); setActiveId(fid);
    setTabs((tt) => (tt.includes(fid) ? tt : [...tt, fid]));
    recomputeOutline(); pushDiagnostics(compileRefState.current.diagnostics, fid);
    ad.focus();
  }, [base, recomputeOutline, pushDiagnostics]);
  const compileRefState = useRef(compile); compileRefState.current = compile;

  // --- mount the editor once the main file is known ---------------------------------
  useEffect(() => {
    if (!hostRef.current || adRef.current || !mainId) return;
    let cancelled = false;
    (async () => {
      const data = await wb<{ content?: string }>(`${base}files/${mainId}/`);
      if (cancelled || !hostRef.current) return;
      const ad = mountEditor(hostRef.current, {
        initialDoc: data.content || "", initialFileId: mainId, citeLibraryUrl: `${base}cite-library/`, csrfToken: csrfToken(), fillHost: true,
        extensions: [
          studioTheme, studioHighlight,
          Prec.highest(keymap.of([
            { key: "Mod-Enter", run: () => { compileRef.current(); return true; } },
            { key: "Mod-s", run: () => { saveNowRef.current(); return true; } },
          ])),
          EditorView.updateListener.of((u) => { if (u.selectionSet || u.docChanged) setLn(u.state.doc.lineAt(u.state.selection.main.head).number); }),
        ],
      });
      adRef.current = ad; loaded.current.add(mainId);
      ad.setKeymap(settingsRef.current.keymap); ad.setFontSize(String(settingsRef.current.fontSize)); ad.setSpellcheck(settingsRef.current.spellcheck);
      let outlineTimer = 0;
      ad.onChange(() => {
        const fid = ad.activeFile();
        markDirty(fid, true); gen.current.set(fid, (gen.current.get(fid) || 0) + 1);
        setSaveStatus("Unsaved changes");
        window.clearTimeout(timers.current.get(fid)); timers.current.set(fid, window.setTimeout(() => saveFile(fid), 1500));
        window.clearTimeout(outlineTimer); outlineTimer = window.setTimeout(recomputeOutline, 500);
      });
      setActiveId(mainId); setTabs([mainId]); setReady(true); recomputeOutline(); ad.focus();
    })();
    return () => { cancelled = true; };
  }, [base, mainId, saveFile, recomputeOutline]);

  // deep link from the Library: /manuscripts/:id/editor?quote=<highlight id> inserts that passage
  const [params, setParams] = useSearchParams();
  useEffect(() => {
    const qid = params.get("quote"); if (!ready || !qid) return;
    (async () => {
      try {
        const h = await api<Hl & { reference_detail?: { bibtex_key: string } }>(`/highlights/${qid}/`);
        const key = h.reference_detail?.bibtex_key ?? (await api<{ bibtex_key: string }>(`/references/${h.reference}/`)).bibtex_key;
        adRef.current?.insertAtCursor(quoteLatex(h.text, key, h.page)); setTab("bib"); setFlash("Quote inserted from your highlights.");
      } catch { setFlash("That highlight could not be loaded."); }
      params.delete("quote"); setParams(params, { replace: true });
    })();
  }, [ready, params, setParams]);

  useEffect(() => { const ad = adRef.current; if (!ad) return; ad.setKeymap(settings.keymap); ad.setFontSize(String(settings.fontSize)); ad.setSpellcheck(settings.spellcheck); try { localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings)); } catch { /* private mode */ } }, [settings, ready]);

  useEffect(() => { const guard = (e: BeforeUnloadEvent) => { if (dirtyRef.current.size) { e.preventDefault(); e.returnValue = ""; } }; window.addEventListener("beforeunload", guard); return () => window.removeEventListener("beforeunload", guard); }, []);

  // --- compile + status polling ------------------------------------------------------
  const applyStatus = useCallback((raw: Compile) => {
    // Tectonic repeats some warnings once per pass — show each distinct problem once
    const seen = new Set<string>();
    const s = { ...raw, diagnostics: (raw.diagnostics || []).filter((d) => { const k = `${d.level}|${d.file}|${d.line}|${d.message}`; if (seen.has(k)) return false; seen.add(k); return true; }) };
    setCompile(s);
    if (s.status !== "running") {
      if (s.pdf_url) setPdfUrl(`${s.pdf_url}${s.pdf_url.includes("?") ? "&" : "?"}t=${Date.now()}`);
      pushDiagnostics(s.diagnostics || [], activeRef.current);
      if ((s.diagnostics || []).some((d) => d.level === "error")) setProblemsOpen(true);
    }
  }, [pushDiagnostics]);
  const poll = useCallback(() => {
    if (pollRef.current) window.clearInterval(pollRef.current);
    let ticks = 0;
    pollRef.current = window.setInterval(async () => {
      try { const s = await api<Compile>(`/manuscripts/${m.id}/compile-status/`); if (s.status !== "running") { window.clearInterval(pollRef.current!); pollRef.current = null; applyStatus(s); return; } } catch { /* keep polling */ }
      if (++ticks > 160) { // 4 minutes: the worker is not answering — say so instead of spinning forever
        window.clearInterval(pollRef.current!); pollRef.current = null;
        setCompile((c) => ({ ...c, status: "failed", log: "No answer from the compile worker after 4 minutes. In a source checkout start it with `make worker` (desktop builds compile in-process). The first compile also downloads the TeX bundle, which needs network access." }));
      }
    }, 1500);
  }, [m.id, applyStatus]);
  useEffect(() => { api<Compile>(`/manuscripts/${m.id}/compile-status/`).then((s) => { applyStatus(s); if (s.status === "running") poll(); }).catch(() => {}); refreshWords(); return () => { if (pollRef.current) window.clearInterval(pollRef.current); }; }, [m.id, applyStatus, poll, refreshWords]);
  const doCompile = useCallback(async () => {
    if (compileRefState.current.status === "running") return;
    await saveAll();
    setCompile((c) => ({ ...c, status: "running" }));
    try { await api(`/manuscripts/${m.id}/compile/`, { method: "POST" }); poll(); }
    catch (e) { setCompile((c) => ({ ...c, status: "failed", log: e instanceof Error ? e.message : "Compile request failed." })); }
  }, [m.id, poll, saveAll]);
  compileRef.current = () => { void doCompile(); };

  // --- global shortcuts ----------------------------------------------------------------
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const mod = e.metaKey || e.ctrlKey; if (!mod) return;
      const k = e.key.toLowerCase();
      if (k === "s") { e.preventDefault(); saveNowRef.current(); }
      else if (k === "enter") { e.preventDefault(); compileRef.current(); }
      else if (k === "b") { e.preventDefault(); setSidebarOpen((v) => !v); }
      else if (k === "\\") { e.preventDefault(); setPreviewOpen((v) => !v); }
      else if (k === "j") { e.preventDefault(); setProblemsOpen((v) => !v); }
      else if (k === "p" && !e.shiftKey) { e.preventDefault(); setQuickOpen(true); }
    };
    window.addEventListener("keydown", onKey, true); return () => window.removeEventListener("keydown", onKey, true);
  }, []);

  // --- resizable columns ---------------------------------------------------------------
  useEffect(() => {
    if (!ready) return;
    const ids = [sidebarOpen ? "#studio-side" : null, "#studio-editor", previewOpen ? "#studio-preview" : null].filter(Boolean) as string[];
    if (ids.length < 2) return;
    const sizes = ids.length === 3 ? [17, 45, 38] : sidebarOpen ? [22, 78] : [55, 45];
    const split = Split(ids, { sizes, minSize: ids.map((x) => (x === "#studio-editor" ? 320 : 180)), gutterSize: 5, gutter: () => { const g = document.createElement("div"); g.className = "studio-gutter"; return g; } });
    return () => split.destroy();
  }, [ready, sidebarOpen, previewOpen]);

  // --- file operations ------------------------------------------------------------------
  const reloadFiles = useCallback(async () => { const d = await wb<{ files: MFile[] }>(`${base}files/`); setFiles(d.files); return d.files; }, [base]);
  const newFile = async () => {
    const path = window.prompt("New file path (e.g. sections/method.tex or references.bib)"); if (!path) return;
    try { const f = await wb<MFile>(`${base}files/`, { path }); const list = await reloadFiles(); if (list.some((x) => x.id === f.id)) { adRef.current?.setFileValue(f.id, ""); loaded.current.add(f.id); await openFile(f.id); } } catch (e) { setFlash(e instanceof Error ? e.message : "Could not create the file."); }
  };
  const uploadFile = async (file: File) => { try { await wb(`${base}files/upload/`, { file, path: file.name.replace(/\s+/g, "_") }); await reloadFiles(); setFlash(`Uploaded ${file.name}`); } catch (e) { setFlash(e instanceof Error ? e.message : "Upload failed."); } };
  const deleteFile = async (f: MFile) => { if (!window.confirm(`Delete ${f.path}?`)) return; await wb(`${base}files/${f.id}/delete/`, {}); loaded.current.delete(f.id); setTabs((tt) => tt.filter((x) => x !== f.id)); if (activeId === f.id) await openFile(mainId); await reloadFiles(); };
  const renameFile = async (f: MFile) => { const path = window.prompt("Rename to", f.path); if (!path || path === f.path) return; try { await wb(`${base}files/${f.id}/rename/`, { path }); await reloadFiles(); } catch (e) { setFlash(e instanceof Error ? e.message : "Rename failed."); } };
  const closeTab = (fid: number) => { setTabs((tt) => { const next = tt.filter((x) => x !== fid); if (fid === activeId) void openFile(next[next.length - 1] ?? mainId); return next.length ? next : [mainId]; }); };

  useEffect(() => { if (!flash) return; const tmr = window.setTimeout(() => setFlash(""), 3500); return () => window.clearTimeout(tmr); }, [flash]);

  const errors = compile.diagnostics.filter((d) => d.level === "error").length;
  const warnings = compile.diagnostics.length - errors;
  const running = compile.status === "running";
  const textFiles = files.filter((f) => f.kind !== "asset");

  return (
    <div className="studio fixed inset-0 flex flex-col" data-testid="studio">
      <input ref={fileInput} type="file" className="hidden" onChange={(e) => { const f = e.target.files?.[0]; if (f) void uploadFile(f); e.target.value = ""; }} />
      {/* ---------------------------------------------------------------- top bar */}
      <header className="flex h-11 shrink-0 items-center gap-1 border-b px-2" style={{ borderColor: "var(--studio-line)", background: "var(--studio-panel)" }}>
        <Link to={`/manuscripts/${m.id}`} className={iconBtn} title="Back to the manuscript"><ArrowLeft className="h-3.5 w-3.5" aria-hidden="true" />Studio</Link>
        <span className="mx-1 h-4 w-px" style={{ background: "var(--studio-line)" }} />
        <span className="truncate text-sm font-medium" style={{ color: "var(--studio-fg)" }} title={m.title}>{m.title}</span>
        <span className="ml-2 hidden truncate text-[11px] st-dim md:inline">{m.project_name}</span>
        <span className={`ml-3 truncate text-[11px] ${dirty.length ? "text-amber-400" : "st-dim"}`} data-testid="save-status">{saveStatus}</span>
        <div className="ml-auto flex items-center gap-0.5">
          <button type="button" onClick={() => setSidebarOpen((v) => !v)} className={`${iconBtn} ${sidebarOpen ? "st-fg" : ""}`} title="Toggle sidebar (⌘B)" aria-label="Toggle sidebar"><PanelLeft className="h-3.5 w-3.5" aria-hidden="true" /></button>
          <button type="button" onClick={() => setPreviewOpen((v) => !v)} className={`${iconBtn} ${previewOpen ? "st-fg" : ""}`} title="Toggle PDF preview (⌘\\)" aria-label="Toggle preview"><PanelRight className="h-3.5 w-3.5" aria-hidden="true" /></button>
          <button type="button" onClick={() => setProblemsOpen((v) => !v)} className={`${iconBtn} ${problemsOpen ? "st-fg" : ""}`} title="Problems (⌘J)"><TerminalSquare className="h-3.5 w-3.5" aria-hidden="true" />{errors > 0 && <span className="rounded-full bg-red-500/20 px-1.5 text-[10px] text-red-300">{errors}</span>}</button>
          <div className="relative">
            <button type="button" onClick={() => setSettingsOpen((v) => !v)} className={iconBtn} title="Editor settings" aria-label="Editor settings"><Settings2 className="h-3.5 w-3.5" aria-hidden="true" /></button>
            {settingsOpen && (
              <div className="absolute right-0 top-full z-30 mt-1 w-56 rounded-lg border p-3 text-xs shadow-xl" style={{ borderColor: "var(--studio-line)", background: "var(--studio-panel)", color: "var(--studio-fg)" }}>
                <label className="mb-2 flex items-center justify-between">Keymap<select value={settings.keymap} onChange={(e) => setSettings((s) => ({ ...s, keymap: e.target.value as Settings["keymap"] }))} className="rounded border bg-transparent px-1 py-0.5" style={{ borderColor: "var(--studio-line)" }}><option value="default">Default</option><option value="vim">Vim</option></select></label>
                <label className="mb-2 flex items-center justify-between">Font size<input type="number" min={11} max={22} value={settings.fontSize} onChange={(e) => setSettings((s) => ({ ...s, fontSize: Number(e.target.value) || 14 }))} className="w-14 rounded border bg-transparent px-1 py-0.5" style={{ borderColor: "var(--studio-line)" }} /></label>
                <label className="mb-2 flex items-center justify-between">Spellcheck<input type="checkbox" checked={settings.spellcheck} onChange={(e) => setSettings((s) => ({ ...s, spellcheck: e.target.checked }))} /></label>
                <label className="flex items-center justify-between">Compile on save<input type="checkbox" checked={settings.autoCompile} onChange={(e) => setSettings((s) => ({ ...s, autoCompile: e.target.checked }))} /></label>
                <p className="mt-3 border-t pt-2 text-[10px] leading-4 st-dim" style={{ borderColor: "var(--studio-line)" }}>⌘S save · ⌘↩ compile · ⌘B sidebar · ⌘\ preview · ⌘J problems · ⌘P quick open · ⌘F find</p>
              </div>
            )}
          </div>
          <a href={`${base}submission.zip`} className={iconBtn} title="arXiv-ready source + .bib"><Package className="h-3.5 w-3.5" aria-hidden="true" /><span className="hidden lg:inline">.zip</span></a>
          <button type="button" onClick={() => void doCompile()} disabled={running} className="ml-1 inline-flex h-7 items-center gap-1.5 rounded-md bg-indigo-600 px-3 text-xs font-medium text-white hover:bg-indigo-500 disabled:opacity-60" title="Recompile (⌘↩)" data-testid="compile-btn">{running ? <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" /> : <Play className="h-3.5 w-3.5" aria-hidden="true" />}{running ? "Compiling…" : "Recompile"}</button>
        </div>
      </header>

      {/* ---------------------------------------------------------------- body */}
      <div className="flex min-h-0 flex-1" style={{ background: "var(--studio-bg)" }}>
        {sidebarOpen && (
          <aside id="studio-side" className="flex min-w-0 flex-col border-r" style={{ borderColor: "var(--studio-line)", background: "var(--studio-panel)" }}>
            <nav className="flex shrink-0 border-b text-[11px]" style={{ borderColor: "var(--studio-line)" }} aria-label="Studio panels">
              {([["files", FolderOpen, "Files"], ["outline", ListTree, "Outline"], ["bib", BookOpen, "Bibliography"], ["history", History, "History"]] as [Tab, typeof FolderOpen, string][]).map(([key, Icon, label]) => (
                <button key={key} type="button" onClick={() => setTab(key)} className={`flex flex-1 items-center justify-center gap-1 py-2 transition-colors ${tab === key ? "border-b-2 border-indigo-400 st-fg" : "st-dim st-hover-fg"}`} title={label} aria-label={label}><Icon className="h-3.5 w-3.5" aria-hidden="true" /><span className="hidden xl:inline">{label}</span></button>
              ))}
            </nav>
            <div className="min-h-0 flex-1 overflow-y-auto p-2">
              {tab === "files" && (
                <div>
                  <div className="mb-1 flex items-center justify-between px-1 text-[10px] uppercase tracking-wider st-dim"><span>Files</span><span className="flex gap-1"><button type="button" onClick={() => void newFile()} className="st-hover-fg" title="New text file" aria-label="New file"><Plus className="h-3.5 w-3.5" aria-hidden="true" /></button><button type="button" onClick={() => fileInput.current?.click()} className="st-hover-fg" title="Upload a figure or file" aria-label="Upload"><Upload className="h-3.5 w-3.5" aria-hidden="true" /></button></span></div>
                  <ul>
                    {[...files].sort((a, b) => a.path.localeCompare(b.path)).map((f) => (
                      <li key={f.id}>
                        <div onClick={() => void openFile(f.id)} onDoubleClick={() => (f.kind === "asset" ? undefined : void renameFile(f))} className={`${sideItem} ${f.id === activeId ? "bg-indigo-500/15 st-fg" : "st-muted"}`} title={f.path} role="button" tabIndex={0} onKeyDown={(e) => { if (e.key === "Enter") void openFile(f.id); }}>
                          <FileText className="h-3.5 w-3.5 shrink-0 opacity-60" aria-hidden="true" /><span className="min-w-0 flex-1 truncate">{f.path}</span>
                          {f.is_main && <span className="rounded st-badge px-1 text-[9px] uppercase">main</span>}
                          {dirty.includes(f.id) && <span className="text-amber-400">●</span>}
                          {!f.is_main && <button type="button" onClick={(e) => { e.stopPropagation(); void deleteFile(f); }} className="hidden st-dim hover:text-red-400 group-hover:inline" aria-label={`Delete ${f.path}`}><Trash2 className="h-3 w-3" aria-hidden="true" /></button>}
                        </div>
                      </li>
                    ))}
                  </ul>
                  <p className="mt-3 px-1 text-[10px] leading-4 st-dim">Double-click renames. Figures uploaded here are available to \includegraphics.</p>
                </div>
              )}
              {tab === "outline" && (
                <div>
                  <p className="mb-1 px-1 text-[10px] uppercase tracking-wider st-dim">Outline · {pathOf(activeId)}</p>
                  {outline.length === 0 && <p className="px-1 text-xs st-dim">No \section yet — the outline fills in as you write.</p>}
                  <ul>{outline.map((o) => <li key={o.line}><button type="button" onClick={() => adRef.current?.gotoLine(o.line)} className={`${sideItem} st-text`} style={{ paddingLeft: 8 + o.depth * 12 }} title={`line ${o.line}`}><span className="truncate">{o.title}</span></button></li>)}</ul>
                </div>
              )}
              {tab === "bib" && <BibPanel m={m} base={base} onInsert={(key) => { adRef.current?.insertAtCursor(`\\cite{${key}}`); }} onQuote={(latex) => { adRef.current?.insertAtCursor(latex); setFlash("Quote inserted."); }} onLinked={() => adRef.current?.reloadCiteLibrary()} />}
              {tab === "history" && <HistoryPanel base={base} onRestored={async () => { loaded.current.clear(); const ad = adRef.current; if (ad) { for (const fid of tabs) { const data = await wb<{ content?: string }>(`${base}files/${fid}/`); ad.setFileValue(fid, data.content || ""); loaded.current.add(fid); } } setFlash("Version restored."); recomputeOutline(); }} />}
            </div>
          </aside>
        )}

        <section id="studio-editor" className="flex min-w-0 flex-col">
          <div className="flex h-8 shrink-0 items-stretch overflow-x-auto border-b text-xs" style={{ borderColor: "var(--studio-line)", background: "var(--studio-panel)" }} role="tablist">
            {tabs.map((fid) => { const f = files.find((x) => x.id === fid); if (!f) return null; return (
              <div key={fid} role="tab" aria-selected={fid === activeId} onClick={() => void openFile(fid)} className={`group flex cursor-pointer items-center gap-1.5 border-r px-3 ${fid === activeId ? "st-fg" : "st-dim st-hover-fg"}`} style={{ borderColor: "var(--studio-line)", background: fid === activeId ? "var(--studio-editor-bg)" : "transparent" }}>
                <span className="truncate">{f.path}</span>{dirty.includes(fid) ? <span className="text-amber-400">●</span> : tabs.length > 1 && <button type="button" onClick={(e) => { e.stopPropagation(); closeTab(fid); }} className="opacity-0 st-hover-fg group-hover:opacity-100" aria-label={`Close ${f.path}`}><X className="h-3 w-3" aria-hidden="true" /></button>}
              </div>); })}
            <button type="button" onClick={() => setQuickOpen(true)} className="ml-auto px-2 st-dim st-hover-fg" title="Quick open (⌘P)" aria-label="Quick open"><Search className="h-3.5 w-3.5" aria-hidden="true" /></button>
          </div>
          <div ref={hostRef} className="min-h-0 flex-1 overflow-hidden" data-testid="editor-host" />
          {problemsOpen && (
            <div className="flex h-44 shrink-0 flex-col border-t text-xs" style={{ borderColor: "var(--studio-line)", background: "var(--studio-panel)" }} data-testid="problems">
              <div className="flex items-center gap-2 px-3 py-1 text-[10px] uppercase tracking-wider st-dim"><span>Problems</span><span className="normal-case tracking-normal">{errors} error{errors === 1 ? "" : "s"} · {warnings} warning{warnings === 1 ? "" : "s"}</span><button type="button" onClick={() => setProblemsOpen(false)} className="ml-auto st-hover-fg" aria-label="Close problems"><X className="h-3.5 w-3.5" aria-hidden="true" /></button></div>
              <ul className="min-h-0 flex-1 overflow-y-auto">
                {compile.diagnostics.length === 0 && <li className="px-3 py-1 st-dim">{compile.status === "failed" ? "The compile failed before producing diagnostics — see the log in the preview pane." : compile.status === "ok" ? "No problems. Clean compile." : "Compile to see problems here."}</li>}
                {compile.diagnostics.map((d, i) => (
                  <li key={i}><button type="button" onClick={async () => { const target = files.find((f) => f.path === (d.file || "main.tex")); if (target && target.id !== activeId) await openFile(target.id); if (d.line) adRef.current?.gotoLine(d.line); }} className="flex w-full items-baseline gap-2 px-3 py-1 text-left st-hover-bg">
                    <span className={`shrink-0 text-[10px] font-semibold uppercase ${d.level === "error" ? "text-red-400" : "text-amber-400"}`}>{d.level}</span>
                    {d.line && <span className="shrink-0 font-mono text-[10px] st-dim">{d.file && d.file !== pathOf(activeId) ? `${d.file} ` : ""}L{d.line}</span>}
                    <span className="min-w-0 flex-1 truncate st-text">{d.message}</span></button></li>
                ))}
              </ul>
            </div>
          )}
        </section>

        {previewOpen && <PdfPane id="studio-preview" url={pdfUrl} status={compile.status} log={compile.log} compiledAt={compile.compiled_at} />}
      </div>

      {/* ---------------------------------------------------------------- status bar */}
      <footer className="flex h-6 shrink-0 items-center gap-4 border-t px-3 text-[11px] st-dim" style={{ borderColor: "var(--studio-line)", background: "var(--studio-panel)" }} data-testid="statusbar">
        <span>Ln {ln}</span>
        <span>{pathOf(activeId)}</span>
        {words && <span title={`headers ${words.headers ?? 0} · captions ${words.captions ?? 0} · math ${words.math ?? 0}`}>{words.words.toLocaleString()} words</span>}
        {missingCites > 0 && <span className="text-amber-400">{missingCites} cite key{missingCites === 1 ? "" : "s"} not in the bibliography</span>}
        <span className={`ml-auto ${compile.status === "ok" ? "text-emerald-400" : compile.status === "failed" ? "text-red-400" : running ? "text-indigo-300" : ""}`}>{running ? "compiling" : compile.status === "ok" ? `compiled ${compile.compiled_at ? new Date(compile.compiled_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" }) : ""}` : compile.status === "failed" ? "compile failed" : "not compiled"}</span>
        <span>{settings.keymap === "vim" ? "VIM" : "LaTeX"}</span>
        {flash && <span className="rounded bg-indigo-500/20 px-2 text-indigo-200">{flash}</span>}
      </footer>

      {quickOpen && <QuickOpen files={textFiles} outline={outline} onClose={() => setQuickOpen(false)} onPick={(pick) => { setQuickOpen(false); if (pick.kind === "file") void openFile(pick.id); else adRef.current?.gotoLine(pick.line); }} />}
    </div>
  );
}

// ------------------------------------------------------------------ side panels
function BibPanel({ m, base, onInsert, onQuote, onLinked }: { m: Manuscript; base: string; onInsert: (key: string) => void; onQuote: (latex: string) => void; onLinked: () => void }) {
  const bib = useQuery({ queryKey: ["manuscript-bib", m.id], queryFn: () => api<BibRow[]>(`/manuscripts/${m.id}/bibliography/`) });
  const [openRef, setOpenRef] = useState<number | null>(null);
  const [q, setQ] = useState("");
  const lib = useQuery({ queryKey: ["cite-library", m.id], queryFn: () => wb<{ candidates: Candidate[] }>(`${base}cite-library/`), enabled: q.length > 0 });
  const matches = useMemo(() => { const needle = q.toLowerCase(); return (lib.data?.candidates ?? []).filter((c) => !c.linked && (c.key.toLowerCase().includes(needle) || c.title.toLowerCase().includes(needle) || c.authors.toLowerCase().includes(needle))).slice(0, 12); }, [lib.data, q]);
  const link = async (c: Candidate) => { await wb(`${base}cite-library/`, { reference: String(c.reference_id) }); await bib.refetch(); await lib.refetch(); onLinked(); onInsert(c.key); };
  return (
    <div>
      <p className="mb-1 px-1 text-[10px] uppercase tracking-wider st-dim">Bibliography · {bib.data?.length ?? 0}</p>
      <p className="mb-2 px-1 text-[10px] leading-4 st-dim">Click a paper to insert \cite{"{key}"}; ✎ shows the passages you highlighted while reading — one click quotes them with the citation. Type \cite{"{"} in the editor to complete from the whole library.</p>
      <ul className="mb-3">{(bib.data ?? []).map((r) => (
        <li key={r.link_id}>
          <div className="flex items-center">
            <button type="button" onClick={() => onInsert(r.cite_key)} className={`${sideItem} st-text`} title={`${r.authors} (${r.year ?? "n.d."}) — ${r.title}`}><span className="shrink-0 font-mono text-indigo-300">@{r.cite_key}</span><span className="truncate st-dim">{r.title}</span></button>
            <button type="button" onClick={() => setOpenRef(openRef === r.reference_id ? null : r.reference_id)} className="shrink-0 px-1 text-[10px] st-dim st-hover-fg" title="Your highlights from this paper" aria-label={`Highlights of ${r.cite_key}`}>{openRef === r.reference_id ? "−" : "✎"}</button>
          </div>
          {openRef === r.reference_id && <PaperHighlights referenceId={r.reference_id} citeKey={r.cite_key} onQuote={onQuote} />}
        </li>
      ))}</ul>
      <div className="relative px-1"><Search className="pointer-events-none absolute left-3 top-1.5 h-3 w-3 st-dim" aria-hidden="true" /><input value={q} onChange={(e) => setQ(e.target.value)} placeholder="Add from the project library…" className="w-full rounded-md border bg-transparent py-1 pl-6 pr-2 text-xs st-fg st-placeholder focus:outline-none" style={{ borderColor: "var(--studio-line)" }} aria-label="Search the library" /></div>
      {q && <ul className="mt-1">{matches.map((c) => <li key={c.reference_id}><button type="button" onClick={() => void link(c)} className={`${sideItem} st-text`} title={c.title}><Plus className="h-3 w-3 shrink-0 text-emerald-400" aria-hidden="true" /><span className="shrink-0 font-mono text-indigo-300">@{c.key}</span><span className="truncate st-dim">{c.authors} {c.year ?? ""}</span></button></li>)}{lib.data && matches.length === 0 && <li className="px-2 py-1 text-xs st-dim">Nothing unlinked matches.</li>}</ul>}
    </div>
  );
}

function PaperHighlights({ referenceId, citeKey, onQuote }: { referenceId: number; citeKey: string; onQuote: (latex: string) => void }) {
  const hls = useQuery({ queryKey: ["studio-highlights", referenceId], queryFn: () => api<{ results: Hl[] }>(`/highlights/?reference=${referenceId}&page_size=100`).then((p) => p.results) });
  if (!hls.data) return <p className="px-2 py-1 text-[10px] st-dim">Loading highlights…</p>;
  if (hls.data.length === 0) return <p className="px-2 py-1 text-[10px] st-dim">No highlights yet — read it in the Library and select text.</p>;
  return (
    <ul className="mb-1 ml-2 border-l pl-2" style={{ borderColor: "var(--studio-line)" }} data-testid="paper-highlights">
      {hls.data.map((h) => (
        <li key={h.id} className="group py-1">
          <p className="line-clamp-3 text-[11px] leading-4 st-text">{h.text}</p>
          <div className="mt-0.5 flex items-center gap-2 text-[10px] st-dim"><span>{h.page ? `p. ${h.page}` : "no page"}</span>{h.comment && <span className="truncate italic">{h.comment}</span>}<button type="button" onClick={() => onQuote(quoteLatex(h.text, citeKey, h.page))} className="ml-auto text-indigo-300 hover:underline" title="Insert as a quote with \\citep{} at the cursor">quote →</button></div>
        </li>
      ))}
    </ul>
  );
}

function HistoryPanel({ base, onRestored }: { base: string; onRestored: () => Promise<void> }) {
  const revs = useQuery({ queryKey: ["revisions", base], queryFn: () => wb<{ revisions: Revision[] }>(`${base}revisions/`) });
  const [open, setOpen] = useState<Revision | null>(null);
  const [diff, setDiff] = useState<{ path: string; diff: string }[] | null>(null);
  const show = async (r: Revision) => { setOpen(r); setDiff(null); const d = await wb<{ diffs: { path: string; diff: string }[] }>(`${base}revisions/${r.id}/diff/`); setDiff(d.diffs); };
  const snapshot = async () => { const label = window.prompt("Label this version", "Before major edit"); if (label === null) return; await wb(`${base}revisions/`, { label }); await revs.refetch(); };
  const restore = async () => { if (!open || !window.confirm(`Restore "${open.label || "this version"}"? The current text is snapshotted first.`)) return; await wb(`${base}revisions/${open.id}/restore/`, {}); setOpen(null); await revs.refetch(); await onRestored(); };
  return (
    <div>
      <div className="mb-1 flex items-center justify-between px-1 text-[10px] uppercase tracking-wider st-dim"><span>History</span><button type="button" onClick={() => void snapshot()} className="normal-case tracking-normal text-indigo-300 hover:underline">+ snapshot</button></div>
      <p className="mb-2 px-1 text-[10px] leading-4 st-dim">Every successful compile snapshots the source. Label a version to keep it findable.</p>
      <ul>{(revs.data?.revisions ?? []).map((r) => <li key={r.id}><button type="button" onClick={() => void show(r)} className={`${sideItem} ${open?.id === r.id ? "bg-indigo-500/15 st-fg" : "st-text"}`}><span className="min-w-0 flex-1 truncate">{r.labeled ? r.label : "auto"}</span><span className="shrink-0 text-[10px] st-dim">{new Date(r.created_at).toLocaleString([], { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</span></button></li>)}{revs.data && revs.data.revisions.length === 0 && <li className="px-2 text-xs st-dim">No versions yet — compile once.</li>}</ul>
      {open && (
        <div className="fixed inset-x-8 inset-y-12 z-40 flex flex-col rounded-xl border shadow-2xl" style={{ borderColor: "var(--studio-line)", background: "var(--studio-panel)" }} role="dialog" aria-label="Version diff">
          <div className="flex items-center gap-2 border-b px-4 py-2 text-xs" style={{ borderColor: "var(--studio-line)" }}><History className="h-3.5 w-3.5 st-muted" aria-hidden="true" /><span className="st-fg">{open.labeled ? open.label : "auto snapshot"}</span><span className="st-dim">{new Date(open.created_at).toLocaleString()}</span><button type="button" onClick={() => void restore()} className="ml-auto rounded-md bg-indigo-600 px-2.5 py-1 font-medium text-white hover:bg-indigo-500">Restore this version</button><button type="button" onClick={() => setOpen(null)} className={iconBtn} aria-label="Close"><X className="h-3.5 w-3.5" aria-hidden="true" /></button></div>
          <pre className="min-h-0 flex-1 overflow-auto p-4 font-mono text-[11px] leading-5 st-text">{diff === null ? "Loading diff…" : diff.length === 0 ? "Identical to the current text." : diff.map((d) => `--- ${d.path}\n${d.diff}`).join("\n\n").split("\n").map((line, i) => <span key={i} className={line.startsWith("+") && !line.startsWith("+++") ? "text-emerald-300" : line.startsWith("-") && !line.startsWith("---") ? "text-red-300" : line.startsWith("@@") ? "text-indigo-300" : ""}>{line}{"\n"}</span>)}</pre>
        </div>
      )}
    </div>
  );
}

function QuickOpen({ files, outline, onClose, onPick }: { files: MFile[]; outline: { line: number; depth: number; title: string }[]; onClose: () => void; onPick: (p: { kind: "file"; id: number } | { kind: "line"; line: number }) => void }) {
  const [q, setQ] = useState("");
  const [active, setActive] = useState(0);
  const rows = useMemo(() => { const needle = q.toLowerCase(); const fs = files.filter((f) => f.path.toLowerCase().includes(needle)).map((f) => ({ kind: "file" as const, id: f.id, label: f.path, tag: "file" })); const os = outline.filter((o) => o.title.toLowerCase().includes(needle)).map((o) => ({ kind: "line" as const, line: o.line, label: o.title, tag: `L${o.line}` })); return [...fs, ...os].slice(0, 14); }, [files, outline, q]);
  useEffect(() => setActive(0), [q]);
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-black/40 pt-24" onClick={onClose} role="presentation">
      <div className="w-full max-w-lg overflow-hidden rounded-xl border shadow-2xl" style={{ borderColor: "var(--studio-line)", background: "var(--studio-panel)" }} onClick={(e) => e.stopPropagation()} role="dialog" aria-label="Quick open">
        <input autoFocus value={q} onChange={(e) => setQ(e.target.value)} onKeyDown={(e) => { if (e.key === "Escape") onClose(); else if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(a + 1, rows.length - 1)); } else if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); } else if (e.key === "Enter" && rows[active]) { const r = rows[active]; onPick(r.kind === "file" ? { kind: "file", id: r.id } : { kind: "line", line: r.line }); } }} placeholder="Jump to a file or section…" className="w-full border-b bg-transparent px-4 py-3 text-sm st-fg st-placeholder focus:outline-none" style={{ borderColor: "var(--studio-line)" }} aria-label="Quick open" />
        <ul className="max-h-80 overflow-y-auto py-1 text-xs">{rows.map((r, i) => <li key={`${r.kind}-${r.label}-${i}`}><button type="button" onMouseEnter={() => setActive(i)} onClick={() => onPick(r.kind === "file" ? { kind: "file", id: r.id } : { kind: "line", line: r.line })} className={`flex w-full items-center gap-2 px-4 py-1.5 text-left ${i === active ? "bg-indigo-500/20 st-fg" : "st-text"}`}>{r.kind === "file" ? <FileText className="h-3.5 w-3.5 st-dim" aria-hidden="true" /> : <ListTree className="h-3.5 w-3.5 st-dim" aria-hidden="true" />}<span className="min-w-0 flex-1 truncate">{r.label}</span><span className="font-mono text-[10px] st-dim">{r.tag}</span></button></li>)}{rows.length === 0 && <li className="px-4 py-2 st-dim">Nothing matches.</li>}</ul>
      </div>
    </div>
  );
}

// ------------------------------------------------------------------ PDF preview
function PdfPane({ id, url, status, log, compiledAt }: { id: string; url: string | null; status: string; log: string; compiledAt: string | null }) {
  const scroll = useRef<HTMLDivElement>(null);
  const pagesEl = useRef<HTMLDivElement>(null);
  const [numPages, setNumPages] = useState(0);
  const [page, setPage] = useState(1);
  const [zoom, setZoom] = useState<number | "fit">("fit");
  const [error, setError] = useState("");
  const [rendering, setRendering] = useState(false);
  const docRef = useRef<{ numPages: number; getPage: (n: number) => Promise<unknown> } | null>(null);

  useEffect(() => {
    if (!url) return;
    let cancelled = false;
    (async () => {
      try {
        setError(""); setRendering(true);
        const lib = (await import(/* @vite-ignore */ PDFJS)) as Record<string, unknown>;
        (lib.GlobalWorkerOptions as { workerSrc: string }).workerSrc = PDFJS_WORKER;
        const doc = await (lib.getDocument as (u: string) => { promise: Promise<{ numPages: number; getPage: (n: number) => Promise<unknown> }> })(url).promise;
        if (cancelled) return;
        docRef.current = doc; setNumPages(doc.numPages);
      } catch (e) { if (!cancelled) setError(e instanceof Error ? e.message : "Could not open the PDF."); }
      finally { if (!cancelled) setRendering(false); }
    })();
    return () => { cancelled = true; };
  }, [url]);

  useEffect(() => {
    const doc = docRef.current; const host = pagesEl.current; if (!doc || !host || !numPages) return;
    let cancelled = false;
    (async () => {
      host.innerHTML = "";
      const width = (scroll.current?.clientWidth ?? 700) - 32;
      for (let n = 1; n <= Math.min(numPages, 60); n++) {
        if (cancelled) return;
        const p = (await doc.getPage(n)) as { getViewport: (o: { scale: number }) => { width: number; height: number }; render: (o: { canvasContext: CanvasRenderingContext2D | null; viewport: unknown }) => { promise: Promise<void> } };
        const base = p.getViewport({ scale: 1 });
        const scale = zoom === "fit" ? width / base.width : zoom;
        const viewport = p.getViewport({ scale });
        const canvas = document.createElement("canvas");
        canvas.width = viewport.width; canvas.height = viewport.height; canvas.className = "studio-page"; canvas.dataset.page = String(n);
        host.appendChild(canvas);
        await p.render({ canvasContext: canvas.getContext("2d"), viewport }).promise;
      }
    })();
    return () => { cancelled = true; };
  }, [numPages, zoom, url]);

  useEffect(() => {
    const el = scroll.current; if (!el) return;
    const onScroll = () => { const canvases = el.querySelectorAll<HTMLCanvasElement>("canvas.studio-page"); const mid = el.scrollTop + el.clientHeight / 3; let cur = 1; canvases.forEach((c) => { if (c.offsetTop <= mid) cur = Number(c.dataset.page); }); setPage(cur); };
    el.addEventListener("scroll", onScroll, { passive: true }); return () => el.removeEventListener("scroll", onScroll);
  }, [numPages]);

  const go = (n: number) => { const c = scroll.current?.querySelector<HTMLCanvasElement>(`canvas[data-page="${n}"]`); if (c && scroll.current) scroll.current.scrollTo({ top: c.offsetTop - 8, behavior: "smooth" }); };
  const zoomLabel = zoom === "fit" ? "fit" : `${Math.round(zoom * 100)}%`;
  const step = (dir: 1 | -1) => setZoom((z) => { const cur = z === "fit" ? 1 : z; return Math.min(3, Math.max(0.4, Math.round((cur + dir * 0.15) * 100) / 100)); });

  return (
    <section id={id} className="flex min-w-0 flex-col border-l" style={{ borderColor: "var(--studio-line)", background: "var(--studio-panel)" }} data-testid="preview">
      <div className="flex h-8 shrink-0 items-center gap-1 border-b px-2 text-[11px] st-muted" style={{ borderColor: "var(--studio-line)" }}>
        <span className="uppercase tracking-wider st-dim">Preview</span>
        {numPages > 0 && <span className="ml-2 flex items-center gap-1"><button type="button" onClick={() => go(Math.max(1, page - 1))} className="st-hover-fg" aria-label="Previous page"><ChevronLeft className="h-3.5 w-3.5" aria-hidden="true" /></button><span className="tabular-nums">{page} / {numPages}</span><button type="button" onClick={() => go(Math.min(numPages, page + 1))} className="st-hover-fg" aria-label="Next page"><ChevronRight className="h-3.5 w-3.5" aria-hidden="true" /></button></span>}
        <span className="ml-auto flex items-center gap-1"><button type="button" onClick={() => step(-1)} className="st-hover-fg" aria-label="Zoom out"><Minus className="h-3.5 w-3.5" aria-hidden="true" /></button><button type="button" onClick={() => setZoom("fit")} className="w-9 text-center tabular-nums st-hover-fg" title="Fit width">{zoomLabel}</button><button type="button" onClick={() => step(1)} className="st-hover-fg" aria-label="Zoom in"><Plus className="h-3.5 w-3.5" aria-hidden="true" /></button>{url && <a href={url.split("?")[0]} target="_blank" rel="noreferrer" className="ml-1 st-hover-fg" title="Download the PDF" aria-label="Download PDF"><Download className="h-3.5 w-3.5" aria-hidden="true" /></a>}</span>
      </div>
      <div ref={scroll} className={`relative min-h-0 flex-1 overflow-y-auto transition-opacity ${status === "running" ? "opacity-50" : ""}`} style={{ background: "var(--studio-bg)" }}>
        <div ref={pagesEl} className="mx-auto flex flex-col items-center gap-3 p-4" />
        {!url && status !== "failed" && (
          <div className="absolute inset-0 flex flex-col items-center justify-center gap-2 p-6 text-center text-xs st-dim">
            {status === "running" ? <Loader2 className="h-5 w-5 animate-spin text-indigo-400" aria-hidden="true" /> : <RefreshCw className="h-5 w-5 st-dim" aria-hidden="true" />}
            <p>{status === "running" ? "Compiling with Tectonic — the first run downloads the TeX bundle and can take a minute." : "No PDF yet. Press ⌘↩ or Recompile."}</p>
          </div>
        )}
        {status === "failed" && (
          <div className="absolute inset-x-0 bottom-0 max-h-[60%] overflow-auto border-t bg-red-950/60 p-3 text-[11px] text-red-100 backdrop-blur" style={{ borderColor: "var(--studio-line)" }} data-testid="compile-log">
            <p className="mb-1 flex items-center gap-1 font-medium"><AlertTriangle className="h-3.5 w-3.5" aria-hidden="true" />Compile failed{compiledAt ? " — showing the last good PDF" : ""}</p>
            <pre className="whitespace-pre-wrap font-mono leading-4 text-red-200/90">{log || "No log was captured."}</pre>
          </div>
        )}
        {error && <p className="p-4 text-xs text-red-300">{error}</p>}
        {rendering && url && <div className="absolute right-3 top-3 rounded-full bg-black/50 px-2 py-0.5 text-[10px] st-text">rendering…</div>}
        {status === "ok" && url && numPages > 0 && <div className="pointer-events-none absolute right-3 top-3 flex items-center gap-1 rounded-full bg-emerald-500/15 px-2 py-0.5 text-[10px] text-emerald-300"><Check className="h-3 w-3" aria-hidden="true" />up to date</div>}
      </div>
    </section>
  );
}
