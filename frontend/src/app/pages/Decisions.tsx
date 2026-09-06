/** Decision log: list + create + edit + delete (SPA slice 9; CRUD sweep 2026-09-06). */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Pencil, Trash2 } from "lucide-react";
import { api } from "../api";
import { Skeleton, SkeletonLines } from "../../components/Skeleton";
import { ErrorState } from "../../components/ErrorState";
import { confirmDialog, errorDialog } from "../../components/Dialog";
import { Kebab, useMenu, type MenuItem } from "../../components/Menu";

type Decision = { id: number; title: string; context: string; decision: string; alternatives: string; decided_on: string };
type Page<T> = { count: number; results: T[] };

const inputClass =
  "w-full rounded border border-stone-300 bg-white px-3 py-2 text-sm text-stone-800 placeholder:text-stone-400 focus:border-indigo-600 focus:outline-none focus:ring-1 focus:ring-indigo-600 dark:border-stone-700 dark:bg-stone-800 dark:text-stone-100";

function fmtDate(d: string) {
  const parsed = new Date(d + "T00:00");
  if (Number.isNaN(parsed.getTime())) return d;
  return parsed.toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

export default function Decisions() {
  const { slug } = useParams();
  const queryClient = useQueryClient();
  const [formOpen, setFormOpen] = useState(false);
  const [title, setTitle] = useState("");
  const [decision, setDecision] = useState("");
  const [context, setContext] = useState("");
  const [alternatives, setAlternatives] = useState("");
  const [decidedOn, setDecidedOn] = useState(new Date().toISOString().slice(0, 10));
  const [editing, setEditing] = useState<Decision | null>(null);
  const menu = useMenu();
  const reset = () => { setTitle(""); setDecision(""); setContext(""); setAlternatives(""); setDecidedOn(new Date().toISOString().slice(0, 10)); setEditing(null); setFormOpen(false); };
  const startEdit = (d: Decision) => { setEditing(d); setTitle(d.title); setDecision(d.decision); setContext(d.context); setAlternatives(d.alternatives ?? ""); setDecidedOn(d.decided_on); setFormOpen(true); window.scrollTo({ top: 0, behavior: "smooth" }); };

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["decisions", slug],
    queryFn: () => api<Page<Decision>>(`/decisions/?project=${slug}`),
  });

  const refresh = () => { queryClient.invalidateQueries({ queryKey: ["decisions", slug] }); queryClient.invalidateQueries({ queryKey: ["overview", slug] }); };
  const create = useMutation({
    mutationFn: () =>
      api(editing ? `/decisions/${editing.id}/` : "/decisions/", {
        method: editing ? "PATCH" : "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project: slug, title, decision, context, alternatives, decided_on: decidedOn }),
      }),
    onSuccess: () => { reset(); refresh(); },
    onError: (e) => void errorDialog("Couldn't save the decision", e),
  });
  const remove = useMutation({
    mutationFn: (id: number) => api(`/decisions/${id}/`, { method: "DELETE" }),
    onSuccess: () => { if (editing) reset(); refresh(); },
    onError: (e) => void errorDialog("Couldn't delete the decision", e),
  });
  const itemsFor = (d: Decision): MenuItem[] => [
    { label: "Edit…", icon: <Pencil className="h-3.5 w-3.5" />, onSelect: () => startEdit(d) },
    { label: "Delete…", icon: <Trash2 className="h-3.5 w-3.5" />, danger: true, onSelect: async () => { if (await confirmDialog({ title: `Delete “${d.title}”?`, body: "The record leaves the log for good.", danger: true, confirmLabel: "Delete decision" })) remove.mutate(d.id); } },
  ];

  if (isLoading)
    return (
      <div role="status" aria-label="Loading">
        <Skeleton className="mb-6 h-4 w-56" />
        <div className="mb-1 flex items-center justify-between">
          <Skeleton className="h-7 w-40" />
          <Skeleton className="h-8 w-32" />
        </div>
        <Skeleton className="mb-6 h-4 w-2/3" />
        <ol className="relative space-y-4 border-l border-stone-200 pl-6 dark:border-stone-800">
          {Array.from({ length: 3 }).map((_, i) => (
            <li key={i}>
              <div className="rounded border border-stone-200 bg-white p-5 dark:border-stone-800 dark:bg-stone-900">
                <Skeleton className="mb-3 h-4 w-1/2" />
                <SkeletonLines lines={2} />
              </div>
            </li>
          ))}
        </ol>
      </div>
    );
  if (error || !data) return <ErrorState message="Couldn't load decisions." onRetry={() => refetch()} />;

  const decisions = data?.results ?? [];

  return (
    <div>
      <nav className="mb-6 text-sm text-stone-500 dark:text-stone-400">
        <Link to="/projects" className="hover:text-indigo-700 hover:underline dark:hover:text-indigo-300">Projects</Link> /{" "}
        <Link to={`/projects/${slug}`} className="hover:text-indigo-700 hover:underline dark:hover:text-indigo-300">{slug}</Link>{" "}
        / <span className="text-stone-700 dark:text-stone-300">Decisions</span>
      </nav>

      <div className="mb-1 flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight text-stone-900 dark:text-stone-100">Decision log</h1>
        <button onClick={() => (formOpen ? reset() : setFormOpen(true))}
                className={
                  formOpen
                    ? "rounded border border-stone-300 bg-white px-3 py-1.5 text-sm font-medium text-stone-600 transition-colors hover:border-stone-400 dark:border-stone-700 dark:bg-stone-800 dark:text-stone-300"
                    : "rounded bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-indigo-700 active:scale-[.98]"
                }>
          {formOpen ? "Cancel" : "Record decision"}
        </button>
      </div>
      <p className="mb-6 text-sm text-stone-500 dark:text-stone-400">
        A kept record of what was decided, the context behind it, and the roads not taken.
      </p>

      {formOpen && (
        <form className="mb-8 space-y-4 rounded border border-stone-200 bg-white p-5 shadow-sm dark:border-stone-800 dark:bg-stone-900"
              onSubmit={(e) => { e.preventDefault(); if (title.trim() && decision.trim()) create.mutate(); }}>
          <div className="space-y-1.5">
            <label className="block text-xs font-medium uppercase tracking-wide text-stone-400 dark:text-stone-400">Decision</label>
            <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="What was decided (one line)"
                   aria-label="Decision title" className={inputClass} />
            <textarea value={decision} onChange={(e) => setDecision(e.target.value)} rows={3}
                      placeholder="The decision and why (markdown ok)" aria-label="Decision body"
                      className={inputClass} />
          </div>
          <div className="space-y-1.5">
            <label className="block text-xs font-medium uppercase tracking-wide text-stone-400 dark:text-stone-400">
              Context <span className="font-normal normal-case text-stone-300 dark:text-stone-400">— optional</span>
            </label>
            <textarea value={context} onChange={(e) => setContext(e.target.value)} rows={2}
                      placeholder="The situation that prompted this decision" aria-label="Decision context"
                      className={inputClass} />
          </div>
          <div className="space-y-1.5">
            <label className="block text-xs font-medium uppercase tracking-wide text-stone-400 dark:text-stone-400">
              Alternatives <span className="font-normal normal-case text-stone-300 dark:text-stone-400">— optional</span>
            </label>
            <textarea value={alternatives} onChange={(e) => setAlternatives(e.target.value)} rows={2}
                      placeholder="What was considered and why it was rejected" aria-label="Decision alternatives"
                      className={inputClass} />
          </div>
          <div className="flex flex-wrap items-center gap-3 border-t border-stone-100 pt-4 dark:border-stone-800">
            <button type="submit" disabled={create.isPending}
                    className="rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-indigo-700 active:scale-[.98] disabled:opacity-50">
              {create.isPending ? "Saving…" : editing ? "Save changes" : "Save decision"}
            </button>
            <label className="flex items-center gap-1.5 text-xs text-stone-400 dark:text-stone-400">Decided on <input type="date" value={decidedOn} onChange={(e) => setDecidedOn(e.target.value)} className="rounded border border-stone-300 bg-white px-1.5 py-0.5 text-xs text-stone-700 dark:border-stone-700 dark:bg-stone-800 dark:text-stone-200" aria-label="Decided on" /></label>
            {editing && <span className="text-xs text-stone-400">editing “{editing.title}”</span>}
          </div>
        </form>
      )}

      {decisions.length === 0 ? (
        <div className="rounded border border-dashed border-stone-300 bg-white p-10 text-center dark:border-stone-700 dark:bg-stone-900">
          <p className="mb-1 text-sm font-medium text-stone-600 dark:text-stone-300">No decisions recorded yet</p>
          <p className="mb-4 text-sm text-stone-400 dark:text-stone-400">
            Keep a running log of the choices that shaped this project — what you decided, why, and what you turned down.
          </p>
          <button onClick={() => setFormOpen(true)}
                  className="rounded bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white transition-colors hover:bg-indigo-700 active:scale-[.98]">
            Record your first decision
          </button>
        </div>
      ) : (
        <ol className="relative space-y-4 border-l border-stone-200 pl-6 dark:border-stone-800">
          {decisions.map((d) => (
            <li key={d.id} className="group relative" onContextMenu={(e) => menu.open(e, itemsFor(d))} data-testid="decision">
              <span aria-hidden="true"
                    className="absolute -left-[27px] top-1.5 h-2.5 w-2.5 rounded-full border-2 border-stone-50 bg-indigo-400 transition-colors group-hover:bg-indigo-600 dark:border-stone-950" />
              <article className={`rounded border bg-white p-5 transition-colors hover:border-stone-300 dark:bg-stone-900 ${editing?.id === d.id ? "border-indigo-300 dark:border-indigo-500/50" : "border-stone-200 dark:border-stone-800"}`}>
                <div className="flex items-baseline justify-between gap-3">
                  <h2 className="min-w-0 flex-1 text-sm font-medium text-stone-900 dark:text-stone-100">{d.title}</h2>
                  <time className="shrink-0 font-mono text-xs text-stone-400 dark:text-stone-400">{fmtDate(d.decided_on)}</time>
                  <Kebab items={itemsFor(d)} label={`Actions for ${d.title}`} className="-my-1 opacity-0 group-hover:opacity-100 focus:opacity-100" />
                </div>
                {d.context && (
                  <p className="mt-2 text-xs leading-relaxed text-stone-400 dark:text-stone-400">{d.context.slice(0, 240)}</p>
                )}
                {d.decision && (
                  <p className="mt-2 text-sm leading-relaxed text-stone-600 dark:text-stone-300">{d.decision.slice(0, 280)}</p>
                )}
                {d.alternatives && (
                  <p className="mt-2 text-xs leading-relaxed text-stone-400 dark:text-stone-500"><span className="font-medium uppercase tracking-wide">Rejected · </span>{d.alternatives.slice(0, 200)}</p>
                )}
              </article>
            </li>
          ))}
        </ol>
      )}
      {menu.element}
    </div>
  );
}
