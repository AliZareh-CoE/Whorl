/**
 * Reading-flow mode ([REV] cycle 75): a focused, keyboard-driven "read next"
 * session over the queue. One paper at a time — flashcards for papers.
 */
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useParams } from "react-router-dom";
import { api, csrfToken, petReact } from "../api";
import { listenTo, type Listener } from "../listen";
import { Skeleton, SkeletonLines } from "../../components/Skeleton";
import { queryGate } from "../../components/QueryBoundary";

type Paper = {
  id: number | null; // #450: null when the paper sits in no project yet (library mode)
  project?: string | null;
  reading_status: string;
  priority: string;
  reference: {
    id: number;
    bibtex_key: string;
    title: string;
    authors: { family?: string; given?: string }[];
    year: number | null;
    venue: string;
    abstract: string;
    pdf: string | null;
    doi: string;
  };
  progress?: { page: number | null; pages: number | null; percent: number | null } | null; // #524
};

const STATUS_KEYS: Record<string, string> = { "1": "to_read", "2": "skimmed", "3": "read", "4": "annotated" };
const STATUS_LABEL: Record<string, string> = { to_read: "To read", skimmed: "Skimmed", read: "Read", annotated: "Annotated" };

function authorLine(a: Paper["reference"]["authors"]): string {
  const names = (a ?? []).map((x) => x.family ?? x.given ?? "").filter(Boolean);
  return names.length > 4 ? `${names.slice(0, 4).join(", ")} et al.` : names.join(", ");
}

