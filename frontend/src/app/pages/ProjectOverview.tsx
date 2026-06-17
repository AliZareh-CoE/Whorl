import { useQuery } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import { Skeleton, SkeletonCard } from "../../components/Skeleton";
import { ErrorState } from "../../components/ErrorState";

type Overview = {
  project: { name: string; slug: string; description: string; status: string; color: string };
  current_phase: { name: string; status: string } | null;
  progress: { done: number; total: number; percent: number };
  next_milestones: { id: number; title: string; due_date: string | null; overdue: boolean; phase: string }[];
  counts: Record<string, number>;
  recent_documents: { id: number; title: string; added: string; url: string }[];
  recent_decisions: { id: number; title: string; decided_on: string }[];
};

const section = "rounded border border-stone-200 bg-white p-5 dark:border-stone-800 dark:bg-stone-900";
const h2 =
  "mb-3 flex items-baseline gap-2 text-sm font-medium uppercase tracking-wide text-stone-400 dark:text-stone-400";

const quickLinks = [
  { to: "plan", label: "Plan" },
  { to: "literature", label: "Literature" },
  { to: "documents", label: "Documents" },
  { to: "figures", label: "Figures" },
  { to: "files", label: "Files" },
  { to: "notes", label: "Notes" },
  { to: "research", label: "Research" },
  { to: "decisions", label: "Decisions" },
  { to: "graph", label: "Graph" },
  { to: "review", label: "Review" },
  { to: "timeline", label: "Timeline" },
];

