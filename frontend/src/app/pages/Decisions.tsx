/** Decision log: list + create (SPA slice 9). */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";

type Decision = { id: number; title: string; context: string; decision: string; decided_on: string };
type Page<T> = { count: number; results: T[] };

export default function Decisions() {
  const { slug } = useParams();
  const queryClient = useQueryClient();
  const [formOpen, setFormOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [decision, setDecision] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["decisions", slug],
    queryFn: () => api<Page<Decision>>(`/decisions/?project=${slug}`),
  });

  const create = useMutation({
    mutationFn: () =>
      api("/decisions/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          project: slug,
          title,
          decision,
          decided_on: new Date().toISOString().slice(0, 10),
        }),
      }),
    onSuccess: () => {
      setTitle(""); setDecision(""); setFormOpen(false);
      queryClient.invalidateQueries({ queryKey: ["decisions", slug] });
    },
  });

  if (isLoading) return <p className="text-sm text-stone-400">Loading decisions…</p>;
  return (
    <div>
      <nav className="mb-6 text-sm text-stone-500">
        <Link to="/projects" className="hover:underline">Projects</Link> /{" "}
        <Link to={`/projects/${slug}`} className="hover:underline">{slug}</Link> / Decisions
      </nav>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Decision log</h1>
        <button onClick={() => setFormOpen(!formOpen)}
                className="rounded bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700">
          {formOpen ? "Cancel" : "Record decision"}
        </button>
      </div>

      {formOpen && (
        <form className="mb-6 space-y-3 rounded border border-stone-200 bg-white p-5"
              onSubmit={(e) => { e.preventDefault(); if (title.trim() && decision.trim()) create.mutate(); }}>
          <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="What was decided (one line)"
                 aria-label="Decision title"
                 className="w-full rounded border border-stone-300 bg-white px-3 py-2 text-sm focus:border-indigo-600 focus:outline-none" />
          <textarea value={decision} onChange={(e) => setDecision(e.target.value)} rows={3}
                    placeholder="The decision and why (markdown ok)" aria-label="Decision body"
                    className="w-full rounded border border-stone-300 bg-white px-3 py-2 text-sm focus:border-indigo-600 focus:outline-none" />
          <button type="submit" disabled={create.isPending}
                  className="rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700">
            Save
          </button>
        </form>
      )}

      <ol className="relative space-y-4 border-l border-stone-200 pl-5">
        {(data?.results ?? []).map((d) => (
          <li key={d.id} className="text-sm">
            <span className="absolute -left-[5px] mt-1.5 h-2.5 w-2.5 rounded-full border border-white bg-indigo-400" />
            <span className="font-medium">{d.title}</span>
            <span className="ml-2 text-xs text-stone-400">{d.decided_on}</span>
            {d.decision && <p className="mt-0.5 text-xs text-stone-500">{d.decision.slice(0, 240)}</p>}
          </li>
        ))}
        {data?.results.length === 0 && <li className="text-sm text-stone-400">No decisions recorded yet.</li>}
      </ol>
    </div>
  );
}
