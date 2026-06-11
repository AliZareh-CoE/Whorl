/** Writing board + manuscript detail (SPA slice 7). */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";

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

export function WritingBoard() {
  const { data, isLoading } = useQuery({
    queryKey: ["manuscripts"],
    queryFn: () => api<Page<Manuscript>>("/manuscripts/"),
  });

  if (isLoading) return <p className="text-sm text-stone-400">Loading manuscripts…</p>;
  const rows = data?.results ?? [];
  const populated = COLUMNS.filter(([key]) => rows.some((m) => m.status === key));

  return (
    <div>
      <h1 className="mb-6 text-2xl font-semibold tracking-tight">Writing</h1>
      {rows.length === 0 ? (
        <p className="rounded border border-dashed border-stone-300 bg-white p-10 text-center text-sm text-stone-400">
          Manuscripts move idea → published. Create one from a project's classic writing page ↗
        </p>
      ) : (
        <div className="flex gap-4 overflow-x-auto pb-2">
          {populated.map(([key, label]) => (
            <section key={key} className="w-64 shrink-0">
              <h2 className="mb-2 text-[10px] font-medium uppercase tracking-wide text-stone-400">
                {label}
              </h2>
              <div className="space-y-2">
                {rows.filter((m) => m.status === key).map((m) => (
                  <Link key={m.id} to={`/manuscripts/${m.id}`}
                        className="block rounded border border-stone-200 bg-white p-3 text-sm hover:border-stone-300">
                    <span className="font-medium">{m.title}</span>
                    <p className="mt-0.5 text-xs text-stone-400">
                      {m.project_name}
                      {m.target_venue ? ` · ${m.target_venue}` : ""}
                      {m.deadline ? ` · due ${m.deadline}` : ""}
                    </p>
                  </Link>
                ))}
              </div>
            </section>
          ))}
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

  if (isLoading || !m) return <p className="text-sm text-stone-400">Loading manuscript…</p>;

  return (
    <div>
      <nav className="mb-6 text-sm text-stone-500">
        <Link to="/writing" className="hover:underline">Writing</Link> / {m.title}
      </nav>
      <div className="mb-1 flex items-center gap-3">
        <h1 className="text-2xl font-semibold tracking-tight">{m.title}</h1>
        <select
          value={m.status}
          onChange={(e) => setStatus.mutate(e.target.value)}
          aria-label="Manuscript status"
          className="rounded border border-stone-300 bg-white px-2 py-1 text-xs"
        >
          {COLUMNS.map(([v, l]) => <option key={v} value={v}>{l}</option>)}
        </select>
      </div>
      <p className="mb-4 text-sm text-stone-500">
        {m.project_name}
        {m.target_venue ? ` · ${m.target_venue}` : ""}
        {m.deadline ? ` · deadline ${m.deadline}` : ""}
      </p>
      {m.abstract && (
        <div className="mb-4 max-w-2xl rounded border border-stone-200 bg-white p-4 text-sm text-stone-600">
          {m.abstract}
        </div>
      )}
      <div className="mb-4 flex gap-3 text-xs text-stone-400">
        <a href={`/projects/${m.project}/writing/${m.id}/editor/`} className="underline hover:text-indigo-700">
          LaTeX editor ↗
        </a>
        <a href={`/projects/${m.project}/writing/${m.id}/`} className="underline hover:text-indigo-700">
          bibliography & cite check ↗
        </a>
      </div>

      <section className="max-w-xl rounded border border-stone-200 bg-white p-5">
        <h2 className="mb-3 text-[10px] font-medium uppercase tracking-wide text-stone-400">
          Submission timeline
        </h2>
        {m.events.length === 0 ? (
          <p className="text-sm text-stone-400">No events yet.</p>
        ) : (
          <ol className="relative space-y-4 border-l border-stone-200 pl-4">
            {m.events.map((e) => (
              <li key={e.id} className="text-sm">
                <span className="absolute -left-[5px] mt-1.5 h-2.5 w-2.5 rounded-full border border-white bg-indigo-400" />
                <span className="font-medium">{e.kind.replace(/_/g, " ")}</span>
                <span className="ml-2 text-xs text-stone-400">{e.date}</span>
                {e.notes && <p className="mt-0.5 text-xs text-stone-500">{e.notes}</p>}
              </li>
            ))}
          </ol>
        )}
      </section>
    </div>
  );
}
