/** Reference reader: metadata, abstract with Listen (TTS), PDF, status (SPA, cycle 74). */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useRef, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Pencil, Trash2 } from "lucide-react";
import { listenTo, type Listener } from "../listen";
import { api, csrfToken } from "../api";
import { Skeleton, SkeletonLines } from "../../components/Skeleton";
import { confirmDialog, errorDialog } from "../../components/Dialog";
import { Kebab } from "../../components/Menu";

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
  projects?: { slug: string; name: string; color: string; reading_status: string }[];
  tags?: string[];
};
type Highlight = { id: number; page: number | null; text: string; comment: string; color: string; project_name: string };
type Citation = { style: string; label: string; text: string; html: string; intext: string };

function authorLine(r: Ref): string {
  const names = (r.authors ?? []).map((a) => [a.given, a.family].filter(Boolean).join(" ")).filter(Boolean);
  return names.join(", ");
}
/** One author per line, "Family, Given" — the editable form of the JSON author list. */
function authorsToText(a: Ref["authors"]): string { return (a ?? []).map((x) => (x.given ? `${x.family ?? ""}, ${x.given}` : x.family ?? "")).join("\n"); }
function textToAuthors(t: string): Ref["authors"] {
  return t.split("\n").map((l) => l.trim()).filter(Boolean).map((l) => {
    if (l.includes(",")) { const [family, ...rest] = l.split(","); return { family: family.trim(), given: rest.join(",").trim() }; }
    const parts = l.split(/\s+/); return parts.length > 1 ? { family: parts[parts.length - 1], given: parts.slice(0, -1).join(" ") } : { family: l };
  });
}
const field = "w-full rounded border border-stone-300 bg-white px-3 py-1.5 text-sm text-stone-800 focus:border-indigo-600 focus:outline-none focus:ring-1 focus:ring-indigo-600 dark:border-stone-700 dark:bg-stone-800 dark:text-stone-100";

/** CRUD sweep 2026-09-06: every metadata field is editable in place; delete removes the
 * paper from the library (and every project) after a confirm. */
function EditReference({ r, onClose }: { r: Ref; onClose: () => void }) {
  const queryClient = useQueryClient();
  const [form, setForm] = useState({ title: r.title, authors: authorsToText(r.authors), year: r.year ? String(r.year) : "", venue: r.venue, doi: r.doi ?? "", url: r.url ?? "", abstract: r.abstract });
  const set = (k: keyof typeof form) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) => setForm((f) => ({ ...f, [k]: e.target.value }));
  const save = useMutation({
    mutationFn: () => api(`/references/${r.id}/`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title: form.title.trim(), authors: textToAuthors(form.authors), year: form.year ? Number(form.year) : null, venue: form.venue, doi: form.doi.trim() || null, url: form.url.trim(), abstract: form.abstract }) }),
    onSuccess: () => { queryClient.invalidateQueries({ queryKey: ["reference", String(r.id)] }); queryClient.invalidateQueries({ queryKey: ["library"] }); onClose(); },
    onError: (e) => void errorDialog("Couldn't save the reference", e),
  });
  return (
    <form onSubmit={(e) => { e.preventDefault(); if (form.title.trim()) save.mutate(); }} className="mb-4 space-y-3 rounded border border-indigo-200 bg-white p-6 dark:border-indigo-500/40 dark:bg-stone-900" data-testid="reference-edit">
      <h2 className="text-sm font-medium uppercase tracking-wide text-stone-400">Edit reference</h2>
      <label className="block text-xs text-stone-500"><span className="mb-1 block">Title</span><input value={form.title} onChange={set("title")} className={field} required aria-label="Title" /></label>
      <label className="block text-xs text-stone-500"><span className="mb-1 block">Authors · one per line, “Family, Given”</span><textarea value={form.authors} onChange={set("authors")} rows={3} className={`${field} font-mono text-xs`} aria-label="Authors" /></label>
      <div className="grid gap-3 sm:grid-cols-[6rem_minmax(0,1fr)]">
        <label className="block text-xs text-stone-500"><span className="mb-1 block">Year</span><input value={form.year} onChange={set("year")} inputMode="numeric" pattern="[0-9]{4}" className={field} aria-label="Year" /></label>
        <label className="block text-xs text-stone-500"><span className="mb-1 block">Venue</span><input value={form.venue} onChange={set("venue")} className={field} aria-label="Venue" /></label>
      </div>
      <div className="grid gap-3 sm:grid-cols-2">
        <label className="block text-xs text-stone-500"><span className="mb-1 block">DOI</span><input value={form.doi} onChange={set("doi")} className={`${field} font-mono text-xs`} aria-label="DOI" /></label>
        <label className="block text-xs text-stone-500"><span className="mb-1 block">URL</span><input value={form.url} onChange={set("url")} className={`${field} font-mono text-xs`} aria-label="URL" /></label>
      </div>
      <label className="block text-xs text-stone-500"><span className="mb-1 block">Abstract</span><textarea value={form.abstract} onChange={set("abstract")} rows={5} className={field} aria-label="Abstract" /></label>
      <div className="flex items-center gap-3">
        <button type="submit" disabled={save.isPending || !form.title.trim()} className="rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50">{save.isPending ? "Saving…" : "Save changes"}</button>
        <button type="button" onClick={onClose} className="text-sm text-stone-500 hover:underline dark:text-stone-400">Cancel</button>
      </div>
    </form>
  );
}

