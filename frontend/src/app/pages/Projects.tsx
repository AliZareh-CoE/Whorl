import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { ErrorState } from "../../components/ErrorState";
import { api } from "../api";

type Project = {
  name: string;
  slug: string;
  status: string;
  description: string;
  color: string;
};
type Page<T> = { count: number; results: T[] };

const statusTone: Record<string, string> = {
  ACTIVE: "text-emerald-700",
  PLANNING: "text-indigo-700",
  PAUSED: "text-amber-700",
  COMPLETE: "text-stone-600",
  ARCHIVED: "text-stone-400",
};

export default function Projects() {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["projects"],
    queryFn: () => api<Page<Project>>("/projects/"),
  });

  if (isLoading) return <p className="text-sm text-stone-400 dark:text-stone-400">Loading projects…</p>;
  if (error || !data) return <ErrorState message="Couldn't load projects." onRetry={() => refetch()} />;

  const projects = data?.results ?? [];

  return (
    <div>
      <div className="mb-6 flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight text-stone-900 dark:text-stone-100">Projects</h1>
          <p className="mt-1 text-sm text-stone-500 dark:text-stone-400">
            {projects.length === 0
              ? "Every object in Atlas lives inside a project."
              : `${projects.length} ${projects.length === 1 ? "project" : "projects"}`}
          </p>
        </div>
        <Link
          to="/projects/new"
          className="shrink-0 rounded bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-indigo-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2"
        >
          New project
        </Link>
      </div>

      {projects.length === 0 ? (
        <div className="rounded border border-dashed border-stone-300 bg-white p-10 text-center dark:border-stone-700 dark:bg-stone-900">
          <p className="mb-1 text-sm font-medium text-stone-700 dark:text-stone-300">No projects yet</p>
          <p className="mb-5 text-sm text-stone-500 dark:text-stone-400">
            A project is the home for your plan, literature, notes, and decisions.
          </p>
          <Link
            to="/projects/new"
            className="inline-block rounded bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-indigo-700 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-2"
          >
            Create your first project
          </Link>
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {projects.map((p) => (
            <Link
              key={p.slug}
              to={`/projects/${p.slug}`}
              className="group relative flex flex-col overflow-hidden rounded border border-stone-200 bg-white p-5 pl-6 transition-colors hover:border-stone-300 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 dark:border-stone-800 dark:bg-stone-900"
            >
              <span
                aria-hidden="true"
                className="absolute inset-y-0 left-0 w-1"
                style={{ background: p.color }}
              />
              <div className="mb-1.5 flex items-start justify-between gap-3">
                <h2 className="min-w-0 truncate font-medium text-stone-900 group-hover:text-indigo-700 dark:text-stone-100 dark:group-hover:text-indigo-400">
                  {p.name}
                </h2>
                <span
                  className={`shrink-0 text-[10px] font-medium uppercase tracking-wide ${
                    statusTone[p.status] ?? "text-stone-500"
                  }`}
                >
                  {p.status.toLowerCase()}
                </span>
              </div>
              {p.description ? (
                <p className="line-clamp-2 text-sm leading-relaxed text-stone-500 dark:text-stone-400">
                  {p.description}
                </p>
              ) : (
                <p className="text-sm italic text-stone-400 dark:text-stone-400">No description</p>
              )}
            </Link>
          ))}
        </div>
      )}
    </div>
  );
}
