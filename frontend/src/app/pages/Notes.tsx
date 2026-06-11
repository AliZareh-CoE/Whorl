/** Notes list + markdown editor with wiki-links (SPA slice 6). */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { api } from "../api";

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
  const { data, isLoading } = useQuery({
    queryKey: ["notes", slug],
    queryFn: () => api<Page<Note>>(`/notes/?project=${slug}`),
  });

  if (isLoading) return <p className="text-sm text-stone-400">Loading notes…</p>;
  return (
    <div>
      <nav className="mb-6 text-sm text-stone-500">
        <Link to="/projects" className="hover:underline">Projects</Link> /{" "}
        <Link to={`/projects/${slug}`} className="hover:underline">{slug}</Link> / Notes
      </nav>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Notes</h1>
        <Link to={`/projects/${slug}/notes/new`}
              className="rounded bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700">
          New note
        </Link>
      </div>
      <div className="divide-y divide-stone-100 rounded border border-stone-200 bg-white">
        {data?.results.map((n) => (
          <Link key={n.id} to={`/projects/${slug}/notes/${n.id}`}
                className="block px-4 py-3 text-sm hover:bg-stone-50">
            <span className="font-medium">{n.title}</span>
            <p className="truncate text-xs text-stone-400">
              {n.body.slice(0, 120) || "(empty)"}
              {n.backlinks.length > 0 && ` · ${n.backlinks.length} backlink${n.backlinks.length > 1 ? "s" : ""}`}
            </p>
          </Link>
        ))}
        {data?.results.length === 0 && (
          <p className="px-4 py-8 text-center text-sm text-stone-400">
            Notes are the project's thinking space — [[wiki-links]] connect them.
          </p>
        )}
      </div>
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
    <div>
      <nav className="mb-6 text-sm text-stone-500">
        <Link to={`/projects/${slug}/notes`} className="hover:underline">Notes</Link> /{" "}
        {isNew ? "New" : title || "…"}
      </nav>
      <div className="mb-4 flex items-center gap-3">
        <input
          value={title}
          onChange={(e) => { setTitle(e.target.value); setSaved(false); }}
          placeholder="Note title"
          aria-label="Note title"
          className="flex-1 rounded border border-stone-300 bg-white px-3 py-2 text-lg font-medium focus:border-indigo-600 focus:outline-none"
        />
        <button onClick={togglePreview}
                className="rounded border border-stone-300 bg-white px-3 py-2 text-sm hover:border-stone-400">
          {previewHtml !== null ? "Edit" : "Preview"}
        </button>
        <button onClick={() => save.mutate()} disabled={save.isPending || !title.trim()}
                className="rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50">
          {save.isPending ? "Saving…" : saved ? "Saved" : "Save"}
        </button>
      </div>

      {previewHtml !== null ? (
        /* server-rendered through markdownify → nh3-sanitized, so this is safe HTML */
        <div className="prose prose-stone max-w-none rounded border border-stone-200 bg-white p-5"
             dangerouslySetInnerHTML={{ __html: previewHtml }} />
      ) : (
        <textarea
          value={body}
          onChange={(e) => { setBody(e.target.value); setSaved(false); }}
          rows={18}
          placeholder="Markdown. [[Note Title]] links to other notes in this project."
          aria-label="Note body"
          className="w-full rounded border border-stone-300 bg-white p-4 font-mono text-sm focus:border-indigo-600 focus:outline-none"
        />
      )}

      {!isNew && (note?.backlinks.length ?? 0) > 0 && (
        <section className="mt-4 rounded border border-stone-200 bg-white p-4">
          <h2 className="mb-2 text-[10px] font-medium uppercase tracking-wide text-stone-400">Backlinks</h2>
          <ul className="space-y-1 text-sm">
            {note!.backlinks.map((b) => (
              <li key={b.id}>
                <Link to={`/projects/${slug}/notes/${b.id}`} className="text-indigo-600 hover:underline">
                  {b.title}
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}
      <p className="mt-2 text-xs text-stone-400">Ctrl/Cmd-S saves.</p>
    </div>
  );
}