export default function Reference() {
  const { id } = useParams();
  const listenerRef = useRef<Listener | null>(null);
  const [listening, setListening] = useState(false);
  const [ttsError, setTtsError] = useState("");
  const [tldr, setTldr] = useState<string[] | null>(null);
  const [summarizing, setSummarizing] = useState(false);
  const [editing, setEditing] = useState(false);
  const navigate = useNavigate();

  const queryClient = useQueryClient();
  const { data: ref, isLoading } = useQuery({
    queryKey: ["reference", id],
    queryFn: () => api<Ref>(`/references/${id}/`),
  });
  const { data: highlights } = useQuery({ queryKey: ["highlights", Number(id)], queryFn: () => api<{ results: Highlight[] }>(`/highlights/?reference=${id}&page_size=200`).then((p) => p.results) });
  const citeStyle = (() => { try { return localStorage.getItem("atlas-cite-style") || "apa"; } catch { return "apa"; } })();
  const { data: citation } = useQuery({ queryKey: ["cite", Number(id), citeStyle], queryFn: () => api<Citation>(`/references/${id}/cite/?style=${citeStyle}`) });
  const { data: commentData } = useQuery({
    queryKey: ["comments", "reference", id],
    queryFn: () => api<{ comments: { id: number; body: string; created_at: string }[] }>(`/comments/reference/${id}/`),
  });
  const [commentBody, setCommentBody] = useState("");
  const remove = useMutation({
    mutationFn: () => api(`/references/${id}/`, { method: "DELETE" }),
    onSuccess: () => { queryClient.invalidateQueries(); navigate("/library"); },
    onError: (e) => void errorDialog("Couldn't delete the reference", e),
  });
  const confirmDelete = async () => {
    if (!ref) return;
    const n = ref.projects?.length ?? 0;
    if (await confirmDialog({ title: "Delete this reference from the library?", body: <>“{ref.title}” disappears from {n === 0 ? "the library" : `${n} project${n === 1 ? "" : "s"} and the library`}, with its PDF, highlights and reading notes. This cannot be undone.</>, danger: true, confirmLabel: "Delete reference" })) remove.mutate();
  };
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
    if (listening) { listenerRef.current?.stop(); listenerRef.current = null; setListening(false); return; }
    setTtsError("");
    setListening(true);
    // #404: chunked, prefetched playback (see app/listen.ts)
    const l = listenTo(text);
    listenerRef.current = l;
    try { await l.done; } catch (e) { setTtsError(String((e as Error).message ?? e)); }
    finally { if (listenerRef.current === l) { listenerRef.current = null; setListening(false); } }
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

  if (isLoading || !ref)
    return (
      <div role="status" aria-label="Loading" className="max-w-3xl space-y-4">
        <Skeleton className="h-4 w-40" />
        <section className="rounded border border-stone-200 bg-white p-6 dark:border-stone-800 dark:bg-stone-900">
          <Skeleton className="mb-3 h-7 w-3/4" />
          <Skeleton className="mb-2 h-4 w-1/2" />
          <Skeleton className="h-4 w-1/3" />
        </section>
        <section className="rounded border border-stone-200 bg-white p-6 dark:border-stone-800 dark:bg-stone-900">
          <Skeleton className="mb-3 h-3 w-24" />
          <SkeletonLines lines={4} />
        </section>
      </div>
    );

  return (
    <div className="max-w-3xl">
      <nav className="mb-6 text-sm text-stone-500 dark:text-stone-400">
        <Link to="/library" className="transition-colors hover:text-indigo-700 hover:underline dark:hover:text-indigo-300">Library</Link>
        <span className="px-1.5 text-stone-300 dark:text-stone-400">/</span>
        <span className="font-mono text-xs text-stone-400 dark:text-stone-400">{ref.bibtex_key}</span>
      </nav>

      {editing && <EditReference r={ref} onClose={() => setEditing(false)} />}
      <section className="mb-4 rounded border border-stone-200 bg-white p-6 dark:border-stone-800 dark:bg-stone-900">
        <div className="flex items-start gap-3">
          <h1 className="min-w-0 flex-1 text-2xl font-semibold leading-snug tracking-tight text-stone-900 dark:text-stone-100">{ref.title}</h1>
          <Kebab label="Reference actions" className="mt-1 shrink-0" items={[
            { label: editing ? "Close the editor" : "Edit metadata…", icon: <Pencil className="h-3.5 w-3.5" />, onSelect: () => setEditing((v) => !v) },
            "-",
            { label: "Delete from library…", icon: <Trash2 className="h-3.5 w-3.5" />, danger: true, onSelect: () => void confirmDelete() },
          ]} />
        </div>
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
               className="text-indigo-600 transition-colors hover:text-indigo-700 hover:underline focus:outline-none focus-visible:underline dark:text-indigo-400 dark:hover:text-indigo-300">DOI ↗</a>
          )}
          {ref.url && (
            <a href={ref.url}
               className="text-indigo-600 transition-colors hover:text-indigo-700 hover:underline focus:outline-none focus-visible:underline dark:text-indigo-400 dark:hover:text-indigo-300">Link ↗</a>
          )}
          {ref.pdf && (
            <a href={ref.pdf}
               className="text-indigo-600 transition-colors hover:text-indigo-700 hover:underline focus:outline-none focus-visible:underline dark:text-indigo-400 dark:hover:text-indigo-300">PDF ↗</a>
          )}
          <Link to={`/library?q=${encodeURIComponent(ref.bibtex_key)}`} className="ml-auto text-xs text-indigo-600 transition-colors hover:underline dark:text-indigo-400" title="Open in the Library workbench: read, highlight, cite, discover">open in the Library →</Link>
        </div>
      </section>

      {ref.abstract && (
        <section className="mb-4 rounded border border-stone-200 bg-white p-6 dark:border-stone-800 dark:bg-stone-900">
          <div className="mb-3 flex flex-wrap items-center gap-2">
            <h2 className="text-sm font-medium uppercase tracking-wide text-stone-400 dark:text-stone-400">Abstract</h2>
            <div className="flex items-center gap-2">
              <button onClick={() => listen(`${ref.title}. ${ref.abstract}`)}
                      className="rounded border border-stone-300 bg-white px-2 py-0.5 text-xs text-stone-600 transition-colors hover:border-stone-400 hover:text-stone-800 focus:outline-none focus-visible:border-indigo-600 dark:border-stone-700 dark:bg-stone-800 dark:text-stone-300">
                {listening ? "⏸ Stop" : "🔊 Listen"}
              </button>
              <button onClick={() => summarize(ref.abstract)} disabled={summarizing}
                      className="rounded border border-stone-300 bg-white px-2 py-0.5 text-xs text-stone-600 transition-colors hover:border-stone-400 hover:text-stone-800 focus:outline-none focus-visible:border-indigo-600 disabled:opacity-50 dark:border-stone-700 dark:bg-stone-800 dark:text-stone-300">
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

      {citation && (
        <section className="mb-4 rounded border border-stone-200 bg-white p-6 dark:border-stone-800 dark:bg-stone-900" data-testid="cite-block">
          <h2 className="mb-2 text-sm font-medium uppercase tracking-wide text-stone-400 dark:text-stone-400">Cite · {citation.label}</h2>
          <p className="text-sm leading-relaxed text-stone-700 dark:text-stone-200" dangerouslySetInnerHTML={{ __html: citation.html }} />
          <div className="mt-2 flex flex-wrap gap-2 text-xs">
            <button type="button" onClick={() => navigator.clipboard?.writeText(citation.text)} className="rounded bg-indigo-600 px-2.5 py-1 font-medium text-white hover:bg-indigo-700">Copy citation</button>
            <button type="button" onClick={() => navigator.clipboard?.writeText(citation.intext)} className="rounded border border-stone-300 px-2.5 py-1 text-stone-600 dark:border-stone-700 dark:text-stone-300">{citation.intext}</button>
            <button type="button" onClick={() => navigator.clipboard?.writeText(`\\cite{${ref.bibtex_key}}`)} className="rounded border border-stone-300 px-2.5 py-1 font-mono text-stone-600 dark:border-stone-700 dark:text-stone-300">\cite{"{"}{ref.bibtex_key}{"}"}</button>
          </div>
        </section>
      )}

      {highlights && highlights.length > 0 && (
        <section className="mb-4 rounded border border-stone-200 bg-white p-6 dark:border-stone-800 dark:bg-stone-900" data-testid="highlights-section">
          <h2 className="mb-3 flex items-baseline gap-2 text-sm font-medium uppercase tracking-wide text-stone-400 dark:text-stone-400">Highlights <span className="text-stone-300 dark:text-stone-500">{highlights.length}</span></h2>
          <ul className="space-y-2">
            {highlights.map((h) => (
              <li key={h.id} className="rounded-lg border border-stone-200 p-3 text-sm dark:border-stone-800" style={{ borderLeft: `3px solid ${({ yellow: "#facc15", green: "#4ade80", blue: "#60a5fa", pink: "#f472b6" } as Record<string, string>)[h.color] ?? "#facc15"}` }}>
                <p className="leading-relaxed text-stone-700 dark:text-stone-200">{h.text}</p>
                {h.comment && <p className="mt-1 text-xs italic text-stone-500 dark:text-stone-400">{h.comment}</p>}
                <p className="mt-1 text-[11px] text-stone-400">{h.page ? `p.${h.page}` : "no page"}{h.project_name ? ` · ${h.project_name}` : ""}</p>
              </li>
            ))}
          </ul>
        </section>
      )}

      {ref.pdf && (
        <section className="mb-4 flex flex-wrap items-center gap-3 rounded border border-stone-200 bg-white p-4 dark:border-stone-800 dark:bg-stone-900" data-testid="read-cta">
          <p className="min-w-0 flex-1 text-sm text-stone-600 dark:text-stone-300">A PDF is attached. Read it in the Library's reader to highlight passages, search inside it and take reading notes.</p>
          <Link to={`/library?q=${encodeURIComponent(ref.bibtex_key)}&read=${ref.id}`} className="rounded bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700">Read &amp; highlight →</Link>
          <a href={ref.pdf} target="_blank" rel="noreferrer" className="text-xs text-stone-400 hover:underline">open the file ↗</a>
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
                  className="rounded bg-indigo-600 px-3 py-2 text-sm font-medium text-white transition-colors hover:bg-indigo-700 active:scale-[.98] disabled:opacity-50">
            Comment
          </button>
        </form>
      </section>
    </div>
  );
}
