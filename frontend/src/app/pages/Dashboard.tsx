import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";

type Attention = {
  empty: boolean;
  overdue: { title: string; due_date: string; project: string; url: string }[];
  deadlines: { title: string; deadline: string; days_to_deadline: number; project: string; url: string }[];
  inbox: { id: number; text: string }[];
};

type Dash = {
  stats: Record<string, number>;
  inbox_count: number;
  attention: Attention;
  active: {
    name: string; slug: string; url: string; color: string;
    phase: string | null; done: number; total: number; percent: number;
  }[];
  milestones: { title: string; project: string; due_date: string | null; overdue: boolean; url: string }[];
  deadlines: { title: string; deadline: string | null; url: string }[];
};

const card = "rounded border border-stone-200 bg-white px-4 py-3";

/** Inline triage on an attention inbox row (#157): file to a project or dismiss. */
function TriageControls({ id, projects }: { id: number; projects: { slug: string; name: string }[] }) {
  const queryClient = useQueryClient();
  const [slug, setSlug] = useState(projects[0]?.slug ?? "");
  const triage = useMutation({
    mutationFn: (body: { processed: boolean; project?: string }) =>
      api(`/quick-capture/${id}/`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["dashboard"] }),
  });
  return (
    <span className="flex shrink-0 items-center gap-1">
      <select
        value={slug}
        onChange={(e) => setSlug(e.target.value)}
        className="rounded border border-stone-200 px-1 py-0.5 text-xs text-stone-600"
      >
        {projects.map((p) => (
          <option key={p.slug} value={p.slug}>{p.name.slice(0, 22)}</option>
        ))}
      </select>
      <button
        type="button"
        disabled={triage.isPending || !slug}
        onClick={() => triage.mutate({ processed: true, project: slug })}
        className="rounded px-1.5 py-0.5 text-xs text-indigo-600 hover:bg-indigo-50 disabled:opacity-50"
      >
        file
      </button>
      <button
        type="button"
        title="Dismiss"
        disabled={triage.isPending}
        onClick={() => triage.mutate({ processed: true })}
        className="rounded px-1.5 py-0.5 text-xs text-stone-400 hover:bg-stone-100 hover:text-stone-600 disabled:opacity-50"
      >
        ✕
      </button>
    </span>
  );
}

