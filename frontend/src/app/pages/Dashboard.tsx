import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../api";
import { toggleCalm, useCalm } from "../calm";
import { Skeleton, SkeletonCard, SkeletonLines } from "../../components/Skeleton";

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

const card = "rounded border border-stone-200 bg-white px-4 py-4 dark:border-stone-800 dark:bg-stone-900";
const section = "rounded border border-stone-200 bg-white p-5 dark:border-stone-800 dark:bg-stone-900";
const h2 = "mb-3 text-sm font-medium uppercase tracking-wide text-stone-400 dark:text-stone-400";

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
        className="rounded border border-stone-200 px-1 py-0.5 text-xs text-stone-600 dark:border-stone-700 dark:bg-stone-800 dark:text-stone-300"
      >
        {projects.map((p) => (
          <option key={p.slug} value={p.slug}>{p.name.slice(0, 22)}</option>
        ))}
      </select>
      <button
        type="button"
        disabled={triage.isPending || !slug}
        onClick={() => triage.mutate({ processed: true, project: slug })}
        className="rounded px-1.5 py-0.5 text-xs text-indigo-600 transition-colors hover:bg-indigo-50 active:opacity-80 disabled:opacity-50 dark:text-indigo-400 dark:hover:bg-indigo-500/10"
      >
        file
      </button>
      <button
        type="button"
        title="Dismiss"
        disabled={triage.isPending}
        onClick={() => triage.mutate({ processed: true })}
        className="rounded px-1.5 py-0.5 text-xs text-stone-400 transition-colors hover:bg-stone-100 hover:text-stone-600 active:opacity-80 disabled:opacity-50 dark:text-stone-400 dark:hover:bg-stone-800 dark:hover:text-stone-300"
      >
        ✕
      </button>
    </span>
  );
}

