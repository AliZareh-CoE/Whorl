import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api, petReact } from "../api";

type Task = { id: number; title: string; done: boolean; due_date?: string | null };
type Milestone = {
  id: number;
  title: string;
  due_date: string | null;
  completed_at: string | null;
  overdue: boolean;
  tasks: Task[];
};
type Phase = {
  id: number;
  name: string;
  order: number;
  status: string;
  progress: number;
  milestones: Milestone[];
};
type PlanData = { project: { name: string; slug: string; color: string }; phases: Phase[] };

const statusCls: Record<string, string> = {
  done: "bg-green-50 text-green-700 dark:bg-green-500/10 dark:text-green-300",
  in_progress: "bg-indigo-50 text-indigo-700 dark:bg-indigo-500/10 dark:text-indigo-300",
  blocked: "bg-red-50 text-red-700 dark:bg-red-500/10 dark:text-red-300",
  not_started: "bg-stone-100 text-stone-600 dark:bg-stone-800 dark:text-stone-300",
};

export default function Plan() {
  const { slug } = useParams();
  const queryClient = useQueryClient();
  const { data, isLoading, error } = useQuery({
    queryKey: ["plan", slug],
    queryFn: () => api<PlanData>(`/projects/${slug}/plan/`),
  });

  function patchPlan(update: (plan: PlanData) => PlanData) {
    queryClient.setQueryData<PlanData>(["plan", slug], (old) => (old ? update(old) : old));
  }

  const toggleMilestone = useMutation({
    mutationFn: (m: Milestone) =>
      api(`/milestones/${m.id}/`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          completed_at: m.completed_at ? null : new Date().toISOString(),
        }),
      }),
    onMutate: async (m) => {
      // optimistic: flip locally, progress recomputes from the next refetch
      if (!m.completed_at) petReact("milestone");
      patchPlan((plan) => ({
        ...plan,
        phases: plan.phases.map((ph) => ({
          ...ph,
          milestones: ph.milestones.map((x) =>
            x.id === m.id
              ? { ...x, completed_at: x.completed_at ? null : new Date().toISOString() }
              : x,
          ),
        })),
      }));
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["plan", slug] });
      queryClient.invalidateQueries({ queryKey: ["overview", slug] });
      queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    },
  });

  const toggleTask = useMutation({
    mutationFn: (t: Task) =>
      api(`/tasks/${t.id}/`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ done: !t.done }),
      }),
    onMutate: async (t) => {
      patchPlan((plan) => ({
        ...plan,
        phases: plan.phases.map((ph) => ({
          ...ph,
          milestones: ph.milestones.map((m) => ({
            ...m,
            tasks: m.tasks.map((x) => (x.id === t.id ? { ...x, done: !x.done } : x)),
          })),
        })),
      }));
    },
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["plan", slug] }),
  });

  if (isLoading) return <p className="text-sm text-stone-400 dark:text-stone-400">Loading plan…</p>;
  if (error || !data)
    return <p className="text-sm text-red-600 dark:text-red-300">Couldn't load the plan.</p>;

  const totalMilestones = data.phases.reduce((n, p) => n + p.milestones.length, 0);
  const doneMilestones = data.phases.reduce(
    (n, p) => n + p.milestones.filter((m) => m.completed_at).length,
    0,
  );

  return (
    <div>
      <nav className="mb-6 text-sm text-stone-500 dark:text-stone-400">
        <Link to="/projects" className="hover:underline">Projects</Link> /{" "}
        <Link to={`/projects/${slug}`} className="hover:underline">{data.project.name}</Link> / Plan
      </nav>

      <div className="mb-6 flex items-baseline justify-between gap-4">
        <h1 className="text-2xl font-semibold tracking-tight">Plan</h1>
        {totalMilestones > 0 && (
          <span className="shrink-0 text-sm text-stone-400 dark:text-stone-400">
            {doneMilestones}/{totalMilestones} milestones complete
          </span>
        )}
      </div>

      {data.phases.length === 0 ? (
        <div className="rounded border border-dashed border-stone-300 bg-white p-10 text-center dark:border-stone-700 dark:bg-stone-900">
          <p className="mb-1 text-sm font-medium text-stone-600 dark:text-stone-300">No phases yet</p>
          <p className="mb-4 text-sm text-stone-400 dark:text-stone-400">
            A plan is built from ordered phases, each with its own milestones.
          </p>
          <a
            href={`/projects/${slug}/plan/`}
            className="inline-block rounded border border-stone-300 bg-white px-3 py-1.5 text-sm text-stone-700 hover:border-stone-400 hover:text-indigo-700 dark:border-stone-700 dark:bg-stone-900 dark:text-stone-300 dark:hover:text-indigo-300"
          >
            Build the plan ↗
          </a>
        </div>
      ) : (
        <div className="space-y-4">
          {data.phases.map((phase) => {
            const done = phase.milestones.filter((m) => m.completed_at).length;
            return (
              <section key={phase.id} className="rounded border border-stone-200 bg-white p-5 dark:border-stone-800 dark:bg-stone-900">
                <div className="mb-3 flex items-baseline gap-3">
                  <span className="font-mono text-xs text-stone-300 dark:text-stone-400">{phase.order}</span>
                  <h2 className="min-w-0 flex-1 font-medium text-stone-900 dark:text-stone-100">{phase.name}</h2>
                  <span className={`shrink-0 rounded px-2 py-0.5 text-xs ${statusCls[phase.status] ?? statusCls.not_started}`}>
                    {phase.status.replace("_", " ")}
                  </span>
                </div>

                <div className="mb-1 text-xs text-stone-400 dark:text-stone-400">
                  {done}/{phase.milestones.length} milestones
                </div>
                <div className="mb-4 h-1.5 w-full overflow-hidden rounded-full bg-stone-100 dark:bg-stone-800">
                  <div
                    className="h-1.5 rounded-full transition-[width] duration-300"
                    style={{ width: `${phase.progress}%`, background: data.project.color }}
                  />
                </div>

                <ul className="divide-y divide-stone-100 dark:divide-stone-800">
                  {phase.milestones.map((m) => {
                    const isOverdue = m.overdue && !m.completed_at;
                    return (
                      <li key={m.id} className="py-2.5">
                        <div className="flex items-center gap-3">
                          <button
                            type="button"
                            aria-label="Toggle milestone"
                            onClick={() => toggleMilestone.mutate(m)}
                            className={`relative flex h-5 w-5 shrink-0 items-center justify-center rounded border text-xs transition-colors after:absolute after:-inset-2.5 after:content-[''] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-1 ${
                              m.completed_at
                                ? "border-indigo-600 bg-indigo-600 text-white"
                                : "border-stone-300 bg-white text-transparent hover:border-indigo-400 dark:border-stone-700 dark:bg-stone-900 dark:hover:border-indigo-400"
                            }`}
                          >
                            ✓
                          </button>
                          <span className={`min-w-0 flex-1 text-sm ${m.completed_at ? "text-stone-400 line-through dark:text-stone-400" : "text-stone-800 dark:text-stone-300"}`}>
                            {m.title}
                          </span>
                          {m.due_date && (
                            <span
                              className={`shrink-0 rounded px-1.5 py-0.5 text-xs ${
                                isOverdue
                                  ? "bg-red-50 font-medium text-red-600 dark:bg-red-500/10 dark:text-red-300"
                                  : "text-stone-400 dark:text-stone-400"
                              }`}
                            >
                              {isOverdue ? "overdue · " : "due "}
                              {m.due_date}
                            </span>
                          )}
                        </div>
                        {m.tasks.length > 0 && (
                          <ul className="ml-2.5 mt-2 space-y-1.5 border-l border-stone-100 pl-4 dark:border-stone-800">
                            {m.tasks.map((t) => (
                              <li key={t.id} className="flex items-center gap-2.5 text-sm">
                                <button
                                  type="button"
                                  aria-label="Toggle task"
                                  onClick={() => toggleTask.mutate(t)}
                                  className={`relative flex h-4 w-4 shrink-0 items-center justify-center rounded border text-[10px] transition-colors after:absolute after:-inset-2.5 after:content-[''] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-1 ${
                                    t.done
                                      ? "border-stone-400 bg-stone-400 text-white dark:border-stone-500 dark:bg-stone-500"
                                      : "border-stone-300 bg-white text-transparent hover:border-stone-400 dark:border-stone-700 dark:bg-stone-900 dark:hover:border-stone-500"
                                  }`}
                                >
                                  ✓
                                </button>
                                <span className={`min-w-0 flex-1 ${t.done ? "text-stone-400 line-through dark:text-stone-400" : "text-stone-700 dark:text-stone-300"}`}>
                                  {t.title}
                                </span>
                                {t.due_date && (
                                  <span className="shrink-0 text-xs text-stone-400 dark:text-stone-400">due {t.due_date}</span>
                                )}
                              </li>
                            ))}
                          </ul>
                        )}
                      </li>
                    );
                  })}
                  {phase.milestones.length === 0 && (
                    <li className="py-2.5 text-sm text-stone-400 dark:text-stone-400">No milestones in this phase yet.</li>
                  )}
                </ul>
              </section>
            );
          })}
        </div>
      )}

      <p className="mt-4 text-xs text-stone-400 dark:text-stone-400">
        Editing phases and milestones still lives on the{" "}
        <a href={`/projects/${slug}/plan/`} className="underline hover:text-indigo-700 dark:hover:text-indigo-300">classic plan page ↗</a>
      </p>
    </div>
  );
}
