/** Reference reader: metadata, abstract with Listen (TTS), PDF, status (SPA, cycle 74). */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, csrfToken } from "../api";

type Ref = {
  id: number;
  bibtex_key: string;
  title: string;
  authors: { family?: string; given?: string }[];
  year: number | null;
  venue: string;
  abstract: string;
  doi: string;
  url: string;
  pdf: string | null;
  citation_count: number | null;
};

function authorLine(r: Ref): string {
  const names = (r.authors ?? []).map((a) => [a.given, a.family].filter(Boolean).join(" ")).filter(Boolean);
  return names.join(", ");
}

export default function Reference() {
  const { id } = useParams();
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [listening, setListening] = useState(false);
  const [ttsError, setTtsError] = useState("");
  const [tldr, setTldr] = useState<string[] | null>(null);
  const [summarizing, setSummarizing] = useState(false);

  const queryClient = useQueryClient();
  const { data: ref, isLoading } = useQuery({
    queryKey: ["reference", id],
    queryFn: () => api<Ref>(`/references/${id}/`),
  });
  const { data: commentData } = useQuery({
    queryKey: ["comments", "reference", id],
    queryFn: () => api<{ comments: { id: number; body: string; created_at: string }[] }>(`/comments/reference/${id}/`),
  });
  const [commentBody, setCommentBody] = useState("");
  const addComment = useMutation({
    mutationFn: () =>
      api(`/comments/reference/${id}/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ body: commentBody }),
      }),
    onSuccess: () => {
      setCommentBody("");
      queryClient.invalidateQueries({ queryKey: ["comments", "reference", id] });
    },
  });

  async function listen(text: string) {
    if (listening) {
      audioRef.current?.pause();
      setListening(false);
      return;
    }
    setTtsError("");
    setListening(true);
    try {
      const body = new URLSearchParams({ text });
      const res = await fetch("/tts/", {
        method: "POST",
        headers: { "X-CSRFToken": csrfToken() },
        body,
      });
      if (!res.ok) throw new Error((await res.json()).error ?? "Read-aloud unavailable.");
      const blob = await res.blob();
      const audio = new Audio(URL.createObjectURL(blob));
      audioRef.current = audio;
      audio.onended = () => setListening(false);
      await audio.play();
    } catch (e) {
      setTtsError(String((e as Error).message ?? e));
      setListening(false);
    }
  }

  async function summarize(text: string) {
    if (tldr) { setTldr(null); return; }
    setSummarizing(true);
    try {
      const res = await fetch("/summarize/", {
        method: "POST",
        headers: { "X-CSRFToken": csrfToken(), "X-SPA": "1" },
        body: new URLSearchParams({ text }),
      });
      setTldr((await res.json()).sentences ?? []);
    } finally {
      setSummarizing(false);
    }
  }

  if (isLoading || !ref) return <p className="text-sm text-stone-400">Loading reference…</p>;

  return (
    <div>
      <nav className="mb-6 text-sm text-stone-500">
        <Link to="/library" className="hover:underline">Library</Link> / {ref.bibtex_key}
      </nav>
      <h1 className="mb-1 text-2xl font-semibold tracking-tight">{ref.title}</h1>
      <p className="mb-4 text-sm text-stone-500">
        {authorLine(ref)}{ref.year ? ` · ${ref.year}` : ""}{ref.venue ? ` · ${ref.venue}` : ""}
        {ref.citation_count != null ? ` · ${ref.citation_count} citations` : ""}
      </p>

      <div className="mb-4 flex flex-wrap items-center gap-2 text-sm">
        <span className="rounded bg-stone-100 px-2 py-0.5 font-mono text-xs text-stone-500">{ref.bibtex_key}</span>
        {ref.doi && <a href={`https://doi.org/${ref.doi}`} className="text-indigo-600 hover:underline">DOI ↗</a>}
        {ref.url && <a href={ref.url} className="text-indigo-600 hover:underline">Link ↗</a>}
        {ref.pdf && <a href={ref.pdf} className="text-indigo-600 hover:underline">PDF ↗</a>}
        <a href={`/library/${ref.id}/`} className="text-stone-400 underline hover:text-indigo-700">edit / annotate (classic) ↗</a>
      </div>

      {ref.abstract && (
        <section className="mb-4 rounded border border-stone-200 bg-white p-5">
          <div className="mb-2 flex items-center gap-2">
            <h2 className="text-sm font-medium uppercase tracking-wide text-stone-400">Abstract</h2>
            <button onClick={() => listen(`${ref.title}. ${ref.abstract}`)}
                    className="rounded border border-stone-300 bg-white px-2 py-0.5 text-xs hover:border-stone-400">
              {listening ? "⏸ Stop" : "🔊 Listen"}
            </button>
            <button onClick={() => summarize(ref.abstract)} disabled={summarizing}
                    className="rounded border border-stone-300 bg-white px-2 py-0.5 text-xs hover:border-stone-400 disabled:opacity-50">
              {summarizing ? "…" : tldr ? "Hide tl;dr" : "≡ tl;dr"}
            </button>
            {ttsError && <span className="text-xs text-red-600">{ttsError}</span>}
          </div>
          {tldr && (
            <ul className="mb-3 list-disc space-y-1 rounded bg-stone-50 p-3 pl-7 text-sm text-stone-600">
              {tldr.map((s, i) => <li key={i}>{s}</li>)}
            </ul>
          )}
          <p className="text-sm leading-relaxed text-stone-700">{ref.abstract}</p>
        </section>
      )}

      {ref.pdf && (
        <section className="mb-4 rounded border border-stone-200 bg-white p-2">
          <iframe src={ref.pdf} title="PDF" className="h-[70vh] w-full rounded" />
        </section>
      )}

      <section className="rounded border border-stone-200 bg-white p-5">
        <h2 className="mb-3 text-sm font-medium uppercase tracking-wide text-stone-400">
          Comments {commentData && commentData.comments.length > 0 && <span className="text-stone-300">{commentData.comments.length}</span>}
        </h2>
        {commentData && commentData.comments.length > 0 ? (
          <ul className="mb-4 space-y-3">
            {commentData.comments.map((c) => (
              <li key={c.id} className="border-l-2 border-stone-200 pl-3 text-sm">
                <p className="whitespace-pre-wrap text-stone-700">{c.body}</p>
                <p className="mt-0.5 text-xs text-stone-400">{c.created_at.slice(0, 16).replace("T", " ")}</p>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mb-3 text-sm text-stone-400">No comments yet — thoughts, caveats, todos about this paper.</p>
        )}
        <form className="flex items-start gap-2"
              onSubmit={(e) => { e.preventDefault(); if (commentBody.trim()) addComment.mutate(); }}>
          <textarea value={commentBody} onChange={(e) => setCommentBody(e.target.value)} rows={2}
                    placeholder="Add a comment…" aria-label="Add comment"
                    className="flex-1 rounded border border-stone-300 bg-white px-3 py-2 text-sm focus:border-indigo-600 focus:outline-none" />
          <button type="submit" disabled={addComment.isPending || !commentBody.trim()}
                  className="rounded bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50">
            Comment
          </button>
        </form>
      </section>
    </div>
  );
}