export default function ReadingFlow() {
  const { slug } = useParams();
  const navigate = useNavigate();
  // #450: /library/read?<filters> runs the same flow over any Library view
  const libraryMode = !slug;
  const search = useLocation().search;
  const queryClient = useQueryClient();
  const [i, setI] = useState(0);
  const [done, setDone] = useState<Set<number>>(new Set());
  const [noteOpen, setNoteOpen] = useState(false);
  const [noteText, setNoteText] = useState("");
  const [flash, setFlash] = useState("");
  const listenerRef = useRef<Listener | null>(null);
  const [listening, setListening] = useState(false);
  // tl;dr (#395): section-by-section from the PDF text when it is indexed, else the abstract
  const [tldr, setTldr] = useState<{ title: string; page: number | null; sentences: string[] }[] | null>(null);

  const flow = useQuery({
    queryKey: ["reading-flow", slug ?? "library", search],
    queryFn: () => api<{ papers: Paper[] }>(libraryMode ? `/references/reading-flow/${search}` : `/projects/${slug}/reading-flow/`),
  });
  const data = flow.data;
  const papers = data?.papers ?? [];
  const paper = papers[i];

  async function setStatus(status: string) {
    if (!paper) return;
    if (paper.id === null) { setFlash("This paper is in no project yet — file it from the Library first."); setTimeout(() => setFlash(""), 2500); return; }
    await api(`/project-references/${paper.id}/`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reading_status: status }),
    });
    setFlash(`Marked ${STATUS_LABEL[status]}`);
    setTimeout(() => setFlash(""), 1200);
    queryClient.invalidateQueries({ queryKey: ["literature", slug ?? paper.project] });
    queryClient.invalidateQueries({ queryKey: ["references"] });
    if (status === "read" || status === "annotated") petReact("paper");
    if (status === "read" || status === "annotated") {
      setDone((d) => new Set(d).add(paper.id as number));
      next();
    }
  }
  function next() { setNoteOpen(false); setTldr(null); setI((x) => Math.min(x + 1, papers.length)); }
  function prev() { setNoteOpen(false); setTldr(null); setI((x) => Math.max(x - 1, 0)); }

  async function summarize() {
    if (!paper) return;
    if (tldr) { setTldr(null); return; }
    try {
      const out = await api<{ source: string; sections: { title: string; page: number | null; sentences: string[] }[]; reason?: string }>(`/references/${paper.reference.id}/tldr/`);
      setTldr(out.sections.length ? out.sections : [{ title: "Nothing to summarise", page: null, sentences: [out.reason ?? "No abstract and no PDF text on file."] }]);
    } catch {
      setFlash("Couldn't summarise this paper.");
    }
  }

  async function listen() {
    if (listening) { listenerRef.current?.stop(); listenerRef.current = null; setListening(false); return; }
    if (!paper) return;
    setListening(true);
    // #404: chunked, prefetched — the abstract starts within a sentence and reads without gaps
    const l = listenTo(`${paper.reference.title}. ${paper.reference.abstract}`);
    listenerRef.current = l;
    try { await l.done; } catch (e) { setFlash(String((e as Error).message ?? "Read-aloud unavailable.")); }
    finally { if (listenerRef.current === l) { listenerRef.current = null; setListening(false); } }
  }

  async function saveNote() {
    if (!paper || !noteText.trim()) { setNoteOpen(false); return; }
    await api("/quick-capture/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: `[${paper.reference.bibtex_key}] ${noteText}`, project: slug ?? paper.project ?? null }),
    });
    setNoteText(""); setNoteOpen(false);
    setFlash("Note captured");
    setTimeout(() => setFlash(""), 1200);
  }

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (noteOpen) {
        if (e.key === "Escape") setNoteOpen(false);
        return;
      }
      if (e.key === "Escape") { if (libraryMode) navigate("/library"); else navigate(`/projects/${slug}/queue`); return; }
      if (STATUS_KEYS[e.key]) { e.preventDefault(); setStatus(STATUS_KEYS[e.key]); }
      else if (e.key === "n" || e.key === "ArrowRight") next();
      else if (e.key === "p" || e.key === "ArrowLeft") prev();
      else if (e.key === "j") { e.preventDefault(); setNoteOpen(true); }
      else if (e.key === "l") listen();
      else if (e.key === "s") { e.preventDefault(); summarize(); }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  });

  // #409: skeleton while loading, ErrorState with retry when the fetch fails
  const gate = queryGate(flow, {
    message: "Couldn't load the reading flow.",
    skeleton: (
      <div role="status" aria-label="Loading" className="mx-auto max-w-3xl px-4">
        <div className="mb-3 flex items-center justify-between">
          <Skeleton className="h-3 w-32" />
          <Skeleton className="h-3 w-20" />
        </div>
        <Skeleton className="mb-6 h-1 w-full rounded-full" />
        <article className="rounded border border-stone-200 bg-white p-6 sm:p-8 dark:border-stone-800 dark:bg-stone-900">
          <Skeleton className="mb-3 h-4 w-40" />
          <Skeleton className="mb-2 h-7 w-3/4" />
          <Skeleton className="mb-5 h-4 w-1/2" />
          <SkeletonLines lines={5} />
        </article>
      </div>
    ),
  });
  if (gate) return gate;

  if (!paper) {
    return (
      <div className="mx-auto max-w-lg px-4 pt-24 text-center">
        <p className="mb-3 text-4xl">📚</p>
        <h1 className="mb-2 text-2xl font-semibold tracking-tight text-stone-900 dark:text-stone-100">Your reading queue is empty</h1>
        <p className="mx-auto mb-8 max-w-sm text-sm leading-relaxed text-stone-500 dark:text-stone-400">
          {done.size > 0
            ? `You read ${done.size} paper${done.size > 1 ? "s" : ""} this session — nicely done. There's nothing left to work through here.`
            : "Nothing left to read in this project. Link new references to build the queue back up."}
        </p>
        <Link
          to={libraryMode ? "/library" : `/projects/${slug}/literature`}
          className="inline-flex items-center gap-1.5 rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
        >
          Back to literature
        </Link>
      </div>
    );
  }

  const r = paper.reference;
  return (
    <div className="mx-auto max-w-3xl px-4">
      <div className="mb-3 flex items-center justify-between text-xs">
        <span className="font-medium tracking-wide text-stone-500 dark:text-stone-400">
          <span className="text-stone-700 dark:text-stone-300">{i + 1}</span>
          <span className="text-stone-400"> of {papers.length}</span>
          <span className="ml-2 text-stone-400">· Reading flow</span>
        </span>
        <span className="flex items-center gap-3 text-stone-400">
          {flash && <span className="font-medium text-emerald-600">{flash}</span>}
          <Link to={libraryMode ? "/library" : `/projects/${slug}/queue`} className="transition-colors hover:text-stone-600 dark:hover:text-stone-300">Esc to exit</Link>
        </span>
      </div>
      <div className="mb-6 h-1 w-full overflow-hidden rounded-full bg-stone-200 dark:bg-stone-800">
        <div className="h-full rounded-full bg-indigo-600 transition-[width] duration-300" style={{ width: `${(i / papers.length) * 100}%` }} />
      </div>

      <article className="rounded border border-stone-200 bg-white p-6 sm:p-8 dark:border-stone-800 dark:bg-stone-900">
        <div className="mb-3 flex flex-wrap items-center gap-1.5">
          {paper.priority === "high" && (
            <span className="rounded-full bg-rose-50 px-2 py-0.5 text-[11px] font-medium text-rose-700">High priority</span>
          )}
          <span className="rounded bg-stone-100 px-2 py-0.5 font-mono text-[11px] text-stone-500 dark:bg-stone-800 dark:text-stone-400">{r.bibtex_key}</span>
          <span className="rounded-full bg-indigo-50 px-2 py-0.5 text-[11px] font-medium text-indigo-700 dark:bg-indigo-500/15 dark:text-indigo-300">{STATUS_LABEL[paper.reading_status]}</span>
          {paper.progress?.page != null && paper.progress.page > 1 && (
            <span className="inline-flex items-center gap-1.5 rounded-full bg-stone-100 px-2 py-0.5 text-[11px] font-medium text-stone-600 dark:bg-stone-800 dark:text-stone-300" title="Where the reader left off" data-testid="flow-progress">
              <span className="inline-block h-1 w-10 overflow-hidden rounded-full bg-stone-300 dark:bg-stone-700" aria-hidden="true"><span className="block h-full rounded-full bg-indigo-500" style={{ width: `${paper.progress.percent ?? 0}%` }} /></span>
              p. {paper.progress.page}{paper.progress.pages ? ` of ${paper.progress.pages}` : ""}
            </span>
          )}
        </div>
        <h1 className="mb-1.5 text-2xl font-semibold leading-snug tracking-tight text-stone-900 dark:text-stone-100">{r.title}</h1>
        <p className="mb-5 text-sm text-stone-500 dark:text-stone-400">{authorLine(r.authors)}{r.year ? ` · ${r.year}` : ""}{r.venue ? ` · ${r.venue}` : ""}</p>
        <div className="mb-5 flex flex-wrap items-center gap-3 text-xs">
          <button
            onClick={listen}
            className="rounded border border-stone-300 bg-white px-2.5 py-1 font-medium text-stone-600 transition-colors hover:border-stone-400 hover:bg-stone-50 dark:border-stone-700 dark:bg-stone-800 dark:text-stone-300 dark:hover:border-stone-600 dark:hover:bg-stone-800"
          >
            {listening ? "⏸ Stop (l)" : "🔊 Listen (l)"}
          </button>
          <Link to={`/references/${r.id}`} className="font-medium text-indigo-600 transition-colors hover:text-indigo-700 hover:underline dark:text-indigo-400 dark:hover:text-indigo-300">Open reader ↗</Link>
          {r.doi && <a href={`https://doi.org/${r.doi}`} className="font-medium text-indigo-600 transition-colors hover:text-indigo-700 hover:underline dark:text-indigo-400 dark:hover:text-indigo-300">DOI ↗</a>}
        </div>
        {tldr && (
          <ol className="mb-4 space-y-2 rounded border border-stone-100 bg-stone-50 p-4 text-sm leading-relaxed text-stone-600 dark:border-stone-800 dark:bg-stone-800 dark:text-stone-300" data-testid="flow-tldr">
            {tldr.map((s, i) => (
              <li key={i}>
                <span className="font-medium text-stone-800 dark:text-stone-100">{s.title}</span>
                {s.page && <span className="ml-1.5 rounded-full bg-stone-200 px-1.5 py-0.5 text-[10px] text-stone-500 dark:bg-stone-700 dark:text-stone-300">p.{s.page}</span>}
                <span className="ml-1 text-stone-400">·</span> {s.sentences.join(" ")}
              </li>
            ))}
          </ol>
        )}
        {r.abstract
          ? <p className="max-w-prose text-[15px] leading-7 text-stone-700 dark:text-stone-300">{r.abstract}</p>
          : <p className="text-sm italic text-stone-400">No abstract on file — open the reader for the PDF.</p>}
      </article>

      {noteOpen ? (
        <div className="mt-4 rounded border border-indigo-200 bg-white p-4 shadow-sm dark:border-indigo-500/30 dark:bg-stone-900">
          <textarea autoFocus value={noteText} onChange={(e) => setNoteText(e.target.value)} rows={3}
                    placeholder={`Quick note on ${r.bibtex_key}… (Enter to save, Esc to cancel)`}
                    onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); saveNote(); } }}
                    className="w-full rounded border border-stone-300 bg-white p-2.5 text-sm leading-relaxed text-stone-700 placeholder:text-stone-400 focus:border-indigo-600 focus:outline-none focus:ring-1 focus:ring-indigo-600 dark:border-stone-700 dark:bg-stone-800 dark:text-stone-300" />
          <div className="mt-2.5 flex items-center gap-3">
            <button onClick={saveNote} className="rounded bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-indigo-700">Save note</button>
            <button onClick={() => setNoteOpen(false)} className="text-xs text-stone-500 transition-colors hover:text-stone-700 hover:underline dark:text-stone-400 dark:hover:text-stone-300">Cancel</button>
          </div>
        </div>
      ) : (
        <div className="mt-5 space-y-3 text-center">
          <div className="flex flex-wrap items-center justify-center gap-1.5">
            <Key k="1" label="To read" /><Key k="2" label="Skimmed" /><Key k="3" label="Read →" accent /><Key k="4" label="Annotated →" accent />
          </div>
          <div className="flex flex-wrap items-center justify-center gap-1.5">
            <Key k="n" label="Next" /><Key k="p" label="Prev" /><Key k="j" label="Note" /><Key k="l" label="Listen" /><Key k="s" label="tl;dr" />
          </div>
        </div>
      )}
    </div>
  );
}

function Key({ k, label, accent = false }: { k: string; label: string; accent?: boolean }) {
  return (
    <span
      className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-xs transition-colors ${
        accent
          ? "border-indigo-200 bg-indigo-50 text-indigo-700 dark:border-indigo-500/30 dark:bg-indigo-500/15 dark:text-indigo-300"
          : "border-stone-200 bg-white text-stone-500 hover:border-stone-300 dark:border-stone-800 dark:bg-stone-900 dark:text-stone-400 dark:hover:border-stone-700"
      }`}
    >
      <kbd className={`rounded border px-1.5 py-0.5 font-mono text-[10px] ${
        accent ? "border-indigo-300 bg-white text-indigo-700 dark:border-indigo-500/40 dark:bg-stone-900 dark:text-indigo-300" : "border-stone-300 bg-stone-50 text-stone-600 dark:border-stone-700 dark:bg-stone-800 dark:text-stone-300"
      }`}>{k}</kbd>
      {label}
    </span>
  );
}
