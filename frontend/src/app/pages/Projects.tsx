import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api";

type Project = { name: string; slug: string; status: string; description: string };
type Page<T> = { count: number; results: T[] };

export default function Projects() {
  const { data, isLoading } = useQuery({
    queryKey: ["projects"],
    queryFn: () => api<Page<Project>>("/projects/"),
  });

  if (isLoading) return <p className="text-sm text-stone-400">Loading projects…</p>;
  return (
    <div>
      <div className="mb-6 flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Projects</h1>
        <Link to="/projects/new"
              className="rounded bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700">
          New project
        </Link>
      </div>
      <div className="space-y-3">
        {data?.results.map((p) => (
          <Link key={p.slug} to={`/projects/${p.slug}`}
             className="block rounded border border-stone-200 bg-white p-5 hover:border-stone-300">
            <div className="flex items-center gap-3">
              <span className="font-medium">{p.name}</span>
              <span className="rounded bg-stone-100 px-2 py-0.5 text-xs text-stone-500">{p.status}</span>
            </div>
            {p.description && <p className="mt-1 truncate text-sm text-stone-500">{p.description}</p>}
          </Link>
        ))}
      </div>
    </div>
  );
}
