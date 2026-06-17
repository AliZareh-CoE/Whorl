/**
 * Reading-flow mode ([REV] cycle 75): a focused, keyboard-driven "read next"
 * session over the queue. One paper at a time — flashcards for papers.
 */
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, csrfToken, petReact } from "../api";

type Paper = {
  id: number;
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
  const queryClient = useQueryClient();
  const [i, setI] = useState(0);
  const [done, setDone] = useState<Set<number>>(new Set());
  const [noteOpen, setNoteOpen] = useState(false);
  const [noteText, setNoteText] = useState("");
  const [flash, setFlash] = useState("");
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [listening, setListening] = useState(false);
  const [tldr, setTldr] = useState<string[] | null>(null);

  const { data, isLoading } = useQuery({
    queryKey: ["reading-flow", slug],
    queryFn: () => api<{ papers: Paper[] }>(`/projects/${slug}/reading-flow/`),
  });
  const papers = data?.papers ?? [];
  const paper = papers[i];

  async function setStatus(status: string) {
    if (!paper) return;
    await api(`/project-references/${paper.id}/`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ reading_status: status }),
    });
    setFlash(`Marked ${STATUS_LABEL[status]}`);
    setTimeout(() => setFlash(""), 1200);
    queryClient.invalidateQueries({ queryKey: ["literature", slug] });
    if (status === "read" || status === "annotated") petReact("paper");
    if (status === "read" || status === "annotated") {
      setDone((d) => new Set(d).add(paper.id));
      next();
    }
  }
  function next() { setNoteOpen(false); setTldr(null); setI((x) => Math.min(x + 1, papers.length)); }
  function prev() { setNoteOpen(false); setTldr(null); setI((x) => Math.max(x - 1, 0)); }

  async function summarize() {
    if (!paper) return;
    if (tldr) { setTldr(null); return; }
    const res = await fetch("/summarize/", {
      method: "POST",
      headers: { "X-CSRFToken": csrfToken(), "X-SPA": "1" },
      body: new URLSearchParams({ text: paper.reference.abstract }),
    });
    setTldr((await res.json()).sentences ?? []);
  }

  async function listen() {
    if (listening) { audioRef.current?.pause(); setListening(false); return; }
    if (!paper) return;
    setListening(true);
    try {
      const res = await fetch("/tts/", {
        method: "POST",
        headers: { "X-CSRFToken": csrfToken() },
        body: new URLSearchParams({ text: `${paper.reference.title}. ${paper.reference.abstract}` }),
      });
      if (!res.ok) throw new Error();
      const audio = new Audio(URL.createObjectURL(await res.blob()));
      audioRef.current = audio;
      audio.onended = () => setListening(false);
      await audio.play();
    } catch { setListening(false); }
  }

  async function saveNote() {
    if (!paper || !noteText.trim()) { setNoteOpen(false); return; }
    await api("/quick-capture/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ text: `[${paper.reference.bibtex_key}] ${noteText}`, project: slug }),
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
      if (e.key === "Escape") { navigate(`/projects/${slug}/queue`); return; }
      if (STATUS_KEYS[e.key]) { e.preventDefault(); setStatus(STATUS_KEYS[e.key]); }
      else if (e.key === "n" || e.key === "ArrowRight") next();
      else if (e.key === "p" || e.key === "ArrowLeft") prev();
      else if (e.key === "j") { e.preventDefault(); setNoteOpen(true); }
      else if (e.key === "l") listen();
      else if (e.key === "s" && paper.reference.abstract) { e.preventDefault(); summarize(); }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  });

  if (isLoading) return <p className="p-8 text-sm text-stone-400">Loading your queue…</p>;

  if (!paper) {
    return (
      <div className="mx-auto max-w-lg px-4 pt-24 text-center">
        <p className="mb-3 text-4xl">📚</p>
        <h1 className="mb-2 text-2xl font-semibold tracking-tight text-stone-900">Your reading queue is empty</h1>
        <p className="mx-auto mb-8 max-w-sm text-sm leading-relaxed text-stone-500">
          {done.size > 0
            ? `You read ${done.size} paper${done.size > 1 ? "s" : ""} this session — nicely done. There's nothing left to work through here.`
            : "Nothing left to read in this project. Link new references to build the queue back up."}
        </p>
        <Link
          to={`/projects/${slug}/literature`}
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
        <span className="font-medium tracking-wide text-stone-500">
          <span className="text-stone-700">{i + 1}</span>
          <span className="text-stone-400"> of {papers.length}</span>
          <span className="ml-2 text-stone-400">· Reading flow</span>
        </span>
        <span className="flex items-center gap-3 text-stone-400">
          {flash && <span className="font-medium text-emerald-600">{flash}</span>}
          <Link to={`/projects/${slug}/queue`} className="transition-colors hover:text-stone-600">Esc to exit</Link>
        </span>
      </div>
      <div className="mb-6 h-1 w-full overflow-hidden rounded-full bg-stone-200">
        <div className="h-full rounded-full bg-indigo-600 transition-[width] duration-300" style={{ width: `${(i / papers.length) * 100}%` }} />
      </div>

      <article className="rounded border border-stone-200 bg-white p-6 sm:p-8">
        <div className="mb-3 flex flex-wrap items-center gap-1.5">
          {paper.priority === "high" && (
            <span className="rounded-full bg-rose-50 px-2 py-0.5 text-[11px] font-medium text-rose-700">High priority</span>
          )}
          <span className="rounded bg-stone-100 px-2 py-0.5 font-mono text-[11px] text-stone-500">{r.bibtex_key}</span>
          <span className="rounded-full bg-indigo-50 px-2 py-0.5 text-[11px] font-medium text-indigo-700">{STATUS_LABEL[paper.reading_status]}</span>
        </div>
        <h1 className="mb-1.5 text-2xl font-semibold leading-snug tracking-tight text-stone-900">{r.title}</h1>
        <p className="mb-5 text-sm text-stone-500">{authorLine(r.authors)}{r.year ? ` · ${r.year}` : ""}{r.venue ? ` · ${r.venue}` : ""}</p>
        <div className="mb-5 flex flex-wrap items-center gap-3 text-xs">
          <button
            onClick={listen}
            className="rounded border border-stone-300 bg-white px-2.5 py-1 font-medium text-stone-600 transition-colors hover:border-stone-400 hover:bg-stone-50"
          >
            {listening ? "⏸ Stop (l)" : "🔊 Listen (l)"}
          </button>
          <Link to={`/references/${r.id}`} className="font-medium text-indigo-600 transition-colors hover:text-indigo-700 hover:underline">Open reader ↗</Link>
          {r.doi && <a href={`https://doi.org/${r.doi}`} className="font-medium text-indigo-600 transition-colors hover:text-indigo-700 hover:underline">DOI ↗</a>}
        </div>
        {tldr && (
          <ul className="mb-4 list-disc space-y-1.5 rounded border border-stone-100 bg-stone-50 p-4 pl-8 text-sm leading-relaxed text-stone-600">
            {tldr.map((s, i) => <li key={i}>{s}</li>)}
          </ul>
        )}
        {r.abstract
          ? <p className="max-w-prose text-[15px] leading-7 text-stone-700">{r.abstract}</p>
          : <p className="text-sm italic text-stone-400">No abstract on file — open the reader for the PDF.</p>}
      </article>

      {noteOpen ? (
        <div className="mt-4 rounded border border-indigo-200 bg-white p-4 shadow-sm">
          <textarea autoFocus value={noteText} onChange={(e) => setNoteText(e.target.value)} rows={3}
                    placeholder={`Quick note on ${r.bibtex_key}… (Enter to save, Esc to cancel)`}
                    onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); saveNote(); } }}
                    className="w-full rounded border border-stone-300 bg-white p-2.5 text-sm leading-relaxed text-stone-700 placeholder:text-stone-400 focus:border-indigo-600 focus:outline-none focus:ring-1 focus:ring-indigo-600" />
          <div className="mt-2.5 flex items-center gap-3">
            <button onClick={saveNote} className="rounded bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-indigo-700">Save note</button>
            <button onClick={() => setNoteOpen(false)} className="text-xs text-stone-500 transition-colors hover:text-stone-700 hover:underline">Cancel</button>
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
          ? "border-indigo-200 bg-indigo-50 text-indigo-700"
          : "border-stone-200 bg-white text-stone-500 hover:border-stone-300"
      }`}
    >
      <kbd className={`rounded border px-1.5 py-0.5 font-mono text-[10px] ${
        accent ? "border-indigo-300 bg-white text-indigo-700" : "border-stone-300 bg-stone-50 text-stone-600"
      }`}>{k}</kbd>
      {label}
    </span>
  );
}
