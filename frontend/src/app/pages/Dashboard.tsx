import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api";

type Dash = {
  stats: Record<string, number>;
  inbox_count: number;
  active: {
    name: string; slug: string; url: string; color: string;
    phase: string | null; done: number; total: number; percent: number;
  }[];
  milestones: { title: string; project: string; due_date: string | null; overdue: boolean; url: string }[];
  deadlines: { title: string; deadline: string | null; url: string }[];
};

const card = "rounded border border-stone-200 bg-white px-4 py-3";

export default function Dashboard() {
  const { data, isLoading, error } = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => api<Dash>("/dashboard/"),
  });

  if (isLoading) return <p className="text-sm text-stone-400">Loading your day…</p>;
  if (error || !data) return <p className="text-sm text-red-600">Couldn't load the dashboard.</p>;

  return (
    <div>
      <h1 className="mb-6 text-2xl font-semibold tracking-tight">Today, everywhere</h1>

      <div className="mb-4 grid grid-cols-4 gap-4">
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

      <div className="grid grid-cols-2 gap-4">
        <section className="rounded border border-stone-200 bg-white p-5">
          <h2 className="mb-3 text-sm font-medium uppercase tracking-wide text-stone-400">Active projects</h2>
          <div className="space-y-3">
            {data.active.map((p) => (
              <Link key={p.slug} to={`/projects/${p.slug}`} className="block">
                <div className="mb-1 flex items-baseline justify-between text-sm">
                  <span className="font-medium">{p.name}</span>
                  <span className="text-xs text-stone-400">
                    {p.phase ? `${p.phase} · ` : ""}{p.done}/{p.total} milestones
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

        <section className="rounded border border-stone-200 bg-white p-5">
          <h2 className="mb-3 text-sm font-medium uppercase tracking-wide text-stone-400">Coming up</h2>
          <ul className="space-y-2 text-sm">
            {data.deadlines.map((d) => (
              <li key={d.url + d.title}>
                <a href={d.url} className="flex items-baseline gap-2 hover:text-indigo-700">
                  <span aria-hidden="true">✍</span>
                  <span className="min-w-0 flex-1 truncate font-medium">{d.title}</span>
                  <span className="shrink-0 text-xs text-stone-400">{d.deadline}</span>
                </a>
              </li>
            ))}
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
          </ul>
        </section>
      </div>
    </div>
  );
}
