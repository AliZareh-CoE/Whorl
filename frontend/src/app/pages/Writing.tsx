/** Writing board + manuscript detail (SPA slice 7). */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import { Skeleton, SkeletonLines } from "../../components/Skeleton";

type Event = { id: number; kind: string; date: string; notes: string };
type Manuscript = {
  id: number;
  project: string;
  project_name: string;
  title: string;
  status: string;
  target_venue: string;
  deadline: string | null;
  abstract: string;
  events: Event[];
};
type Page<T> = { count: number; results: T[] };

const COLUMNS: [string, string][] = [
  ["idea", "Idea"],
  ["outlining", "Outlining"],
  ["drafting", "Drafting"],
  ["internal_review", "Internal review"],
  ["submitted", "Submitted"],
  ["under_review", "Under review"],
  ["revision", "Revision"],
  ["accepted", "Accepted"],
  ["published", "Published"],
  ["shelved", "Shelved"],
];

const h2 = "mb-3 text-sm font-medium uppercase tracking-wide text-stone-400 dark:text-stone-400";

/** Whole-day countdown to a deadline; null when none. */
function daysUntil(deadline: string | null): number | null {
  if (!deadline) return null;
  const due = new Date(deadline + "T00:00");
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  return Math.round((due.getTime() - today.getTime()) / 86_400_000);
}

/** Calm deadline phrasing; restrained red only when overdue or within a week. */
function deadlineLabel(deadline: string | null): { text: string; urgent: boolean } | null {
  const days = daysUntil(deadline);
  if (days === null) return null;
  if (days < 0) return { text: `${-days}d overdue`, urgent: true };
  if (days === 0) return { text: "due today", urgent: true };
  if (days <= 7) return { text: `${days}d left`, urgent: true };
  return { text: `${days}d left`, urgent: false };
}

export function WritingBoard() {
  const { data, isLoading } = useQuery({
    queryKey: ["manuscripts"],
    queryFn: () => api<Page<Manuscript>>("/manuscripts/"),
  });

  if (isLoading)
    return (
      <div role="status" aria-label="Loading">
        <Skeleton className="mb-1 h-7 w-40" />
        <Skeleton className="mb-6 h-4 w-64" />
        <div className="flex gap-5 overflow-x-auto pb-4">
          {Array.from({ length: 3 }).map((_, col) => (
            <section key={col} className="w-64 shrink-0">
              <Skeleton className="mb-3 h-3 w-24" />
              <div className="space-y-2.5">
                {Array.from({ length: 2 }).map((_, c) => (
                  <div key={c} className="rounded border border-stone-200 bg-white p-4 dark:border-stone-800 dark:bg-stone-900">
                    <Skeleton className="mb-2 h-4 w-3/4" />
                    <Skeleton className="h-3 w-1/2" />
                  </div>
                ))}
              </div>
            </section>
          ))}
        </div>
      </div>
    );
  const rows = data?.results ?? [];
  const populated = COLUMNS.filter(([key]) => rows.some((m) => m.status === key));

  return (
    <div>
      <h1 className="mb-1 text-2xl font-semibold tracking-tight">Writing</h1>
      <p className="mb-6 text-sm text-stone-500 dark:text-stone-400">
        Manuscripts move idea → published.
      </p>
      {rows.length === 0 ? (
        <div className="rounded border border-dashed border-stone-300 bg-white p-10 text-center dark:border-stone-700 dark:bg-stone-900">
          <p className="mb-1 text-sm font-medium text-stone-600 dark:text-stone-300">
            No manuscripts yet
          </p>
          <p className="text-sm text-stone-400 dark:text-stone-400">
            A manuscript tracks one paper from idea through to publication, with its own
            bibliography and submission timeline.
          </p>
          <p className="mt-3 text-sm text-stone-400 dark:text-stone-400">
            Create one from a project's classic writing page ↗
          </p>
        </div>
      ) : (
        <div className="flex gap-5 overflow-x-auto pb-4">
          {populated.map(([key, label]) => {
            const items = rows.filter((m) => m.status === key);
            return (
              <section key={key} className="w-64 shrink-0">
                <h2 className="mb-3 flex items-baseline gap-2 text-sm font-medium uppercase tracking-wide text-stone-400 dark:text-stone-400">
                  {label}
                  <span className="text-stone-300 dark:text-stone-400">{items.length}</span>
                </h2>
                <div className="space-y-2.5">
                  {items.map((m) => {
                    const dl = deadlineLabel(m.deadline);
                    return (
                      <Link
                        key={m.id}
                        to={`/manuscripts/${m.id}`}
                        className="block rounded border border-stone-200 bg-white p-4 text-sm transition-colors hover:border-stone-300 hover:bg-stone-50 dark:border-stone-800 dark:bg-stone-900 dark:hover:bg-stone-800"
                      >
                        <span className="font-medium text-stone-900 dark:text-stone-100">
                          {m.title}
                        </span>
                        <p className="mt-1 text-xs text-stone-400 dark:text-stone-400">
                          {m.project_name}
                          {m.target_venue ? ` · ${m.target_venue}` : ""}
                        </p>
                        {dl && (
                          <p
                            className={`mt-2 text-xs ${
                              dl.urgent
                                ? "font-medium text-red-600 dark:text-red-300"
                                : "text-stone-400 dark:text-stone-400"
                            }`}
                          >
                            {dl.text}
                          </p>
                        )}
                      </Link>
                    );
                  })}
                </div>
              </section>
            );
          })}
        </div>
      )}
    </div>
  );
}

