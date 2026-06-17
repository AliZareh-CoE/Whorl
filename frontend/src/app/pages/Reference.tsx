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

  if (isLoading || !ref) return <p className="text-sm text-stone-400 dark:text-stone-400">Loading reference…</p>;

  return (
    <div className="max-w-3xl">
      <nav className="mb-6 text-sm text-stone-500 dark:text-stone-400">
        <Link to="/library" className="hover:text-indigo-700 hover:underline dark:hover:text-indigo-300">Library</Link>
        <span className="px-1.5 text-stone-300 dark:text-stone-400">/</span>
        <span className="font-mono text-xs text-stone-400 dark:text-stone-400">{ref.bibtex_key}</span>
      </nav>

      <section className="mb-4 rounded border border-stone-200 bg-white p-6 dark:border-stone-800 dark:bg-stone-900">
        <h1 className="text-2xl font-semibold leading-snug tracking-tight text-stone-900 dark:text-stone-100">{ref.title}</h1>
        {authorLine(ref) && (
          <p className="mt-2 text-sm leading-relaxed text-stone-600 dark:text-stone-300">{authorLine(ref)}</p>
        )}
        <p className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-stone-400 dark:text-stone-400">
          {ref.year && <span>{ref.year}</span>}
          {ref.venue && <><span aria-hidden="true">·</span><span className="italic text-stone-500 dark:text-stone-400">{ref.venue}</span></>}
          {ref.citation_count != null && (
            <><span aria-hidden="true">·</span><span>{ref.citation_count} citation{ref.citation_count === 1 ? "" : "s"}</span></>
          )}
        </p>

        <div className="mt-4 flex flex-wrap items-center gap-x-4 gap-y-2 border-t border-stone-100 pt-4 text-sm dark:border-stone-800">
          {ref.doi && (
            <a href={`https://doi.org/${ref.doi}`}
               className="text-indigo-600 hover:text-indigo-700 hover:underline focus:outline-none focus-visible:underline dark:text-indigo-400 dark:hover:text-indigo-300">DOI ↗</a>
          )}
          {ref.url && (
            <a href={ref.url}
               className="text-indigo-600 hover:text-indigo-700 hover:underline focus:outline-none focus-visible:underline dark:text-indigo-400 dark:hover:text-indigo-300">Link ↗</a>
          )}
          {ref.pdf && (
            <a href={ref.pdf}
               className="text-indigo-600 hover:text-indigo-700 hover:underline focus:outline-none focus-visible:underline dark:text-indigo-400 dark:hover:text-indigo-300">PDF ↗</a>
          )}
          <a href={`/library/${ref.id}/`}
             className="ml-auto text-xs text-stone-400 hover:text-stone-600 hover:underline focus:outline-none focus-visible:underline dark:text-stone-400 dark:hover:text-stone-300">
            edit / annotate (classic) ↗
          </a>
        </div>
      </section>

      {ref.abstract && (
        <section className="mb-4 rounded border border-stone-200 bg-white p-6 dark:border-stone-800 dark:bg-stone-900">
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <h2 className="text-sm font-medium uppercase tracking-wide text-stone-400 dark:text-stone-400">Abstract</h2>
            <div className="flex items-center gap-2">
              <button onClick={() => listen(`${ref.title}. ${ref.abstract}`)}
                      className="rounded border border-stone-300 bg-white px-2 py-0.5 text-xs text-stone-600 hover:border-stone-400 hover:text-stone-800 focus:outline-none focus-visible:border-indigo-600 dark:border-stone-700 dark:bg-stone-800 dark:text-stone-300">
                {listening ? "⏸ Stop" : "🔊 Listen"}
              </button>
              <button onClick={() => summarize(ref.abstract)} disabled={summarizing}
                      className="rounded border border-stone-300 bg-white px-2 py-0.5 text-xs text-stone-600 hover:border-stone-400 hover:text-stone-800 focus:outline-none focus-visible:border-indigo-600 disabled:opacity-50 dark:border-stone-700 dark:bg-stone-800 dark:text-stone-300">
                {summarizing ? "…" : tldr ? "Hide tl;dr" : "≡ tl;dr"}
              </button>
            </div>
            {ttsError && <span className="text-xs text-red-600 dark:text-red-300">{ttsError}</span>}
          </div>
          {tldr && (
            <ul className="mb-4 list-disc space-y-1 rounded bg-stone-50 p-3 pl-7 text-sm leading-relaxed text-stone-600 dark:bg-stone-800 dark:text-stone-300">
              {tldr.map((s, i) => <li key={i}>{s}</li>)}
            </ul>
          )}
          <p className="max-w-prose text-[15px] leading-7 text-stone-700 dark:text-stone-300">{ref.abstract}</p>
        </section>
      )}

      {ref.pdf && (
        <section className="mb-4 rounded border border-stone-200 bg-white p-2 dark:border-stone-800 dark:bg-stone-900">
          <iframe src={ref.pdf} title="PDF" className="h-[70vh] w-full rounded" />
        </section>
      )}

      <section className="rounded border border-stone-200 bg-white p-6 dark:border-stone-800 dark:bg-stone-900">
        <h2 className="mb-3 flex items-baseline gap-2 text-sm font-medium uppercase tracking-wide text-stone-400 dark:text-stone-400">
          Comments {commentData && commentData.comments.length > 0 && <span className="text-stone-300 dark:text-stone-400">{commentData.comments.length}</span>}
        </h2>
        {commentData && commentData.comments.length > 0 ? (
          <ul className="mb-4 space-y-3">
            {commentData.comments.map((c) => (
              <li key={c.id} className="border-l-2 border-stone-200 pl-3 text-sm dark:border-stone-800">
                <p className="whitespace-pre-wrap text-stone-700 dark:text-stone-300">{c.body}</p>
                <p className="mt-0.5 text-xs text-stone-400 dark:text-stone-400">{c.created_at.slice(0, 16).replace("T", " ")}</p>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mb-3 text-sm text-stone-400 dark:text-stone-400">No comments yet — thoughts, caveats, todos about this paper.</p>
        )}
        <form className="flex items-start gap-2"
              onSubmit={(e) => { e.preventDefault(); if (commentBody.trim()) addComment.mutate(); }}>
          <textarea value={commentBody} onChange={(e) => setCommentBody(e.target.value)} rows={2}
                    placeholder="Add a comment…" aria-label="Add comment"
                    className="flex-1 rounded border border-stone-300 bg-white px-3 py-2 text-sm placeholder:text-stone-400 focus:border-indigo-600 focus:outline-none focus:ring-1 focus:ring-indigo-600 dark:border-stone-700 dark:bg-stone-800 dark:text-stone-100" />
          <button type="submit" disabled={addComment.isPending || !commentBody.trim()}
                  className="rounded bg-indigo-600 px-3 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50">
            Comment
          </button>
        </form>
      </section>
    </div>
  );
}