export default function Dashboard() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => api<Dash>("/dashboard/"),
  });

  if (isLoading) return <p className="text-sm text-stone-400">Loading your day…</p>;
  if (error || !data) return <p className="text-sm text-red-600">Couldn't load the dashboard.</p>;

  const attention = data.attention;
  return (
    <div>
      <h1 className="mb-4 text-2xl font-semibold tracking-tight">Today, everywhere</h1>

      {/* the answer first ([REV] cycle 145 → SPA #156): what needs me today */}
      {attention.empty ? (
        <div className="mb-3 rounded border border-stone-200 bg-white px-4 py-2.5 text-sm text-stone-500">
          All clear — nothing overdue, no deadlines inside two weeks, inbox triaged.
        </div>
      ) : (
        <section className="mb-3 rounded border border-l-2 border-stone-200 border-l-red-400 bg-white p-4">
          <h2 className="mb-2 text-xs font-medium uppercase tracking-wide text-stone-400">Needs attention</h2>
          <ul className="space-y-1 text-sm">
            {attention.overdue.map((m) => (
              <li key={`o${m.url}${m.title}`} className="flex items-baseline gap-2">
                <span className="shrink-0 text-xs font-medium text-red-600">overdue</span>
                <a href={m.url} className="min-w-0 flex-1 truncate hover:underline">{m.title}</a>
                <span className="shrink-0 text-xs text-stone-400">{m.project} · due {m.due_date}</span>
              </li>
            ))}
            {attention.deadlines.map((d) => (
              <li key={`d${d.url}${d.title}`} className="flex items-baseline gap-2">
                <span className={`shrink-0 text-xs font-medium ${d.days_to_deadline < 7 ? "text-red-600" : "text-amber-600"}`}>deadline</span>
                <a href={d.url} className="min-w-0 flex-1 truncate hover:underline">{d.title}</a>
                <span className="shrink-0 text-xs text-stone-400">
                  {d.project} · {d.days_to_deadline < 0 ? "passed" : `${d.days_to_deadline} day${d.days_to_deadline === 1 ? "" : "s"}`} ({d.deadline})
                </span>
              </li>
            ))}
            {attention.inbox.map((q) => (
              <li key={`q${q.id}`} className="flex items-baseline gap-2">
                <span className="shrink-0 text-xs font-medium text-indigo-600">inbox</span>
                <span className="min-w-0 flex-1 truncate text-stone-600">{q.text}</span>
                <TriageControls id={q.id} projects={data.active} />
                <Link to="/inbox" className="shrink-0 text-xs text-stone-400 hover:underline" title="Open the full inbox">all →</Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      <div className="mb-4 grid grid-cols-2 gap-3 sm:grid-cols-4">
        <div className={card}>
          <p className="text-2xl font-semibold">{data.stats.papers_read}</p>
          <p className="text-xs text-stone-400">papers read this month</p>
        </div>
        <div className={card}>
          <p className="text-2xl font-semibold">{data.stats.notes_written}</p>
          <p className="text-xs text-stone-400">notes written this month</p>
        </div>
        <div className={card}>
          <p className="text-2xl font-semibold">{data.stats.milestones_done}</p>
          <p className="text-xs text-stone-400">milestones completed</p>
        </div>
        <div className={card}>
          <p className="text-2xl font-semibold">{data.inbox_count}</p>
          <p className="text-xs text-stone-400"><a href="/inbox/" className="hover:underline">inbox items to triage</a></p>
        </div>
      </div>

      <div className="grid gap-3 lg:grid-cols-3">
        <section className="rounded border border-stone-200 bg-white p-4">
          <h2 className="mb-3 text-xs font-medium uppercase tracking-wide text-stone-400">Active projects</h2>
          <div className="space-y-3">
            {data.active.map((p) => (
              <Link key={p.slug} to={`/projects/${p.slug}`} className="block">
                <div className="mb-1 flex items-baseline justify-between text-sm">
                  <span className="font-medium">{p.name}</span>
                  <span className="text-xs text-stone-400">
                    {p.phase ? `${p.phase} · ` : ""}{p.done}/{p.total}
                  </span>
                </div>
                <div className="h-1.5 w-full rounded-full bg-stone-100">
                  <div className="h-1.5 rounded-full" style={{ width: `${p.percent}%`, background: p.color }} />
                </div>
              </Link>
            ))}
            {data.active.length === 0 && <p className="text-sm text-stone-400">No active projects.</p>}
          </div>
        </section>

        <section className="rounded border border-stone-200 bg-white p-4">
          <h2 className="mb-3 text-xs font-medium uppercase tracking-wide text-stone-400">Deadlines</h2>
          <ul className="space-y-1.5 text-sm">
            {data.deadlines.map((d) => (
              <li key={d.url + d.title}>
                <a href={d.url} className="flex items-baseline gap-2 hover:text-indigo-700">
                  <span aria-hidden="true">✍</span>
                  <span className="min-w-0 flex-1 truncate font-medium">{d.title}</span>
                  <span className="shrink-0 text-xs text-stone-400">{d.deadline}</span>
                </a>
              </li>
            ))}
            {data.deadlines.length === 0 && <p className="text-sm text-stone-400">No manuscript deadlines.</p>}
          </ul>
        </section>

        <section className="rounded border border-stone-200 bg-white p-4">
          <h2 className="mb-3 text-xs font-medium uppercase tracking-wide text-stone-400">Upcoming milestones</h2>
          <ul className="space-y-1.5 text-sm">
            {data.milestones.map((m) => (
              <li key={m.url + m.title}>
                <a href={m.url} className="flex items-baseline gap-2 hover:text-indigo-700">
                  <span aria-hidden="true">◆</span>
                  <span className="min-w-0 flex-1 truncate">{m.title}</span>
                  <span className={`shrink-0 text-xs ${m.overdue ? "font-medium text-red-600" : "text-stone-400"}`}>
                    {m.due_date}{m.overdue ? " · overdue" : ""}
                  </span>
                </a>
              </li>
            ))}
            {data.milestones.length === 0 && <p className="text-sm text-stone-400">Nothing scheduled.</p>}
          </ul>
        </section>
      </div>
    </div>
  );
}
