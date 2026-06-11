/** Bots with run-history charts (SPA slice 10). */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../api";

type Run = { ok: boolean; count: number | null; started_at: string };
type Bot = { slug: string; name: string; description: string; enabled: boolean; last_result: string; runs: Run[] };

function RunChart({ runs }: { runs: Run[] }) {
  if (runs.length < 2) return null;
  const ordered = [...runs].reverse();
  const top = Math.max(...ordered.map((r) => r.count ?? 0), 1);
  return (
    <div className="mt-3 flex h-10 items-end gap-px" aria-label="Run history chart">
      {ordered.map((r, i) => (
        <div key={i}
             title={`${r.started_at.slice(0, 16).replace("T", " ")} — ${r.ok ? r.count ?? 0 : "failed"}`}
             className={`w-2.5 rounded-t ${r.ok ? "bg-indigo-300 hover:bg-indigo-500" : "bg-red-400 hover:bg-red-600"}`}
             style={{ height: `${Math.max(8, Math.round(((r.count ?? 0) * 100) / top))}%` }} />
      ))}
    </div>
  );
}

export default function Automations() {
  const queryClient = useQueryClient();
  const { data, isLoading } = useQuery({
    queryKey: ["bots"],
    queryFn: () => api<{ bots: Bot[] }>("/bots/"),
  });
  const act = useMutation({
    mutationFn: ({ slug, action }: { slug: string; action: "toggle" | "run" }) =>
      api(`/bots/${slug}/action/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ action }),
      }),
    onSettled: () => queryClient.invalidateQueries({ queryKey: ["bots"] }),
  });

  if (isLoading) return <p className="text-sm text-stone-400">Loading bots…</p>;
  return (
    <div>
      <h1 className="mb-2 text-2xl font-semibold tracking-tight">Automations</h1>
      <p className="mb-6 text-sm text-stone-500">Bots that handle routine work and report to your Inbox. Enabled bots run daily at 06:00.</p>
      <div className="max-w-3xl space-y-3">
        {data?.bots.map((bot) => (
          <article key={bot.slug} className="rounded border border-stone-200 bg-white px-5 py-4">
            <div className="flex items-center gap-3">
              <h2 className="font-medium">{bot.name}</h2>
              <span className={`rounded px-2 py-0.5 text-xs ${bot.enabled ? "bg-green-50 text-green-700" : "bg-stone-100 text-stone-500"}`}>
                {bot.enabled ? "On" : "Off"}
              </span>
              <span className="ml-auto" />
              <button onClick={() => act.mutate({ slug: bot.slug, action: "run" })} disabled={act.isPending}
                      className="rounded border border-stone-300 bg-white px-2 py-1 text-xs hover:border-stone-400 disabled:opacity-50">
                Run now
              </button>
              <button onClick={() => act.mutate({ slug: bot.slug, action: "toggle" })}
                      className={`rounded px-3 py-1 text-xs font-medium ${bot.enabled ? "border border-stone-300 bg-white text-stone-600 hover:border-stone-400" : "bg-indigo-600 text-white hover:bg-indigo-700"}`}>
                {bot.enabled ? "Disable" : "Enable"}
              </button>
            </div>
            <p className="mt-1 text-sm text-stone-500">{bot.description}</p>
            {bot.last_result && <p className="mt-2 text-xs text-stone-400">Last: {bot.last_result}</p>}
            <RunChart runs={bot.runs} />
          </article>
        ))}
      </div>
    </div>
  );
}