export default function Dashboard() {
  // Calm mode (#274) lives in ../calm so the ⌘K palette verb (#277) can flip it and this
  // page updates live (#278) — no remount, no settings page.
  const calm = useCalm();

  const { data, isLoading, error } = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => api<Dash>("/dashboard/"),
  });

  if (isLoading)
    return (
      <div role="status" aria-label="Loading" className="space-y-6">
        <div>
          <Skeleton className="mb-2 h-7 w-56" />
          <Skeleton className="h-4 w-72" />
        </div>
        <SkeletonLines lines={3} />
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
        <div className="grid gap-4 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      </div>
    );
  if (error || !data) return <p className="text-sm text-red-600 dark:text-red-300">Couldn't load the dashboard.</p>;

  const attention = data.attention;
  return (
    <div>
      <div className="mb-6 flex items-start justify-between gap-4">
        <div>
          <h1 className="mb-1 text-2xl font-semibold tracking-tight dark:text-stone-100">Today, everywhere</h1>
          <p className="text-sm text-stone-500 dark:text-stone-300">What needs you, across every project.</p>
        </div>
        <button
          type="button"
          onClick={toggleCalm}
          aria-pressed={calm}
          title={calm ? "Show the monthly stats" : "Hide the monthly stats — show only what needs you"}
          className="shrink-0 rounded border border-stone-200 px-2.5 py-1 text-xs text-stone-500 transition-colors hover:border-stone-300 hover:text-stone-700 dark:border-stone-700 dark:text-stone-400 dark:hover:text-stone-200"
        >
          {calm ? "Full view" : "Calm mode"}
        </button>
      </div>

      {/* the answer first ([REV] cycle 145 → SPA #156): what needs me today */}
      {attention.empty ? (
        <div className="mb-4 rounded border border-dashed border-stone-300 bg-white px-4 py-3 text-sm text-stone-500 dark:border-stone-700 dark:bg-stone-900 dark:text-stone-300">
          All clear — nothing overdue, no deadlines inside two weeks, inbox triaged.
        </div>
      ) : (
        <section className="mb-4 rounded border border-l-2 border-stone-200 border-l-red-400 bg-white p-5 dark:border-stone-800 dark:bg-stone-900">
          <h2 className={`${h2} mb-2.5`}>Needs attention</h2>
          <ul className="space-y-1.5 text-sm">
            {attention.overdue.map((m) => (
              <li key={`o${m.url}${m.title}`} className="flex items-baseline gap-2">
                <span className="shrink-0 text-xs font-medium text-red-600 dark:text-red-300">overdue</span>
                <a href={m.url} className="min-w-0 flex-1 truncate hover:underline dark:text-stone-100">{m.title}</a>
                <span className="shrink-0 text-xs text-stone-400 dark:text-stone-400">{m.project} · due {m.due_date}</span>
              </li>
            ))}
            {attention.deadlines.map((d) => (
              <li key={`d${d.url}${d.title}`} className="flex items-baseline gap-2">
                <span className={`shrink-0 text-xs font-medium ${d.days_to_deadline < 7 ? "text-red-600 dark:text-red-300" : "text-amber-600 dark:text-amber-300"}`}>deadline</span>
                <a href={d.url} className="min-w-0 flex-1 truncate hover:underline dark:text-stone-100">{d.title}</a>
                <span className="shrink-0 text-xs text-stone-400 dark:text-stone-400">
                  {d.project} · {d.days_to_deadline < 0 ? "passed" : `${d.days_to_deadline} day${d.days_to_deadline === 1 ? "" : "s"}`} ({d.deadline})
                </span>
              </li>
            ))}
            {attention.inbox.map((q) => (
              <li key={`q${q.id}`} className="flex items-baseline gap-2">
                <span className="shrink-0 text-xs font-medium text-indigo-600 dark:text-indigo-400">inbox</span>
                <span className="min-w-0 flex-1 truncate text-stone-600 dark:text-stone-300">{q.text}</span>
                <TriageControls id={q.id} projects={data.active} />
                <Link to="/inbox" className="shrink-0 text-xs text-stone-400 hover:underline dark:text-stone-400" title="Open the full inbox">all →</Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      {!calm && (
      <div className="mb-4 grid grid-cols-2 gap-4 sm:grid-cols-4">
        <div className={card}>
          <p className="text-2xl font-semibold tabular-nums dark:text-stone-100">{data.stats.papers_read}</p>
          <p className="mt-0.5 text-xs text-stone-400 dark:text-stone-400">papers read this month</p>
        </div>
        <div className={card}>
          <p className="text-2xl font-semibold tabular-nums dark:text-stone-100">{data.stats.notes_written}</p>
          <p className="mt-0.5 text-xs text-stone-400 dark:text-stone-400">notes written this month</p>
        </div>
        <div className={card}>
          <p className="text-2xl font-semibold tabular-nums dark:text-stone-100">{data.stats.milestones_done}</p>
          <p className="mt-0.5 text-xs text-stone-400 dark:text-stone-400">milestones completed</p>
        </div>
        <div className={card}>
          <p className="text-2xl font-semibold tabular-nums dark:text-stone-100">{data.inbox_count}</p>
          <p className="mt-0.5 text-xs text-stone-400 dark:text-stone-400"><a href="/inbox/" className="hover:text-indigo-700 dark:hover:text-indigo-300">inbox items to triage</a></p>
        </div>
      </div>
      )}

      <div className="grid gap-4 lg:grid-cols-3">
        <section className={section}>
          <h2 className={h2}>Active projects</h2>
          <div className="space-y-3.5">
            {data.active.map((p) => (
              <Link key={p.slug} to={`/projects/${p.slug}`} className="group block">
                <div className="mb-1.5 flex items-baseline justify-between text-sm">
                  <span className="min-w-0 flex-1 truncate font-medium group-hover:text-indigo-700 dark:text-stone-100 dark:group-hover:text-indigo-300">{p.name}</span>
                  <span className="ml-2 shrink-0 text-xs text-stone-400 dark:text-stone-400">
                    {p.phase ? `${p.phase} · ` : ""}{p.done}/{p.total}
                  </span>
                </div>
                <div className="h-1.5 w-full rounded-full bg-stone-100 dark:bg-stone-800">
                  <div className="h-1.5 rounded-full" style={{ width: `${p.percent}%`, background: p.color }} />
                </div>
              </Link>
            ))}
            {data.active.length === 0 && (
              <p className="text-sm text-stone-400 dark:text-stone-400">
                No active projects. <Link to="/projects" className="text-indigo-600 hover:text-indigo-700 dark:text-indigo-400 dark:hover:text-indigo-300">Start one →</Link>
              </p>
            )}
          </div>
        </section>

        <section className={section}>
          <h2 className={h2}>Deadlines</h2>
          <ul className="space-y-1 text-sm">
            {data.deadlines.map((d) => (
              <li key={d.url + d.title}>
                <a href={d.url} className="-mx-2 flex items-baseline gap-2 rounded px-2 py-1 hover:bg-stone-50 hover:text-indigo-700 dark:hover:bg-stone-800 dark:hover:text-indigo-300">
                  <span aria-hidden="true" className="text-stone-300 dark:text-stone-400">✍</span>
                  <span className="min-w-0 flex-1 truncate font-medium dark:text-stone-100">{d.title}</span>
                  <span className="shrink-0 text-xs text-stone-400 dark:text-stone-400">{d.deadline}</span>
                </a>
              </li>
            ))}
            {data.deadlines.length === 0 && (
              <li className="text-sm text-stone-400 dark:text-stone-400">
                Manuscript deadlines show up here. <Link to="/writing" className="text-indigo-600 hover:text-indigo-700 dark:text-indigo-400 dark:hover:text-indigo-300">Open Writing →</Link>
              </li>
            )}
          </ul>
        </section>

        <section className={section}>
          <h2 className={h2}>Upcoming milestones</h2>
          <ul className="space-y-1 text-sm">
            {data.milestones.map((m) => (
              <li key={m.url + m.title}>
                <a href={m.url} className="-mx-2 flex items-baseline gap-2 rounded px-2 py-1 hover:bg-stone-50 hover:text-indigo-700 dark:hover:bg-stone-800 dark:hover:text-indigo-300">
                  <span aria-hidden="true" className="text-stone-300 dark:text-stone-400">◆</span>
                  <span className="min-w-0 flex-1 truncate dark:text-stone-100">{m.title}</span>
                  <span className={`shrink-0 text-xs ${m.overdue ? "font-medium text-red-600 dark:text-red-300" : "text-stone-400 dark:text-stone-400"}`}>
                    {m.due_date}{m.overdue ? " · overdue" : ""}
                  </span>
                </a>
              </li>
            ))}
            {data.milestones.length === 0 && (
              <li className="text-sm text-stone-400 dark:text-stone-400">Nothing scheduled — add milestones inside a project plan.</li>
            )}
          </ul>
        </section>
      </div>
    </div>
  );
}
