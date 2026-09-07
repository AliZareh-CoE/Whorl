/* Achievements (owner, 2026-09-07: "a lot of achievements — some for fun, some really hard,
 * souls game mode on research"). The ledger: score and rank, four tiers with progress bars,
 * hidden ones shown as ???, the five closest to unlocking, and the Souls mode switch that
 * turns the companion's tone grim (deaths, bonfires, bosses). All derived from real work. */
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { Award, Check, Flame, Lock, Skull, Sparkles, Swords, Trophy } from "lucide-react";
import { api } from "../api";
import { ErrorState } from "../../components/ErrorState";

type Row = { key: string; title: string; description: string; tier: string; points: number; hidden: boolean; unlocked: boolean; unlocked_at: string | null; progress: { current: number; target: number; percent: number } };
type Ledger = { achievements: Row[]; score: number; max_score: number; unlocked: number; total: number; rank: { name: string; floor: number; next: string | null; next_at: number | null }; tiers: { key: string; points: number; total: number; unlocked: number }[]; souls_mode: boolean; souls: { deaths: number; bonfires: number; bosses: number; souls: number }; recent_unlocks: string[]; next_up: Row[] };

const panel = "rise rounded-2xl border border-stone-200 bg-white/70 p-5 backdrop-blur dark:border-stone-800 dark:bg-stone-900/60";
const railH = "text-[11px] font-semibold uppercase tracking-wider text-stone-400";
export const TIER_META: Record<string, { label: string; blurb: string; cls: string; bar: string; icon: typeof Award }> = {
  fun: { label: "Fun", blurb: "small delights — some hidden", cls: "text-sky-600 dark:text-sky-300", bar: "from-sky-500 to-cyan-400", icon: Sparkles },
  steady: { label: "Steady", blurb: "the shape of good habits", cls: "text-emerald-600 dark:text-emerald-300", bar: "from-emerald-500 to-teal-400", icon: Award },
  hard: { label: "Hard", blurb: "months of work", cls: "text-amber-600 dark:text-amber-300", bar: "from-amber-500 to-orange-400", icon: Trophy },
  souls: { label: "Souls", blurb: "prepare to write", cls: "text-red-600 dark:text-red-300", bar: "from-red-600 to-rose-500", icon: Skull },
};

