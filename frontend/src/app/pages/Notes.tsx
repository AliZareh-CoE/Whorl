/** Notes list + markdown editor with wiki-links (SPA slice 6). */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api";
import { Skeleton } from "../../components/Skeleton";
import { ErrorState } from "../../components/ErrorState";

type Backlink = { id: number; title: string };
type Note = {
  id: number;
  title: string;
  body: string;
  backlinks: Backlink[];
  updated_at: string;
};
type Page<T> = { count: number; results: T[] };

export function NotesList() {
  const { slug } = useParams();
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["notes", slug],
    queryFn: () => api<Page<Note>>(`/notes/?project=${slug}`),
  });

  if (isLoading)
    return (
      <div role="status" aria-label="Loading">
        <Skeleton className="mb-6 h-4 w-56" />
        <div className="mb-6 flex items-center justify-between">
          <Skeleton className="h-7 w-32" />
          <Skeleton className="h-8 w-24" />
        </div>
        <div className="divide-y divide-stone-100 overflow-hidden rounded border border-stone-200 bg-white dark:divide-stone-800 dark:border-stone-800 dark:bg-stone-900">
          {Array.from({ length: 5 }).map((_, i) => (
            <div key={i} className="px-5 py-4">
              <Skeleton className="mb-2 h-4 w-2/5" />
              <Skeleton className="h-3 w-3/4" />
            </div>
          ))}
        </div>
      </div>
    );
  if (error || !data) return <ErrorState message="Couldn't load notes." onRetry={() => refetch()} />;
  const notes = data?.results ?? [];
  return (
    <div>
      <nav className="mb-6 text-sm text-stone-500 dark:text-stone-400">
        <Link to="/projects" className="hover:text-indigo-700 hover:underline dark:hover:text-indigo-300">Projects</Link>
        <span className="px-1.5 text-stone-300 dark:text-stone-400">/</span>
        <Link to={`/projects/${slug}`} className="hover:text-indigo-700 hover:underline dark:hover:text-indigo-300">{slug}</Link>
        <span className="px-1.5 text-stone-300 dark:text-stone-400">/</span>
        <span className="text-stone-700 dark:text-stone-300">Notes</span>
      </nav>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight text-stone-900 dark:text-stone-100">Notes</h1>
        <Link to={`/projects/${slug}/notes/new`}
              className="rounded bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-indigo-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-600 focus-visible:ring-offset-2">
          New note
        </Link>
      </div>

      {notes.length === 0 ? (
        <div className="rounded border border-dashed border-stone-300 bg-white p-12 text-center dark:border-stone-700 dark:bg-stone-900">
          <p className="mb-1 text-sm font-medium text-stone-700 dark:text-stone-300">No notes yet</p>
          <p className="mx-auto mb-5 max-w-md text-sm text-stone-400 dark:text-stone-400">
            Notes are the project's thinking space — connect them with{" "}
            <span className="font-medium text-indigo-600 dark:text-indigo-400">[[wiki-links]]</span>.
          </p>
          <Link to={`/projects/${slug}/notes/new`}
                className="inline-block rounded bg-indigo-600 px-3.5 py-1.5 text-sm font-medium text-white transition-colors hover:bg-indigo-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-600 focus-visible:ring-offset-2">
            Write your first note
          </Link>
        </div>
      ) : (
        <div className="divide-y divide-stone-100 overflow-hidden rounded border border-stone-200 bg-white dark:divide-stone-800 dark:border-stone-800 dark:bg-stone-900">
          {notes.map((n) => (
            <Link key={n.id} to={`/projects/${slug}/notes/${n.id}`}
                  className="block px-5 py-4 transition-colors hover:bg-stone-50 focus:outline-none focus-visible:bg-stone-50 dark:hover:bg-stone-800 dark:focus-visible:bg-stone-800">
              <div className="flex items-baseline justify-between gap-3">
                <span className="truncate text-sm font-medium text-stone-900 dark:text-stone-100">{n.title}</span>
                {n.backlinks.length > 0 && (
                  <span className="shrink-0 text-xs text-stone-400 dark:text-stone-400">
                    {n.backlinks.length} backlink{n.backlinks.length > 1 ? "s" : ""}
                  </span>
                )}
              </div>
              <p className="mt-0.5 truncate text-xs text-stone-400 dark:text-stone-400">
                {n.body.slice(0, 140) || "Empty note"}
              </p>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}

export function NoteEditor() {
  const { slug, id } = useParams();
  const isNew = id === undefined;
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [previewHtml, setPreviewHtml] = useState<string | null>(null);
  const [saved, setSaved] = useState(true);

  const { data: note } = useQuery({
    queryKey: ["note", id],
    queryFn: () => api<Note>(`/notes/${id}/`),
    enabled: !isNew,
  });
  useEffect(() => {
    if (note) {
      setTitle(note.title);
      setBody(note.body);
    }
  }, [note]);

  const save = useMutation({
    mutationFn: () =>
      isNew
        ? api<Note>("/notes/", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ project: slug, title, body }),
          })
        : api<Note>(`/notes/${id}/`, {
            method: "PATCH",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ title, body }),
          }),
    onSuccess: (created) => {
      setSaved(true);
      queryClient.invalidateQueries({ queryKey: ["notes", slug] });
      queryClient.invalidateQueries({ queryKey: ["note", id] });
      if (isNew) navigate(`/projects/${slug}/notes/${created.id}`, { replace: true });
    },
  });

  async function togglePreview() {
    if (previewHtml !== null) {
      setPreviewHtml(null);
      return;
    }
    const data = await api<{ html: string }>("/notes/preview/", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ body, project: slug }),
    });
    setPreviewHtml(data.html);
  }

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key === "s") {
        e.preventDefault();
        save.mutate();
      }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  });

  return (
    <div className="mx-auto max-w-3xl">
      <nav className="mb-6 text-sm text-stone-500 dark:text-stone-400">
        <Link to={`/projects/${slug}`} className="hover:text-indigo-700 hover:underline dark:hover:text-indigo-300">{slug}</Link>
        <span className="px-1.5 text-stone-300 dark:text-stone-400">/</span>
        <Link to={`/projects/${slug}/notes`} className="hover:text-indigo-700 hover:underline dark:hover:text-indigo-300">Notes</Link>
        <span className="px-1.5 text-stone-300 dark:text-stone-400">/</span>
        <span className="text-stone-700 dark:text-stone-300">{isNew ? "New note" : title || "Untitled"}</span>
      </nav>
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-center">
        <input
          value={title}
          onChange={(e) => { setTitle(e.target.value); setSaved(false); }}
          placeholder="Note title"
          aria-label="Note title"
          className="flex-1 rounded border border-stone-300 bg-white px-3 py-2 text-lg font-medium text-stone-900 placeholder:text-stone-400 focus:border-indigo-600 focus:outline-none focus:ring-1 focus:ring-indigo-600 dark:border-stone-700 dark:bg-stone-800 dark:text-stone-100"
        />
        <div className="flex items-center gap-2">
          <button onClick={togglePreview}
                  className="rounded border border-stone-300 bg-white px-3 py-2 text-sm text-stone-600 transition-colors hover:border-stone-400 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-600 focus-visible:ring-offset-2 dark:border-stone-700 dark:bg-stone-800 dark:text-stone-300">
            {previewHtml !== null ? "Edit" : "Preview"}
          </button>
          <button onClick={() => save.mutate()} disabled={save.isPending || !title.trim()}
                  className="rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-indigo-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-600 focus-visible:ring-offset-2 disabled:opacity-50">
            {save.isPending ? "Saving…" : saved ? "Saved" : "Save"}
          </button>
        </div>
      </div>

      {previewHtml !== null ? (
        /* server-rendered through markdownify → nh3-sanitized, so this is safe HTML */
        <div className="prose prose-stone max-w-none rounded border border-stone-200 bg-white p-8 dark:prose-invert dark:border-stone-800 dark:bg-stone-900"
             dangerouslySetInnerHTML={{ __html: previewHtml }} />
      ) : (
        <textarea
          value={body}
          onChange={(e) => { setBody(e.target.value); setSaved(false); }}
          rows={20}
          placeholder="Markdown. [[Note Title]] links to other notes in this project."
          aria-label="Note body"
          className="w-full resize-y rounded border border-stone-300 bg-white p-6 font-mono text-sm leading-relaxed text-stone-900 placeholder:text-stone-400 focus:border-indigo-600 focus:outline-none focus:ring-1 focus:ring-indigo-600 dark:border-stone-700 dark:bg-stone-800 dark:text-stone-100"
        />
      )}

      {!isNew && (note?.backlinks.length ?? 0) > 0 && (
        <section className="mt-6 rounded border border-stone-200 bg-white p-5 dark:border-stone-800 dark:bg-stone-900">
          <h2 className="mb-3 text-sm font-medium uppercase tracking-wide text-stone-400 dark:text-stone-400">Backlinks</h2>
          <ul className="space-y-2 text-sm">
            {note!.backlinks.map((b) => (
              <li key={b.id}>
                <Link to={`/projects/${slug}/notes/${b.id}`} className="text-indigo-600 transition-colors hover:text-indigo-700 hover:underline dark:text-indigo-400 dark:hover:text-indigo-300">
                  {b.title}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}
      <p className="mt-4 text-xs text-stone-400 dark:text-stone-400">Press Ctrl/Cmd-S to save.</p>
    </div>
  );
}