export default function ProjectOverview() {
  const { slug } = useParams();
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["overview", slug],
    queryFn: () => api<Overview>(`/projects/${slug}/overview/`),
  });

  if (isLoading)
    return (
      <div role="status" aria-label="Loading" className="space-y-4">
        <Skeleton className="h-4 w-40" />
        <div className="flex items-center gap-3">
          <Skeleton className="h-3 w-3 rounded-full" />
          <Skeleton className="h-7 w-64" />
        </div>
        <SkeletonCard />
        <div className="grid grid-cols-3 gap-3 sm:grid-cols-4 lg:grid-cols-8">
          {Array.from({ length: 8 }).map((_, i) => (
            <Skeleton key={i} className="h-14" />
          ))}
        </div>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <SkeletonCard />
          <SkeletonCard />
        </div>
      </div>
    );
  if (error || !data)
    return <ErrorState message="Couldn't load this project." onRetry={() => refetch()} />;
  const { project, progress } = data;

  return (
    <div>
      <nav className="mb-6 text-sm text-stone-500 dark:text-stone-400">
        <Link
          to="/projects"
          className="hover:text-indigo-700 hover:underline dark:hover:text-indigo-300"
        >
          Projects
        </Link>
        <span className="px-1.5 text-stone-300 dark:text-stone-400">/</span>
        <span className="text-stone-700 dark:text-stone-300">{project.name}</span>
      </nav>

      <header className="mb-6">
        <div className="mb-1.5 flex items-center gap-3">
          <span
            aria-hidden="true"
            className="h-3 w-3 shrink-0 rounded-full"
            style={{ background: project.color }}
          />
          <h1 className="text-2xl font-semibold tracking-tight text-stone-900 dark:text-stone-100">
            {project.name}
          </h1>
          <span className="rounded bg-stone-100 px-2 py-0.5 text-xs font-medium uppercase tracking-wide text-stone-500 dark:bg-stone-800 dark:text-stone-300">
            {project.status}
          </span>
        </div>
        {project.description && (
          <p className="max-w-2xl text-sm leading-relaxed text-stone-500 dark:text-stone-400">
            {project.description}
          </p>
        )}
      </header>

      <div className="mb-4 rounded border border-stone-200 bg-white p-5 dark:border-stone-800 dark:bg-stone-900">
        <div className="mb-2 flex items-baseline justify-between gap-4 text-sm">
          <span className="font-medium text-stone-900 dark:text-stone-100">
            {data.current_phase ? data.current_phase.name : "No phases yet"}
          </span>
          <span className="shrink-0 text-xs text-stone-400 dark:text-stone-400">
            {progress.done}/{progress.total} milestones
          </span>
        </div>
        <div className="h-1.5 w-full overflow-hidden rounded-full bg-stone-100 dark:bg-stone-800">
          <div
            className="h-full rounded-full transition-[width] duration-500"
            style={{ width: `${progress.percent}%`, background: project.color }}
          />
        </div>
        <nav className="mt-4 flex flex-wrap gap-x-4 gap-y-2 text-xs text-stone-400 dark:text-stone-400">
          {quickLinks.map((l) => (
            <Link
              key={l.to}
              to={`/projects/${project.slug}/${l.to}`}
              className="transition-colors hover:text-indigo-700 dark:hover:text-indigo-300"
            >
              {l.label}
            </Link>
          ))}
        </nav>
      </div>

      <div className="mb-4 grid grid-cols-3 gap-3 sm:grid-cols-4 lg:grid-cols-8">
        {Object.entries(data.counts).map(([key, value]) => (
          <div
            key={key}
            className="rounded border border-stone-200 bg-white px-3 py-2.5 text-center transition-colors hover:border-stone-300 dark:border-stone-800 dark:bg-stone-900 dark:hover:border-stone-700"
          >
            <p className="text-lg font-semibold leading-none text-stone-900 dark:text-stone-100">{value}</p>
            <p className="mt-1 text-[10px] uppercase tracking-wide text-stone-400 dark:text-stone-400">{key}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <section className={section}>
          <h2 className={h2}>
            Next milestones
            {data.next_milestones.length > 0 && (
              <span className="text-stone-300 dark:text-stone-400">{data.next_milestones.length}</span>
            )}
          </h2>
          {data.next_milestones.length === 0 ? (
            <p className="text-sm text-stone-400 dark:text-stone-400">
              No upcoming milestones.{" "}
              <Link
                to={`/projects/${project.slug}/plan`}
                className="text-indigo-600 hover:underline dark:text-indigo-400"
              >
                Open the plan
              </Link>{" "}
              to add some.
            </p>
          ) : (
            <ul className="space-y-2.5 text-sm">
              {data.next_milestones.map((m) => (
                <li key={m.id} className="flex items-baseline gap-2.5">
                  <span aria-hidden="true" className="text-[10px] text-stone-300 dark:text-stone-400">◆</span>
                  <span className="min-w-0 flex-1 truncate text-stone-700 dark:text-stone-300">{m.title}</span>
                  {m.due_date && (
                    <span
                      className={`shrink-0 text-xs ${m.overdue ? "font-medium text-red-600 dark:text-red-300" : "text-stone-400 dark:text-stone-400"}`}
                    >
                      {m.due_date}
                      {m.overdue ? " · overdue" : ""}
                    </span>
                  )}
                </li>
              ))}
            </ul>
          )}
        </section>

        <div className="space-y-4">
          <section className={section}>
            <h2 className={h2}>
              Recent documents
              {data.recent_documents.length > 0 && (
                <span className="text-stone-300 dark:text-stone-400">{data.recent_documents.length}</span>
              )}
            </h2>
            {data.recent_documents.length === 0 ? (
              <p className="text-sm text-stone-400 dark:text-stone-400">
                Nothing uploaded yet.{" "}
                <Link
                  to={`/projects/${project.slug}/documents`}
                  className="text-indigo-600 hover:underline dark:text-indigo-400"
                >
                  Add a document
                </Link>
                .
              </p>
            ) : (
              <ul className="space-y-2 text-sm">
                {data.recent_documents.map((d) => (
                  <li key={d.id} className="flex items-baseline gap-2.5">
                    <a
                      href={d.url}
                      className="min-w-0 flex-1 truncate text-stone-700 hover:text-indigo-700 dark:text-stone-300 dark:hover:text-indigo-300"
                    >
                      {d.title}
                    </a>
                    <span className="shrink-0 text-xs text-stone-400 dark:text-stone-400">{d.added}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>
          <section className={section}>
            <h2 className={h2}>
              Recent decisions
              {data.recent_decisions.length > 0 && (
                <span className="text-stone-300 dark:text-stone-400">{data.recent_decisions.length}</span>
              )}
            </h2>
            {data.recent_decisions.length === 0 ? (
              <p className="text-sm text-stone-400 dark:text-stone-400">
                No decisions recorded.{" "}
                <Link
                  to={`/projects/${project.slug}/decisions`}
                  className="text-indigo-600 hover:underline dark:text-indigo-400"
                >
                  Record one
                </Link>
                .
              </p>
            ) : (
              <ul className="space-y-2 text-sm">
                {data.recent_decisions.map((d) => (
                  <li key={d.id} className="flex items-baseline gap-2.5">
                    <span className="min-w-0 flex-1 truncate text-stone-700 dark:text-stone-300">{d.title}</span>
                    <span className="shrink-0 text-xs text-stone-400 dark:text-stone-400">{d.decided_on}</span>
                  </li>
                ))}
              </ul>
            )}
          </section>
        </div>
      </div>
    </div>
  );
}