export function ManuscriptDetail() {
  const { id } = useParams();
  const queryClient = useQueryClient();
  const { data: m, isLoading } = useQuery({
    queryKey: ["manuscript", id],
    queryFn: () => api<Manuscript>(`/manuscripts/${id}/`),
  });

  const setStatus = useMutation({
    mutationFn: (status: string) =>
      api(`/manuscripts/${id}/`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status }),
      }),
    onMutate: (status) => {
      queryClient.setQueryData<Manuscript>(["manuscript", id], (old) =>
        old ? { ...old, status } : old,
      );
    },
    onSettled: () => {
      queryClient.invalidateQueries({ queryKey: ["manuscript", id] });
      queryClient.invalidateQueries({ queryKey: ["manuscripts"] });
    },
  });

  if (isLoading || !m)
    return (
      <div role="status" aria-label="Loading" className="space-y-4">
        <Skeleton className="h-4 w-32" />
        <Skeleton className="h-7 w-2/3" />
        <Skeleton className="h-4 w-48" />
        <div className="max-w-2xl rounded border border-stone-200 bg-white p-5 dark:border-stone-800 dark:bg-stone-900">
          <SkeletonLines lines={3} />
        </div>
        <div className="max-w-xl rounded border border-stone-200 bg-white p-5 dark:border-stone-800 dark:bg-stone-900">
          <Skeleton className="mb-3 h-3 w-40" />
          <SkeletonLines lines={2} />
        </div>
      </div>
    );

  const dl = deadlineLabel(m.deadline);

  return (
    <div>
      <nav className="mb-6 text-sm text-stone-500 dark:text-stone-400">
        <Link to="/writing" className="transition-colors hover:underline">
          Writing
        </Link>{" "}
        / {m.title}
      </nav>
      <div className="mb-2 flex flex-wrap items-center gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">{m.title}</h1>
        <select
          value={m.status}
          onChange={(e) => setStatus.mutate(e.target.value)}
          aria-label="Manuscript status"
          className="rounded border border-stone-300 bg-white px-2 py-1 text-xs text-stone-600 transition-colors hover:border-stone-400 focus:border-indigo-600 focus:outline-none dark:border-stone-700 dark:bg-stone-800 dark:text-stone-300"
        >
          {COLUMNS.map(([v, l]) => (
            <option key={v} value={v}>
              {l}
            </option>
          ))}
        </select>
      </div>
      <p className="mb-4 flex flex-wrap items-center gap-x-2 gap-y-1 text-sm text-stone-500 dark:text-stone-400">
        <span>{m.project_name}</span>
        {m.target_venue && <span className="text-stone-300 dark:text-stone-400">·</span>}
        {m.target_venue && <span>{m.target_venue}</span>}
        {dl && <span className="text-stone-300 dark:text-stone-400">·</span>}
        {dl && (
          <span
            className={
              dl.urgent
                ? "font-medium text-red-600 dark:text-red-300"
                : "text-stone-500 dark:text-stone-400"
            }
          >
            deadline {m.deadline} ({dl.text})
          </span>
        )}
      </p>
      {m.abstract && (
        <div className="mb-4 max-w-2xl rounded border border-stone-200 bg-white p-5 text-sm leading-relaxed text-stone-600 dark:border-stone-800 dark:bg-stone-900 dark:text-stone-300">
          {m.abstract}
        </div>
      )}
      <div className="mb-6 flex flex-wrap gap-4 text-xs text-stone-400 dark:text-stone-400">
        <a
          href={`/projects/${m.project}/writing/${m.id}/editor/`}
          className="underline-offset-2 transition-colors hover:text-indigo-700 hover:underline dark:hover:text-indigo-300"
        >
          LaTeX editor ↗
        </a>
        <a
          href={`/projects/${m.project}/writing/${m.id}/`}
          className="underline-offset-2 transition-colors hover:text-indigo-700 hover:underline dark:hover:text-indigo-300"
        >
          bibliography & cite check ↗
        </a>
      </div>

      <section className="max-w-xl rounded border border-stone-200 bg-white p-5 dark:border-stone-800 dark:bg-stone-900">
        <h2 className={h2}>Submission timeline</h2>
        {m.events.length === 0 ? (
          <p className="text-sm text-stone-400 dark:text-stone-400">
            No submission events yet — they appear here as the manuscript progresses.
          </p>
        ) : (
          <ol className="relative space-y-5 border-l border-stone-200 pl-5 dark:border-stone-700">
            {m.events.map((e) => (
              <li key={e.id} className="text-sm">
                <span className="absolute -left-[5px] mt-1 h-2.5 w-2.5 rounded-full border-2 border-white bg-indigo-500 dark:border-stone-900 dark:bg-indigo-500/10" />
                <div className="flex items-baseline gap-2">
                  <span className="font-medium capitalize text-stone-900 dark:text-stone-100">
                    {e.kind.replace(/_/g, " ")}
                  </span>
                  <span className="text-xs text-stone-400 dark:text-stone-400">{e.date}</span>
                </div>
                {e.notes && (
                  <p className="mt-1 text-xs leading-relaxed text-stone-500 dark:text-stone-400">
                    {e.notes}
                  </p>
                )}
              </li>
            ))}
          </ol>
        )}
      </section>
    </div>
  );
}
