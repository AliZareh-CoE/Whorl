/** Quick-capture inbox with triage (SPA slice 8). */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api";
import { ErrorState } from "../../components/ErrorState";

type Capture = { id: number; text: string; processed: boolean; project: string | null; created_at: string };
type Project = { name: string; slug: string };
type Page<T> = { count: number; results: T[] };

export default function Inbox() {
  const queryClient = useQueryClient();
  const [text, setText] = useState("");

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["inbox"],
    queryFn: () => api<Page<Capture>>("/quick-capture/"),
  });
  const { data: projects } = useQuery({
    queryKey: ["projects"],
    queryFn: () => api<Page<Project>>("/projects/"),
  });

  const refresh = () => queryClient.invalidateQueries({ queryKey: ["inbox"] });
  const capture = useMutation({
    mutationFn: () =>
      api("/quick-capture/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text }),
      }),
    onSuccess: () => { setText(""); refresh(); },
  });
  const triage = useMutation({
    mutationFn: ({ id, project }: { id: number; project?: string }) =>
      api(`/quick-capture/${id}/`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(project ? { processed: true, project } : { processed: true }),
      }),
    onSettled: refresh,
  });

  if (isLoading) return <p className="text-sm text-stone-400">Loading inbox…</p>;
  if (error || !data) return <ErrorState message="Couldn't load the inbox." onRetry={() => refetch()} />;
  const open = (data?.results ?? []).filter((c) => !c.processed);

  return (
    <div className="max-w-2xl">
      <h1 className="mb-2 text-2xl font-semibold tracking-tight">Inbox</h1>
      <p className="mb-6 text-sm text-stone-500 dark:text-stone-300">Get it out of your head now, file it later.</p>

      <form className="mb-10"
            onSubmit={(e) => { e.preventDefault(); if (text.trim()) capture.mutate(); }}>
        <div className="rounded border border-stone-200 bg-white p-2 shadow-sm transition focus-within:border-indigo-600 focus-within:ring-2 focus-within:ring-indigo-600/15 dark:border-stone-800 dark:bg-stone-900">
          <textarea value={text} onChange={(e) => setText(e.target.value)} rows={3}
                    placeholder="Capture a stray thought — an idea, a todo, a paper to find…" aria-label="Capture"
                    className="block w-full resize-none border-0 bg-transparent px-2 py-1.5 text-sm leading-relaxed text-stone-800 placeholder:text-stone-400 focus:outline-none focus:ring-0 dark:text-stone-100" />
          <div className="flex items-center justify-between border-t border-stone-100 px-2 pt-2 dark:border-stone-800">
            <span className="text-xs text-stone-400">Goes straight to the inbox — file it later.</span>
            <button type="submit" disabled={capture.isPending || !text.trim()}
                    className="rounded bg-indigo-600 px-4 py-1.5 text-sm font-medium text-white transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-40">
              {capture.isPending ? "Capturing…" : "Capture"}
            </button>
          </div>
        </div>
      </form>

      <div className="mb-3 flex items-baseline gap-2">
        <h2 className="text-sm font-medium uppercase tracking-wide text-stone-400">To triage</h2>
        {open.length > 0 && <span className="text-sm text-stone-300 dark:text-stone-400">{open.length}</span>}
      </div>

      {open.length === 0 ? (
        <div className="rounded border border-dashed border-stone-300 bg-white p-10 text-center dark:border-stone-700 dark:bg-stone-900">
          <p className="mb-1 text-3xl">📥</p>
          <p className="mb-1 text-sm font-medium text-stone-600 dark:text-stone-300">Inbox zero. Nice.</p>
          <p className="text-sm text-stone-400">Capture a stray thought above and file it to a project when you're ready.</p>
        </div>
      ) : (
        <div className="divide-y divide-stone-100 overflow-hidden rounded border border-stone-200 bg-white dark:divide-stone-800 dark:border-stone-800 dark:bg-stone-900">
          {open.map((c) => (
            <TriageRow key={c.id} capture={c} projects={projects?.results ?? []}
                       onTriage={(project) => triage.mutate({ id: c.id, project })} />
          ))}
        </div>
      )}
    </div>
  );
}

function TriageRow({ capture, projects, onTriage }:
  { capture: Capture; projects: Project[]; onTriage: (project?: string) => void }) {
  const [project, setProject] = useState(projects[0]?.slug ?? "");
  return (
    <div className="group flex items-center gap-3 px-4 py-3 transition hover:bg-stone-50 dark:hover:bg-stone-800">
      <p className="min-w-0 flex-1 whitespace-pre-wrap break-words text-sm leading-relaxed text-stone-700 dark:text-stone-300">{capture.text}</p>
      <div className="flex shrink-0 items-center gap-2 opacity-60 transition group-hover:opacity-100 group-focus-within:opacity-100">
        <select value={project} onChange={(e) => setProject(e.target.value)} aria-label="File to project"
                className="shrink-0 rounded border border-stone-200 bg-white px-2 py-1 text-xs text-stone-600 focus:border-indigo-600 focus:outline-none focus:ring-1 focus:ring-indigo-600/20 dark:border-stone-700 dark:bg-stone-800 dark:text-stone-300">
          {projects.map((p) => <option key={p.slug} value={p.slug}>{p.name}</option>)}
        </select>
        <button onClick={() => onTriage(project)}
                className="shrink-0 rounded bg-indigo-600 px-2.5 py-1 text-xs font-medium text-white transition hover:bg-indigo-700">
          File
        </button>
        <button onClick={() => onTriage(undefined)}
                className="shrink-0 rounded px-2 py-1 text-xs text-stone-400 transition hover:text-stone-600 dark:hover:text-stone-300">
          Dismiss
        </button>
      </div>
    </div>
  );
}
