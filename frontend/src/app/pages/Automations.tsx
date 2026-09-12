/** Bots with run-history charts (SPA slice 10). */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { api } from "../api";
import { queryGate } from "../../components/QueryBoundary";

type Run = { id: number; ok: boolean; count: number | null; captures: number; started_at: string };
type Bot = { slug: string; name: string; description: string; enabled: boolean; last_result: string; runs: Run[] };

function RunChart({ runs }: { runs: Run[] }) {
  if (runs.length < 2) return null;
  const ordered = [...runs].reverse();
  const top = Math.max(...ordered.map((r) => r.count ?? 0), 1);
  return (
    <div className="mt-4">
      <p className="mb-1.5 text-xs font-medium uppercase tracking-wide text-stone-400">Run history</p>
      <div className="flex h-10 items-end gap-px" aria-label="Run history chart">
        {ordered.map((r, i) => {
          const title = `${r.started_at.slice(0, 16).replace("T", " ")} — ${r.ok ? r.count ?? 0 : "failed"}`;
          const cls = `block w-2.5 rounded-t transition-colors ${r.ok ? "bg-indigo-200 hover:bg-indigo-400" : "bg-red-300 hover:bg-red-500"}`;
          const style = { height: `${Math.max(8, Math.round(((r.count ?? 0) * 100) / top))}%` };
          // #423: a bar that filed something opens the Inbox filtered to that run
          return r.ok && r.captures > 0
            ? <Link key={r.id ?? i} to={`/inbox?run=${r.id}`} title={`${title} — ${r.captures} filed in the Inbox, click to see them`} className={cls} style={style} data-testid="run-bar" />
            : <div key={r.id ?? i} title={title} className={cls} style={style} />;
        })}
      </div>
    </div>
  );
}

function StatusChip({ enabled }: { enabled: boolean }) {
  return (
    <span className={`inline-flex items-center gap-1.5 rounded-full px-2.5 py-0.5 text-xs font-medium ${
      enabled ? "bg-green-50 text-green-700 dark:bg-green-500/10 dark:text-green-300" : "bg-stone-100 text-stone-500 dark:bg-stone-800 dark:text-stone-300"
    }`}>
      <span className={`h-1.5 w-1.5 rounded-full ${enabled ? "bg-green-500" : "bg-stone-400"}`} aria-hidden="true" />
      {enabled ? "Enabled" : "Disabled"}
    </span>
  );
}

export default function Automations() {
  const queryClient = useQueryClient();
  const botsQuery = useQuery({
    queryKey: ["bots"],
    queryFn: () => api<{ bots: Bot[] }>("/bots/"),
  });
  const data = botsQuery.data;
  const act = useMutation({
    mutationFn: ({ slug, action }: { slug: string; action: "toggle" | "run" }) =>
      api(`/bots/${slug}/action/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
      }),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["bots"] }),
  });

  const gate = queryGate(botsQuery, { message: "Couldn't load the automations.", skeleton: <p className="text-sm text-stone-400">Loading bots…</p> });
  if (gate) return gate;
  const bots = data?.bots ?? [];
  return (
    <div>
      <h1 className="mb-2 text-2xl font-semibold tracking-tight">Automations</h1>
      <p className="mb-6 max-w-2xl text-sm text-stone-500 dark:text-stone-300">Bots that handle routine work and report to your Inbox. Enabled bots run daily at 06:00.</p>
      {bots.length === 0 ? (
        <div className="max-w-3xl rounded border border-dashed border-stone-300 bg-white p-10 text-center dark:border-stone-700 dark:bg-stone-900">
          <p className="mb-1 text-sm font-medium text-stone-600 dark:text-stone-300">No automations yet</p>
          <p className="text-sm text-stone-400">Bots that tidy your library, surface stale references, and post digests to your Inbox will appear here once configured.</p>
        </div>
      ) : (
        <div className="max-w-3xl space-y-3">
          {bots.map((bot) => (
            <article key={bot.slug} className="rounded border border-stone-200 bg-white p-5 transition-colors hover:border-stone-300 dark:border-stone-800 dark:bg-stone-900">
              <div className="flex items-start gap-3">
                <div className="min-w-0 flex-1">
                  <div className="flex items-center gap-2.5">
                    <h2 className="truncate font-medium text-stone-900 dark:text-stone-100">{bot.name}</h2>
                    <StatusChip enabled={bot.enabled} />
                  </div>
                  <p className="mt-1 text-sm text-stone-500 dark:text-stone-300">{bot.description}</p>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <button onClick={() => act.mutate({ slug: bot.slug, action: "run" })} disabled={act.isPending}
                          className="rounded border border-stone-300 bg-white px-2.5 py-1 text-xs text-stone-600 transition-colors hover:border-stone-400 focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 disabled:opacity-50 dark:border-stone-700 dark:bg-stone-800 dark:text-stone-300">
                    Run now
                  </button>
                  <button onClick={() => act.mutate({ slug: bot.slug, action: "toggle" })}
                          className={`rounded px-3 py-1 text-xs font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 ${bot.enabled ? "border border-stone-300 bg-white text-stone-600 hover:border-stone-400 dark:border-stone-700 dark:bg-stone-800 dark:text-stone-300" : "bg-indigo-600 text-white hover:bg-indigo-700"}`}>
                    {bot.enabled ? "Disable" : "Enable"}
                  </button>
                </div>
              </div>
              {bot.last_result && <p className="mt-3 text-xs text-stone-400">Last run · {bot.last_result}</p>}
              <RunChart runs={bot.runs} />
            </article>
          ))}
        </div>
      )}
    </div>
  );
}
