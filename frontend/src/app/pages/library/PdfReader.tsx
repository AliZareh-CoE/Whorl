/** In-workbench PDF reader (Library v2 slice 7). pdf.js (vendored) renders pages lazily with a
 *  text layer; selecting text pops a colour bar that saves a structured Highlight through the API.
 *  Saved highlights are painted back onto the text layer by matching their text on the page. */
import { useCallback, useEffect, useRef, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { ChevronDown, ChevronLeft, ChevronRight, ExternalLink, Highlighter, Loader2, Minus, Plus, Search, X } from "lucide-react";
import { api } from "../../api";

export type Highlight = {
  id: number; reference: number; project: string | null; project_name: string; page: number | null;
  text: string; comment: string; color: "yellow" | "green" | "blue" | "pink"; created_at: string;
};
export const HL_COLORS: Record<Highlight["color"], string> = { yellow: "#facc15", green: "#4ade80", blue: "#60a5fa", pink: "#f472b6" };

type Props = {
  refId: number;
  initialFind?: string;
  pdfUrl: string;
  title: string;
  highlights: Highlight[];
  projects: { slug: string; name: string }[];
  project: string;
  onProject: (slug: string) => void;
  onSave: (h: { text: string; page: number | null; color: Highlight["color"] }) => Promise<void>;
  onClose: () => void;
  jump: { page: number; nonce: number } | null;
  fullReaderHref: string;
};

const WORKER = "/static/vendor/pdfjs/pdf.worker.min.mjs";
const LIB = "/static/vendor/pdfjs/pdf.min.mjs";

function norm(s: string): string { return s.replace(/\s+/g, " ").trim().toLowerCase(); }

/** Paint saved highlights (and the current find term) onto a rendered text layer by
 *  substring-matching span text — no stored rectangles, so a replaced PDF still shows them. */
export function paintHighlights(layer: HTMLElement, marks: Highlight[], find = "") {
  const spans = Array.from(layer.querySelectorAll<HTMLSpanElement>("span"));
  for (const span of spans) { span.removeAttribute("data-hl"); span.removeAttribute("data-find"); }
  for (const h of marks) {
    const hay = norm(h.text);
    if (hay.length < 4) continue;
    for (const span of spans) {
      const t = norm(span.textContent ?? "");
      if (t.length >= 4 && hay.includes(t)) span.dataset.hl = h.color;
    }
  }
  const term = norm(find);
  if (term.length >= 2) {
    for (const span of spans) {
      const t = norm(span.textContent ?? "");
      if (t.includes(term) || (term.length >= 4 && t.length >= 4 && term.includes(t))) span.dataset.find = "1";
    }
  }
}

export default function PdfReader({ refId, initialFind = "", pdfUrl, title, highlights, projects, project, onProject, onSave, onClose, jump, fullReaderHref }: Props) {
  const scroller = useRef<HTMLDivElement>(null);
  const [findInput, setFindInput] = useState(initialFind);
  const [find, setFind] = useState(initialFind);
  const [hitIndex, setHitIndex] = useState(0);
  const hits = useQuery({ queryKey: ["pdf-find", refId, find], queryFn: () => api<{ page: number; snippet: string }[]>(`/references/${refId}/text-search/?q=${encodeURIComponent(find)}`), enabled: find.trim().length >= 2, staleTime: 60_000 });
  const findRef = useRef(find);
  findRef.current = find;
  const [scale, setScale] = useState(1.25);
  const [numPages, setNumPages] = useState(0);
  const [current, setCurrent] = useState(1);
  const [error, setError] = useState("");
  const [popover, setPopover] = useState<{ x: number; y: number; text: string; page: number | null } | null>(null);
  const [saving, setSaving] = useState(false);
  const pdfRef = useRef<{ numPages: number; getPage: (n: number) => Promise<unknown> } | null>(null);
  const libRef = useRef<Record<string, unknown> | null>(null);
  const rendered = useRef<Map<number, number>>(new Map()); // page -> scale it was rendered at
  const highlightsRef = useRef(highlights);
  highlightsRef.current = highlights;

  // load the document once
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const lib = (await import(/* @vite-ignore */ LIB)) as Record<string, unknown>;
        (lib.GlobalWorkerOptions as { workerSrc: string }).workerSrc = WORKER;
        const doc = await (lib.getDocument as (u: string) => { promise: Promise<{ numPages: number; getPage: (n: number) => Promise<unknown> }> })(pdfUrl).promise;
        if (cancelled) return;
        libRef.current = lib;
        pdfRef.current = doc;
        setNumPages(doc.numPages);
      } catch (e) {
        if (!cancelled) setError(e instanceof Error ? e.message : "Could not open the PDF.");
      }
    })();
    return () => { cancelled = true; };
  }, [pdfUrl]);

  const renderPage = useCallback(async (n: number) => {
    const doc = pdfRef.current; const lib = libRef.current; const root = scroller.current;
    if (!doc || !lib || !root) return;
    if (rendered.current.get(n) === scale) return;
    rendered.current.set(n, scale);
    const wrap = root.querySelector<HTMLDivElement>(`[data-page="${n}"]`);
    if (!wrap) return;
    const page = (await doc.getPage(n)) as { getViewport: (o: { scale: number }) => { width: number; height: number }; render: (o: unknown) => { promise: Promise<void> }; streamTextContent: () => unknown };
    const viewport = page.getViewport({ scale });
    wrap.style.width = `${viewport.width}px`; wrap.style.height = `${viewport.height}px`;
    wrap.innerHTML = "";
    const canvas = document.createElement("canvas");
    canvas.width = viewport.width; canvas.height = viewport.height;
    wrap.appendChild(canvas);
    const textDiv = document.createElement("div"); textDiv.className = "textLayer"; wrap.appendChild(textDiv);
    await page.render({ canvasContext: canvas.getContext("2d"), viewport }).promise;
    const TextLayer = lib.TextLayer as new (o: unknown) => { render: () => Promise<void> };
    await new TextLayer({ textContentSource: page.streamTextContent(), container: textDiv, viewport }).render();
    paintHighlights(textDiv, highlightsRef.current.filter((h) => h.page === n), findRef.current);
  }, [scale]);

  // lazy render on scroll + current page tracking
  useEffect(() => {
    const root = scroller.current;
    if (!root || numPages === 0) return;
    rendered.current.clear();
    const io = new IntersectionObserver((entries) => {
      for (const e of entries) {
        const n = Number((e.target as HTMLElement).dataset.page);
        if (e.isIntersecting) { void renderPage(n); if (e.intersectionRatio > 0.4) setCurrent(n); }
      }
    }, { root, rootMargin: "600px 0px", threshold: [0, 0.5] });
    root.querySelectorAll("[data-page]").forEach((el) => io.observe(el));
    return () => io.disconnect();
  }, [numPages, renderPage]);

  // repaint highlights / find matches when they change
  useEffect(() => {
    const root = scroller.current;
    if (!root) return;
    root.querySelectorAll<HTMLElement>("[data-page]").forEach((wrap) => {
      const layer = wrap.querySelector<HTMLElement>(".textLayer");
      if (layer) paintHighlights(layer, highlights.filter((h) => h.page === Number(wrap.dataset.page)), find);
    });
  }, [highlights, find]);

  // walking the find hits scrolls to their pages
  const goTo = useCallback((page: number) => {
    scroller.current?.querySelector(`[data-page="${page}"]`)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, []);
  useEffect(() => {
    const page = hits.data?.[hitIndex]?.page;
    if (page) goTo(page);
  }, [hits.data, hitIndex, goTo]);
  useEffect(() => { setHitIndex(0); }, [find]);
  useEffect(() => { if (initialFind) { setFindInput(initialFind); setFind(initialFind); } }, [initialFind]);

  // jump to a page from the highlights list
  useEffect(() => {
    if (!jump) return;
    scroller.current?.querySelector(`[data-page="${jump.page}"]`)?.scrollIntoView({ behavior: "smooth", block: "start" });
  }, [jump]);

  // selection → colour bar
  const onMouseUp = () => {
    const sel = window.getSelection();
    const text = sel ? sel.toString().trim() : "";
    if (!sel || text.length < 3 || sel.rangeCount === 0) { setPopover(null); return; }
    const node = sel.anchorNode instanceof Element ? sel.anchorNode : sel.anchorNode?.parentElement;
    const wrap = node?.closest<HTMLElement>("[data-page]");
    if (!wrap || !scroller.current) { setPopover(null); return; }
    const rect = sel.getRangeAt(0).getBoundingClientRect();
    const host = scroller.current.getBoundingClientRect();
    setPopover({ x: rect.left - host.left + rect.width / 2, y: rect.top - host.top + scroller.current.scrollTop - 8, text: text.slice(0, 2000), page: Number(wrap.dataset.page) });
  };

  const save = async (color: Highlight["color"]) => {
    if (!popover) return;
    setSaving(true);
    try { await onSave({ text: popover.text, page: popover.page, color }); setPopover(null); window.getSelection()?.removeAllRanges(); }
    finally { setSaving(false); }
  };

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT") return;
      if (e.key === "Escape") { if (popover) setPopover(null); else onClose(); }
      else if (e.key === "+" || e.key === "=") setScale((s) => Math.min(2.5, +(s + 0.15).toFixed(2)));
      else if (e.key === "-") setScale((s) => Math.max(0.6, +(s - 0.15).toFixed(2)));
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [popover, onClose]);

  return (
    <section className="rise flex min-h-[60vh] flex-col overflow-hidden rounded-2xl border border-stone-200 bg-white dark:border-stone-800 dark:bg-stone-900" style={{ ["--i" as string]: 1 }} data-testid="pdf-reader">
      <div className="flex flex-wrap items-center gap-2 border-b border-stone-100 px-3 py-2 text-xs dark:border-stone-800">
        <button type="button" onClick={onClose} className="inline-flex items-center gap-1 rounded-md px-1.5 py-1 text-stone-500 hover:bg-stone-100 dark:hover:bg-stone-800" title="Back to the list (Esc)"><X className="h-3.5 w-3.5" aria-hidden="true" />List</button>
        <span className="min-w-0 flex-1 truncate font-medium text-stone-700 dark:text-stone-100" title={title}>{title}</span>
        <span className="tabular-nums text-stone-400">{numPages ? `p. ${current} / ${numPages}` : "opening…"}</span>
        <form onSubmit={(e) => { e.preventDefault(); if (find === findInput.trim()) setHitIndex((i) => (hits.data?.length ? (i + 1) % hits.data.length : 0)); else setFind(findInput.trim()); }} className="relative inline-flex items-center" role="search" aria-label="Find in PDF">
          <Search className="pointer-events-none absolute left-1.5 h-3 w-3 text-stone-400" aria-hidden="true" />
          <input value={findInput} onChange={(e) => setFindInput(e.target.value)} placeholder="Find in PDF…" className="w-32 rounded-md border border-stone-200 bg-white py-1 pl-6 pr-1.5 text-xs placeholder:text-stone-400 focus:w-44 focus:border-indigo-400 focus:outline-none dark:border-stone-700 dark:bg-stone-800 dark:text-stone-200" onKeyDown={(e) => { if (e.key === "Escape") { setFindInput(""); setFind(""); (e.target as HTMLInputElement).blur(); } }} />
          {find && (
            <span className="ml-1 inline-flex items-center gap-0.5 tabular-nums text-stone-400">
              {hits.isLoading ? "…" : hits.data?.length ? `${hitIndex + 1}/${hits.data.length} pages` : "no hits"}
              {(hits.data?.length ?? 0) > 1 && (<>
                <button type="button" onClick={() => setHitIndex((i) => (i - 1 + hits.data!.length) % hits.data!.length)} className="rounded px-0.5 hover:bg-stone-100 dark:hover:bg-stone-800" aria-label="Previous page with a hit"><ChevronLeft className="h-3 w-3" aria-hidden="true" /></button>
                <button type="button" onClick={() => setHitIndex((i) => (i + 1) % hits.data!.length)} className="rounded px-0.5 hover:bg-stone-100 dark:hover:bg-stone-800" aria-label="Next page with a hit"><ChevronRight className="h-3 w-3" aria-hidden="true" /></button>
              </>)}
            </span>
          )}
        </form>
        <span className="inline-flex items-center overflow-hidden rounded-md border border-stone-200 dark:border-stone-700">
          <button type="button" onClick={() => setScale((s) => Math.max(0.6, +(s - 0.15).toFixed(2)))} className="px-1.5 py-1 text-stone-500 hover:bg-stone-100 dark:hover:bg-stone-800" aria-label="Zoom out"><Minus className="h-3 w-3" aria-hidden="true" /></button>
          <span className="px-1.5 tabular-nums text-stone-500">{Math.round(scale * 80)}%</span>
          <button type="button" onClick={() => setScale((s) => Math.min(2.5, +(s + 0.15).toFixed(2)))} className="px-1.5 py-1 text-stone-500 hover:bg-stone-100 dark:hover:bg-stone-800" aria-label="Zoom in"><Plus className="h-3 w-3" aria-hidden="true" /></button>
        </span>
        <label className="inline-flex items-center gap-1 text-stone-400" title="Project that receives new highlights">
          <Highlighter className="h-3 w-3" aria-hidden="true" />
          <span className="relative">
            <select value={project} onChange={(e) => onProject(e.target.value)} className="appearance-none rounded-md border border-stone-200 bg-white py-1 pl-2 pr-6 text-xs text-stone-600 dark:border-stone-700 dark:bg-stone-800 dark:text-stone-200" aria-label="Project that receives highlights">
              <option value="">library only</option>
              {projects.map((p) => <option key={p.slug} value={p.slug}>{p.name}</option>)}
            </select>
            <ChevronDown className="pointer-events-none absolute right-1.5 top-1/2 h-3 w-3 -translate-y-1/2 text-stone-400" aria-hidden="true" />
          </span>
        </label>
        <a href={fullReaderHref} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-stone-400 hover:text-indigo-600 dark:hover:text-indigo-300" title="Open the full-page reader with read-aloud"><ExternalLink className="h-3 w-3" aria-hidden="true" /><span className="hidden xl:inline">full reader</span></a>
      </div>
      <div ref={scroller} onMouseUp={onMouseUp} className="pdf-scroller relative flex-1 overflow-auto bg-stone-100 p-4 dark:bg-stone-950/60" style={{ maxHeight: "calc(100vh - 11rem)" }}>
        {error && <p className="rounded-lg bg-red-500/10 px-3 py-2 text-xs text-red-600 dark:text-red-300">{error}</p>}
        {!error && numPages === 0 && <p className="flex items-center gap-1.5 text-xs text-stone-400"><Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" />Rendering…</p>}
        <div className="mx-auto space-y-4">
          {Array.from({ length: numPages }, (_, i) => (
            <div key={i + 1} data-page={i + 1} className="pdf-page" style={{ width: `${612 * scale}px`, height: `${792 * scale}px` }} />
          ))}
        </div>
        {popover && (
          <div className="absolute z-20 -translate-x-1/2 -translate-y-full rounded-full border border-stone-200 bg-white px-1.5 py-1 shadow-lg dark:border-stone-700 dark:bg-stone-900" style={{ left: popover.x, top: popover.y }} role="toolbar" aria-label="Save highlight">
            <div className="flex items-center gap-1">
              {(Object.keys(HL_COLORS) as Highlight["color"][]).map((c) => (
                <button key={c} type="button" disabled={saving} onClick={() => void save(c)} className="h-5 w-5 rounded-full ring-offset-1 hover:ring-2 hover:ring-indigo-400 disabled:opacity-50" style={{ background: HL_COLORS[c] }} aria-label={`Highlight in ${c}`} title={`Highlight in ${c}`} />
              ))}
              <span className="ml-1 pr-1 text-[10px] text-stone-400">{saving ? "saving…" : `p.${popover.page}`}</span>
            </div>
          </div>
        )}
      </div>
    </section>
  );
}
