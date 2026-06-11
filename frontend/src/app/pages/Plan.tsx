import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";

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
  done: "bg-green-50 text-green-700",
  in_progress: "bg-indigo-50 text-indigo-700",
  blocked: "bg-red-50 text-red-700",
  not_started: "bg-stone-100 text-stone-600",
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

  if (isLoading) return <p className="text-sm text-stone-400">Loading plan…</p>;
  if (error || !data) return <p className="text-sm text-red-600">Couldn't load the plan.</p>;

  return (
    <div>
      <nav className="mb-6 text-sm text-stone-500">
        <Link to="/projects" className="hover:underline">Projects</Link> /{" "}
        <Link to={`/projects/${slug}`} className="hover:underline">{data.project.name}</Link> / Plan
      </nav>
      <h1 className="mb-6 text-2xl font-semibold tracking-tight">Plan</h1>

      <div className="space-y-4">
        {data.phases.map((phase) => {
          const done = phase.milestones.filter((m) => m.completed_at).length;
          return (
            <section key={phase.id} className="rounded border border-stone-200 bg-white p-5">
              <div className="mb-2 flex items-baseline gap-3">
                <span className="text-xs text-stone-400">{phase.order}</span>
                <h2 className="font-medium">{phase.name}</h2>
                <span className={`rounded px-2 py-0.5 text-xs ${statusCls[phase.status] ?? statusCls.not_started}`}>
                  {phase.status.replace("_", " ")}
                </span>
              </div>
              <div className="mb-1 text-xs text-stone-500">
                {done}/{phase.milestones.length} milestones
              </div>
              <div className="mb-3 h-1.5 w-full rounded-full bg-stone-100">
                <div
                  className="h-1.5 rounded-full transition-[width] duration-300"
                  style={{ width: `${phase.progress}%`, background: data.project.color }}
                />
              </div>

              <ul className="divide-y divide-stone-100">
                {phase.milestones.map((m) => (
                  <li key={m.id} className="py-2">
                    <div className="flex items-center gap-3">
                      <button
                        type="button"
                        aria-label="Toggle milestone"
                        onClick={() => toggleMilestone.mutate(m)}
                        className={`relative flex h-5 w-5 shrink-0 items-center justify-center rounded border text-xs after:absolute after:-inset-2.5 after:content-[''] ${
                          m.completed_at
                            ? "border-green-600 bg-green-600 text-white"
                            : "border-stone-300 bg-white text-transparent hover:border-stone-400"
                        }`}
                      >
                        ✓
                      </button>
                      <span className={`text-sm ${m.completed_at ? "text-stone-400 line-through" : ""}`}>
                        {m.title}
                      </span>
                      {m.due_date && (
                        <span className={`text-xs ${m.overdue && !m.completed_at ? "font-medium text-red-600" : "text-stone-400"}`}>
                          due {m.due_date}
                          {m.overdue && !m.completed_at ? " · overdue" : ""}
                        </span>
                      )}
                    </div>
                    {m.tasks.length > 0 && (
                      <ul className="ml-7 mt-1 space-y-1">
                        {m.tasks.map((t) => (
                          <li key={t.id} className="flex items-center gap-2 text-sm">
                            <button
                              type="button"
                              aria-label="Toggle task"
                              onClick={() => toggleTask.mutate(t)}
                              className={`relative flex h-4 w-4 shrink-0 items-center justify-center rounded border text-[10px] after:absolute after:-inset-2.5 after:content-[''] ${
                                t.done
                                  ? "border-stone-400 bg-stone-400 text-white"
                                  : "border-stone-300 bg-white text-transparent hover:border-stone-400"
                              }`}
                            >
                              ✓
                            </button>
                            <span className={t.done ? "text-stone-400 line-through" : ""}>{t.title}</span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </li>
                ))}
                {phase.milestones.length === 0 && (
                  <li className="py-2 text-sm text-stone-400">No milestones yet.</li>
                )}
              </ul>
            </section>
          );
        })}
      </div>
      <p className="mt-4 text-xs text-stone-400">
        Editing phases and milestones still lives on the{" "}
        <a href={`/projects/${slug}/plan/`} className="underline hover:text-indigo-700">classic plan page ↗</a>
      </p>
    </div>
  );
}
