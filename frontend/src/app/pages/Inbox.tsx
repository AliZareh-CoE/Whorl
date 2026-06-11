/** Quick-capture inbox with triage (SPA slice 8). */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api";

type Capture = { id: number; text: string; processed: boolean; project: string | null; created_at: string };
type Project = { name: string; slug: string };
type Page<T> = { count: number; results: T[] };

export default function Inbox() {
  const queryClient = useQueryClient();
  const [text, setText] = useState("");

  const { data, isLoading } = useQuery({
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
  const open = (data?.results ?? []).filter((c) => !c.processed);

  return (
    <div>
      <h1 className="mb-2 text-2xl font-semibold tracking-tight">Inbox</h1>
      <p className="mb-6 text-sm text-stone-500">Get it out of your head now, file it later.</p>

      <form className="mb-8 flex max-w-2xl items-start gap-2"
            onSubmit={(e) => { e.preventDefault(); if (text.trim()) capture.mutate(); }}>
        <textarea value={text} onChange={(e) => setText(e.target.value)} rows={2}
                  placeholder="Idea, todo, paper to find…" aria-label="Capture"
                  className="flex-1 rounded border border-stone-300 bg-white px-3 py-2 text-sm focus:border-indigo-600 focus:outline-none" />
        <button type="submit" disabled={capture.isPending}
                className="rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700">
          Capture
        </button>
      </form>

      <div className="max-w-2xl divide-y divide-stone-100 rounded border border-stone-200 bg-white">
        {open.map((c) => (
          <TriageRow key={c.id} capture={c} projects={projects?.results ?? []}
                     onTriage={(project) => triage.mutate({ id: c.id, project })} />
        ))}
        {open.length === 0 && (
          <p className="px-4 py-8 text-center text-sm text-stone-400">Inbox zero. Nice.</p>
        )}
      </div>
    </div>
  );
}

function TriageRow({ capture, projects, onTriage }:
  { capture: Capture; projects: Project[]; onTriage: (project?: string) => void }) {
  const [project, setProject] = useState(projects[0]?.slug ?? "");
  return (
    <div className="flex items-center gap-3 px-4 py-3">
      <p className="min-w-0 flex-1 text-sm">{capture.text}</p>
      <select value={project} onChange={(e) => setProject(e.target.value)} aria-label="File to project"
              className="shrink-0 rounded border border-stone-300 bg-white px-2 py-1 text-xs">
        {projects.map((p) => <option key={p.slug} value={p.slug}>{p.name}</option>)}
      </select>
      <button onClick={() => onTriage(project)}
              className="shrink-0 rounded bg-indigo-600 px-2 py-1 text-xs font-medium text-white hover:bg-indigo-700">
        File
      </button>
      <button onClick={() => onTriage(undefined)}
              className="shrink-0 rounded border border-stone-300 px-2 py-1 text-xs text-stone-500 hover:border-stone-400">
        Dismiss
      </button>
    </div>
  );
}
