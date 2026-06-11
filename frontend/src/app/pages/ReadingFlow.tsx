/**
 * Reading-flow mode ([REV] cycle 75): a focused, keyboard-driven "read next"
 * session over the queue. One paper at a time — flashcards for papers.
 */
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api, csrfToken } from "../api";

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
      <div className="mx-auto max-w-lg pt-24 text-center">
        <p className="mb-2 text-4xl">📚</p>
        <h1 className="mb-2 text-2xl font-semibold tracking-tight">Queue cleared</h1>
        <p className="mb-6 text-sm text-stone-500">
          {done.size > 0 ? `You read ${done.size} paper${done.size > 1 ? "s" : ""} this session.` : "Nothing left to read here."}
        </p>
        <Link to={`/projects/${slug}/literature`} className="text-sm font-medium text-indigo-600 hover:underline">
          Back to literature
        </Link>
      </div>
    );
  }

  const r = paper.reference;
  return (
    <div className="mx-auto max-w-3xl">
      <div className="mb-4 flex items-center justify-between text-xs text-stone-400">
        <span>{i + 1} of {papers.length} · reading flow</span>
        <span className="flex items-center gap-3">
          {flash && <span className="text-green-600">{flash}</span>}
          <Link to={`/projects/${slug}/queue`} className="hover:text-stone-600">Esc to exit</Link>
        </span>
      </div>
      <div className="mb-3 h-1 w-full rounded-full bg-stone-100">
        <div className="h-1 rounded-full bg-indigo-500 transition-[width]" style={{ width: `${(i / papers.length) * 100}%` }} />
      </div>

      <article className="rounded-lg border border-stone-200 bg-white p-8">
        <div className="mb-2 flex items-center gap-2">
          <span className={`rounded px-2 py-0.5 text-xs ${paper.priority === "high" ? "bg-red-50 text-red-700" : "bg-stone-100 text-stone-500"}`}>{paper.priority}</span>
          <span className="rounded bg-stone-100 px-2 py-0.5 font-mono text-xs text-stone-500">{r.bibtex_key}</span>
          <span className="rounded bg-indigo-50 px-2 py-0.5 text-xs text-indigo-700">{STATUS_LABEL[paper.reading_status]}</span>
        </div>
        <h1 className="mb-1 text-xl font-semibold tracking-tight">{r.title}</h1>
        <p className="mb-4 text-sm text-stone-500">{authorLine(r.authors)}{r.year ? ` · ${r.year}` : ""}{r.venue ? ` · ${r.venue}` : ""}</p>
        <div className="mb-4 flex items-center gap-3 text-xs">
          <button onClick={listen} className="rounded border border-stone-300 bg-white px-2 py-1 hover:border-stone-400">
            {listening ? "⏸ Stop (l)" : "🔊 Listen (l)"}
          </button>
          <Link to={`/references/${r.id}`} className="text-indigo-600 hover:underline">Open reader ↗</Link>
          {r.doi && <a href={`https://doi.org/${r.doi}`} className="text-indigo-600 hover:underline">DOI ↗</a>}
        </div>
        {tldr && (
          <ul className="mb-3 list-disc space-y-1 rounded bg-stone-50 p-3 pl-7 text-sm text-stone-600">
            {tldr.map((s, i) => <li key={i}>{s}</li>)}
          </ul>
        )}
        {r.abstract
          ? <p className="text-sm leading-relaxed text-stone-700">{r.abstract}</p>
          : <p className="text-sm italic text-stone-400">No abstract on file — open the reader for the PDF.</p>}
      </article>

      {noteOpen ? (
        <div className="mt-4 rounded-lg border border-indigo-200 bg-white p-4">
          <textarea autoFocus value={noteText} onChange={(e) => setNoteText(e.target.value)} rows={3}
                    placeholder={`Quick note on ${r.bibtex_key}… (Enter to save, Esc to cancel)`}
                    onKeyDown={(e) => { if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); saveNote(); } }}
                    className="w-full rounded border border-stone-300 bg-white p-2 text-sm focus:border-indigo-600 focus:outline-none" />
          <div className="mt-2 flex gap-2">
            <button onClick={saveNote} className="rounded bg-indigo-600 px-3 py-1 text-xs font-medium text-white hover:bg-indigo-700">Save note</button>
            <button onClick={() => setNoteOpen(false)} className="text-xs text-stone-500 hover:underline">Cancel</button>
          </div>
        </div>
      ) : (
        <div className="mt-4 flex flex-wrap items-center justify-center gap-2 text-xs text-stone-500">
          <Key k="1" label="To read" /><Key k="2" label="Skimmed" /><Key k="3" label="Read →" /><Key k="4" label="Annotated →" />
          <span className="mx-1 text-stone-300">|</span>
          <Key k="n" label="Next" /><Key k="p" label="Prev" /><Key k="j" label="Note" /><Key k="l" label="Listen" /><Key k="s" label="tl;dr" />
        </div>
      )}
    </div>
  );
}

function Key({ k, label }: { k: string; label: string }) {
  return (
    <span className="inline-flex items-center gap-1">
      <kbd className="rounded border border-stone-300 bg-stone-50 px-1.5 py-0.5 font-mono text-[10px] text-stone-600">{k}</kbd>
      {label}
    </span>
  );
}