export default function Achievements() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["achievements"], queryFn: () => api<Ledger>("/achievements/") });
  const [tier, setTier] = useState<string>("all");
  const [onlyOpen, setOnlyOpen] = useState(false);
  const souls = useMutation({ mutationFn: (on: boolean) => api("/pet/", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ souls_mode: on }) }), onSuccess: () => { qc.invalidateQueries({ queryKey: ["achievements"] }); qc.invalidateQueries({ queryKey: ["pet"] }); } });
  const d = q.data;
  const rows = useMemo(() => (d?.achievements ?? []).filter((r) => (tier === "all" || r.tier === tier) && (!onlyOpen || !r.unlocked)), [d, tier, onlyOpen]);
  if (q.isLoading) return <p className="text-sm text-stone-400">Counting…</p>;
  if (q.error || !d) return <ErrorState message="Couldn't load the achievements." onRetry={() => q.refetch()} />;
  const pct = Math.round((100 * d.score) / d.max_score);
  const grim = d.souls_mode;
  return (
    <div className={`mx-auto max-w-5xl ${grim ? "souls" : ""}`}>
      <nav className="mb-4 text-sm text-stone-400" aria-label="Breadcrumb"><Link to="/pet" className="hover:underline">Companion</Link> / Achievements</nav>
      <section className={`${panel} relative overflow-hidden`} style={{ ["--i" as string]: 1 }} data-testid="achievements-hero">
        <div className={`pointer-events-none absolute -right-24 -top-24 h-72 w-72 rounded-full blur-3xl ${grim ? "bg-red-600/15" : "bg-amber-400/10"}`} aria-hidden="true" />
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className={railH}>{grim ? "Souls of the researcher" : "Achievements"}</p>
            <h1 className="mt-1 text-4xl font-semibold tracking-tight"><span className="text-gradient">{d.rank.name}</span></h1>
            <p className="mt-1 text-sm text-stone-500">{d.unlocked}/{d.total} unlocked · {d.score} of {d.max_score} points{d.rank.next ? ` · ${d.rank.next_at! - d.score} to ${d.rank.next}` : " · the last rank"}</p>
            <div className="mt-3 h-2 w-72 max-w-full overflow-hidden rounded-full bg-stone-200 dark:bg-stone-800"><div className={`h-full rounded-full bg-gradient-to-r ${grim ? "from-red-600 to-orange-500" : "from-indigo-500 to-fuchsia-400"} transition-all`} style={{ width: `${pct}%` }} /></div>
          </div>
          <label className={`inline-flex cursor-pointer items-center gap-2 rounded-xl border px-3 py-2 text-sm ${grim ? "border-red-500/50 bg-red-500/10 text-red-700 dark:text-red-200" : "border-stone-200 dark:border-stone-700"}`} title="Same facts, told grimly: deaths, bonfires, bosses. The companion changes its tone." data-testid="souls-toggle">
            <input type="checkbox" checked={grim} onChange={(e) => souls.mutate(e.target.checked)} className="accent-red-600" /><Skull className="h-4 w-4" aria-hidden="true" />Souls mode
          </label>
        </div>
        {grim && (
          <dl className="mt-5 grid grid-cols-2 gap-3 text-center sm:grid-cols-4" data-testid="souls-counters">
            {([["deaths", "Deaths", Skull, "rejections · contradictions · failed compiles"], ["bonfires", "Bonfires", Flame, "milestones rested at"], ["bosses", "Bosses slain", Swords, "acceptances"], ["souls", "Souls", Sparkles, "lifetime points"]] as const).map(([k, label, Icon, blurb]) => (
              <div key={k} className="rounded-xl border border-red-500/30 bg-red-500/5 p-3"><dt className="flex items-center justify-center gap-1 text-[11px] uppercase tracking-wider text-red-500"><Icon className="h-3.5 w-3.5" aria-hidden="true" />{label}</dt><dd className="mt-1 text-2xl font-semibold tabular-nums">{d.souls[k]}</dd><dd className="text-[10px] text-stone-400">{blurb}</dd></div>
            ))}
          </dl>
        )}
      </section>

      <div className="mt-5 grid gap-5 lg:grid-cols-[minmax(0,1fr)_18rem]">
        <div>
          <div className="mb-3 flex flex-wrap items-center gap-2 text-xs">
            {["all", "fun", "steady", "hard", "souls"].map((t) => { const m = TIER_META[t]; const stat = d.tiers.find((x) => x.key === t); return (
              <button key={t} type="button" onClick={() => setTier(t)} className={`rounded-full border px-3 py-1 font-medium transition-colors ${tier === t ? "border-indigo-400 bg-indigo-500/10 text-indigo-700 dark:text-indigo-200" : "border-stone-200 text-stone-500 hover:border-stone-300 dark:border-stone-700"}`} data-testid={`tier-${t}`}>
                {m ? m.label : "All"}{stat && <span className="ml-1 text-stone-400">{stat.unlocked}/{stat.total}</span>}
              </button>
            ); })}
            <label className="ml-auto inline-flex cursor-pointer items-center gap-1.5 text-stone-500"><input type="checkbox" checked={onlyOpen} onChange={(e) => setOnlyOpen(e.target.checked)} className="accent-indigo-600" />still locked</label>
          </div>
          <ul className="grid gap-3 sm:grid-cols-2" data-testid="achievement-grid">
            {rows.map((a) => { const m = TIER_META[a.tier]; const Icon = a.unlocked ? Check : a.hidden ? Lock : m.icon; const fresh = d.recent_unlocks.includes(a.key); return (
              <li key={a.key} className={`relative rounded-xl border p-3 transition-colors ${a.unlocked ? (a.tier === "souls" ? "border-red-400/60 bg-red-500/10" : "border-amber-300/60 bg-amber-50/60 dark:border-amber-500/30 dark:bg-amber-500/10") : "border-stone-100 dark:border-stone-800"} ${a.hidden && !a.unlocked ? "opacity-60" : ""}`} data-testid="achievement" data-tier={a.tier} data-unlocked={a.unlocked}>
                {fresh && <span className="absolute -right-1.5 -top-1.5 rounded-full bg-indigo-600 px-1.5 py-0.5 text-[9px] font-semibold uppercase tracking-wider text-white shadow">new</span>}
                <div className="flex items-start gap-2">
                  <span className={`mt-0.5 shrink-0 ${a.unlocked ? (a.tier === "souls" ? "text-red-500" : "text-amber-500") : "text-stone-300"}`}><Icon className="h-4 w-4" aria-hidden="true" /></span>
                  <div className="min-w-0 flex-1">
                    <p className="flex items-center gap-2 text-sm font-medium"><span className="truncate">{a.title}</span><span className={`shrink-0 text-[10px] uppercase tracking-wider ${m.cls}`}>{m.label} · {a.points}</span></p>
                    <p className="mt-0.5 text-[11px] leading-4 text-stone-500">{a.description}</p>
                    {!a.unlocked && !a.hidden && a.progress.target > 1 && <div className="mt-2 flex items-center gap-2"><div className="h-1 flex-1 overflow-hidden rounded-full bg-stone-200 dark:bg-stone-800"><div className={`h-full rounded-full bg-gradient-to-r ${m.bar}`} style={{ width: `${a.progress.percent}%` }} /></div><span className="text-[10px] tabular-nums text-stone-400">{a.progress.current}/{a.progress.target}</span></div>}
                    {a.unlocked && a.unlocked_at && <p className="mt-1 text-[10px] uppercase tracking-wider text-stone-400">unlocked {new Date(a.unlocked_at).toLocaleDateString([], { month: "short", day: "numeric" })}</p>}
                  </div>
                </div>
              </li>
            ); })}
            {rows.length === 0 && <li className="col-span-full rounded-xl border border-dashed border-stone-300 p-6 text-center text-sm text-stone-400 dark:border-stone-700">Nothing here with these filters.</li>}
          </ul>
        </div>
        <aside className="space-y-5">
          <section className={panel} style={{ ["--i" as string]: 3 }} data-testid="next-up">
            <p className={`${railH} mb-2`}>Closest to unlocking</p>
            <ul className="space-y-2">{d.next_up.map((a) => <li key={a.key}><p className="flex items-center justify-between text-sm"><span className="truncate">{a.title}</span><span className="ml-2 shrink-0 text-[11px] tabular-nums text-stone-400">{a.progress.current}/{a.progress.target}</span></p><div className="mt-1 h-1 overflow-hidden rounded-full bg-stone-200 dark:bg-stone-800"><div className={`h-full rounded-full bg-gradient-to-r ${TIER_META[a.tier].bar}`} style={{ width: `${a.progress.percent}%` }} /></div></li>)}</ul>
          </section>
          <section className={panel} style={{ ["--i" as string]: 4 }}>
            <p className={`${railH} mb-2`}>Tiers</p>
            <ul className="space-y-1.5 text-sm">{d.tiers.map((t) => { const m = TIER_META[t.key]; const Icon = m.icon; return <li key={t.key} className="flex items-center gap-2"><Icon className={`h-4 w-4 ${m.cls}`} aria-hidden="true" /><span className="flex-1"><span className="font-medium">{m.label}</span> <span className="text-xs text-stone-400">· {m.blurb}</span></span><span className="text-xs tabular-nums text-stone-500">{t.points} pts</span></li>; })}</ul>
            <p className="mt-3 text-[11px] leading-4 text-stone-400">Everything is read from your real work — nothing to grind, nothing to buy. Hidden ones reveal themselves when they happen.</p>
          </section>
        </aside>
      </div>
    </div>
  );
}
