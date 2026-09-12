/* Mochi's page (Owner report 2026-09-06): the companion as a place, not a footnote. A big
 * living creature you can poke, its stage and mood with the reasons, the road to the next
 * stage, four stats grown from real work, a streak, achievements and the feeding rules —
 * all derived from the database, never a chore. */
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Award, BookOpen, Brain, Check, Flame, Lock, Pencil, Skull, Sparkles, Target, Volume2, Zap } from "lucide-react";
import { Link } from "react-router-dom";
import { api, csrfToken } from "../api";
import { Creature, type Reaction } from "../pet/Creature";
import { queryGate } from "../../components/QueryBoundary";

type Achievement = { key: string; title: string; description: string; unlocked: boolean; tier: string; points: number; hidden: boolean; progress: { current: number; target: number; percent: number } };
type PetState = {
  name: string; stage: string; stage_blurb: string; mood: string; mood_blurb: string; speech: string; speech_lines: string[];
  species?: { key: string; name: string; blurb: string; shiny: boolean };
  reactions: Record<string, string>; stats: Record<string, number>; dominant_stat: string; weekly_points: number; lifetime_points: number;
  to_next_stage: number | null; next_stage_name: string | null; stage_floor: number; next_stage_points: number | null; streak_days: number;
  achievements: Achievement[]; achievement_score: number; rank: { name: string; next: string | null; next_at: number | null }; souls_mode: boolean; souls: { deaths: number; bonfires: number; bosses: number; souls: number }; recent_unlocks: string[]; points_legend: { action: string; points: number }[]; stages: { points: number; name: string; blurb: string }[];
};

const panel = "rise rounded-2xl border border-stone-200 bg-white/70 p-5 backdrop-blur dark:border-stone-800 dark:bg-stone-900/60";
const railH = "text-[11px] font-semibold uppercase tracking-wider text-stone-400";
const STAT_META: Record<string, { label: string; icon: typeof Brain; blurb: string; cls: string }> = {
  wisdom: { label: "Wisdom", icon: BookOpen, blurb: "papers read or annotated", cls: "from-indigo-500 to-violet-400" },
  focus: { label: "Focus", icon: Target, blurb: "milestones completed", cls: "from-emerald-500 to-teal-400" },
  curiosity: { label: "Curiosity", icon: Brain, blurb: "notes and comments", cls: "from-amber-500 to-orange-400" },
  grit: { label: "Grit", icon: Zap, blurb: "experiments and submissions", cls: "from-rose-500 to-pink-400" },
};
const POKES: Reaction[] = ["hop", "love", "nom", "think", "celebrate"];

export default function PetPage() {
  const qc = useQueryClient();
  const pet = useQuery({ queryKey: ["pet"], queryFn: () => api<PetState>("/pet/") });
  const [reaction, setReaction] = useState<Reaction | null>(null);
  const [line, setLine] = useState<string>("");
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState("");
  const [speaking, setSpeaking] = useState(false);
  const rename = useMutation({ mutationFn: (n: string) => api<PetState>("/pet/", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: n }) }), onSuccess: (data) => { qc.setQueryData(["pet"], data); setEditing(false); } });
  const souls = useMutation({ mutationFn: (on: boolean) => api<PetState>("/pet/", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ souls_mode: on }) }), onSuccess: (data) => { qc.setQueryData(["pet"], data); qc.invalidateQueries({ queryKey: ["achievements"] }); setLine(data.speech); } });
  const p = pet.data;
  useEffect(() => { if (p && !line) setLine(p.speech); }, [p, line]);

  const poke = () => {
    if (!p) return;
    const r = POKES[Math.floor(Math.random() * POKES.length)];
    setReaction(null); window.setTimeout(() => setReaction(r), 10);
    const pool = p.speech_lines?.length ? p.speech_lines : [p.speech];
    setLine(pool[Math.floor(Math.random() * pool.length)]);
  };
  const speak = async () => {
    if (speaking || !line) return;
    setSpeaking(true);
    try { const res = await fetch("/tts/", { method: "POST", headers: { "X-CSRFToken": csrfToken() }, body: new URLSearchParams({ text: line }), credentials: "same-origin" }); if (!res.ok) throw new Error(); const audio = new Audio(URL.createObjectURL(await res.blob())); audio.addEventListener("ended", () => setSpeaking(false)); audio.addEventListener("error", () => setSpeaking(false)); await audio.play(); } catch { setSpeaking(false); }
  };

  const gate = queryGate(pet, { message: "Mochi is unreachable.", skeleton: <p className="text-sm text-stone-400">Waking Mochi…</p> });
  if (gate || !p) return gate;
  const progress = p.next_stage_points ? Math.min(100, Math.round(((p.lifetime_points - p.stage_floor) / (p.next_stage_points - p.stage_floor)) * 100)) : 100;
  const unlocked = p.achievements.filter((a) => a.unlocked).length;

  return (
    <div className="mx-auto max-w-5xl">
      <nav className="mb-4 text-sm text-stone-400" aria-label="Breadcrumb">Companion</nav>
      <section className={`${panel} relative overflow-hidden`} style={{ ["--i" as string]: 1 }} data-testid="pet-hero">
        <div className="pointer-events-none absolute -right-24 -top-24 h-72 w-72 rounded-full bg-indigo-500/10 blur-3xl" aria-hidden="true" />
        <div className="flex flex-col items-center gap-8 md:flex-row md:items-center">
          <div className="relative shrink-0">
            <div className="absolute inset-0 -m-6 rounded-full bg-gradient-to-b from-indigo-500/10 to-transparent" aria-hidden="true" />
            <Creature stage={p.stage} mood={p.mood} species={p.species?.key} size={200} reaction={reaction} onClick={poke} className="relative" />
          </div>
          <div className="min-w-0 flex-1 text-center md:text-left">
            <div className="flex flex-wrap items-center justify-center gap-2 md:justify-start">
              {editing ? (
                <form onSubmit={(e) => { e.preventDefault(); if (name.trim()) rename.mutate(name.trim()); }} className="flex items-center gap-2">
                  <input autoFocus value={name} onChange={(e) => setName(e.target.value)} maxLength={40} className="rounded-lg border border-stone-300 bg-white px-2 py-1 text-2xl font-semibold tracking-tight dark:border-stone-700 dark:bg-stone-800" aria-label="Pet name" />
                  <button type="submit" className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700">Save</button>
                  <button type="button" onClick={() => setEditing(false)} className="text-sm text-stone-500 hover:underline">Cancel</button>
                </form>
              ) : (
                <h1 className="text-gradient text-4xl font-semibold tracking-tight">{p.name}<button type="button" onClick={() => { setName(p.name); setEditing(true); }} className="ml-2 inline-flex align-middle text-stone-400 hover:text-indigo-500" aria-label="Rename"><Pencil className="h-4 w-4" aria-hidden="true" /></button></h1>
              )}
            </div>
            <p className="mt-1 text-sm text-stone-500" data-testid="pet-species">{p.species && p.stage !== "egg" ? <><span title={p.species.blurb}>{p.species.shiny ? "✦ a shiny " : "a "}{p.species.name}</span> · </> : null}the {p.stage} · {p.mood}</p>
            <div className="mt-4 rounded-xl border border-indigo-200 bg-indigo-50/70 px-4 py-3 text-sm text-indigo-900 dark:border-indigo-500/30 dark:bg-indigo-500/10 dark:text-indigo-100" data-testid="pet-line">
              <span key={line} className="pet-bubble inline">{line}</span>
              <button type="button" onClick={() => void speak()} disabled={speaking} className="ml-2 inline-flex align-middle text-indigo-400 hover:text-indigo-600 disabled:opacity-40" title="Hear it (local voice)" aria-label="Hear it"><Volume2 className="h-3.5 w-3.5" aria-hidden="true" /></button>
            </div>
            <p className="mt-2 text-xs text-stone-400">Click {p.name} to poke. It watches your cursor. It never nags.</p>
            <div className="mt-5 grid grid-cols-3 gap-3 text-center md:text-left">
              <div><p className={railH}>This week</p><p className="text-2xl font-semibold tabular-nums">{p.weekly_points}<span className="ml-1 text-xs font-normal text-stone-400">pts</span></p><p className="text-[11px] text-stone-500">{p.mood_blurb}</p></div>
              <div><p className={railH}>Streak</p><p className="flex items-center justify-center gap-1 text-2xl font-semibold tabular-nums md:justify-start"><Flame className={`h-5 w-5 ${p.streak_days ? "text-orange-500" : "text-stone-300"}`} aria-hidden="true" />{p.streak_days}<span className="ml-1 text-xs font-normal text-stone-400">day{p.streak_days === 1 ? "" : "s"}</span></p><p className="text-[11px] text-stone-500">{p.streak_days ? "consecutive days with real work" : "any note, paper or milestone starts one"}</p></div>
              <div><p className={railH}>Lifetime</p><p className="text-2xl font-semibold tabular-nums">{p.lifetime_points}<span className="ml-1 text-xs font-normal text-stone-400">pts</span></p><p className="text-[11px] text-stone-500">{p.stage_blurb}</p></div>
            </div>
          </div>
        </div>
        <div className="mt-6" data-testid="stage-progress">
          <div className="mb-1 flex items-center justify-between text-xs text-stone-500"><span>{p.next_stage_name ? `${p.to_next_stage} points to ${p.next_stage_name}` : "Final stage reached"}</span><span className="tabular-nums">{progress}%</span></div>
          <div className="h-2 overflow-hidden rounded-full bg-stone-200 dark:bg-stone-800"><div className="h-full rounded-full bg-gradient-to-r from-indigo-500 to-fuchsia-400 transition-all" style={{ width: `${progress}%` }} /></div>
          <ol className="mt-2 flex justify-between text-[10px] uppercase tracking-wider text-stone-400">{p.stages.map((s) => <li key={s.name} className={s.name === p.stage ? "font-semibold text-indigo-500" : ""} title={s.blurb}>{s.name} · {s.points}</li>)}</ol>
        </div>
      </section>

      <div className="mt-5 grid gap-5 lg:grid-cols-3">
        <section className={`${panel} lg:col-span-2`} style={{ ["--i" as string]: 2 }} data-testid="pet-stats">
          <p className={`${railH} mb-3`}>Stats · grown from real work</p>
          <div className="grid gap-4 sm:grid-cols-2">
            {Object.entries(p.stats).map(([key, level]) => { const meta = STAT_META[key] ?? { label: key, icon: Sparkles, blurb: "", cls: "from-stone-400 to-stone-300" }; const Icon = meta.icon; return (
              <div key={key} className={`rounded-xl border p-3 ${p.dominant_stat === key ? "border-indigo-300 bg-indigo-50/50 dark:border-indigo-500/40 dark:bg-indigo-500/10" : "border-stone-100 dark:border-stone-800"}`}>
                <div className="flex items-center justify-between"><span className="flex items-center gap-1.5 text-sm font-medium"><Icon className="h-4 w-4 text-stone-400" aria-hidden="true" />{meta.label}{p.dominant_stat === key && <span className="rounded-full bg-indigo-500/15 px-1.5 text-[10px] font-semibold uppercase text-indigo-600 dark:text-indigo-300">dominant</span>}</span><span className="text-xs tabular-nums text-stone-500">lvl {level}/10</span></div>
                <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-stone-200 dark:bg-stone-800"><div className={`h-full rounded-full bg-gradient-to-r ${meta.cls}`} style={{ width: `${level * 10}%` }} /></div>
                <p className="mt-1.5 text-[11px] text-stone-500">{meta.blurb}</p>
              </div>); })}
          </div>
          <p className="mt-4 text-xs text-stone-500">{p.reactions && Object.keys(p.reactions).length ? `${p.name} reacts when you finish a milestone, add a paper, capture a thought or write a note.` : ""}</p>
        </section>
        <section className={panel} style={{ ["--i" as string]: 3 }} data-testid="pet-legend">
          <p className={`${railH} mb-3`}>How {p.name} grows</p>
          <ul className="space-y-1.5 text-sm">{p.points_legend.map((l) => <li key={l.action} className="flex items-center justify-between"><span className="text-stone-600 dark:text-stone-300">{l.action}</span><span className="rounded-full bg-stone-100 px-2 text-xs font-semibold tabular-nums text-stone-600 dark:bg-stone-800 dark:text-stone-300">+{l.points}</span></li>)}</ul>
          <p className="mt-3 text-[11px] leading-4 text-stone-400">Points come from things you already do. Nothing decays. Sleeping means you rested too.</p>
        </section>
      </div>

      <section className={`${panel} mt-5`} style={{ ["--i" as string]: 4 }} data-testid="pet-achievements">
        <div className="mb-3 flex flex-wrap items-center gap-3">
          <p className={railH}>Achievements <span className="normal-case tracking-normal text-stone-400">{unlocked}/{p.achievements.length}</span></p>
          <span className="text-sm"><span className="text-gradient font-semibold">{p.rank.name}</span> <span className="text-xs text-stone-400">· {p.achievement_score} pts{p.rank.next ? ` · ${p.rank.next_at! - p.achievement_score} to ${p.rank.next}` : ""}</span></span>
          <Link to="/achievements" className="text-xs font-medium text-indigo-600 hover:underline dark:text-indigo-300" data-testid="ledger-link">The whole ledger →</Link>
          <label className={`ml-auto inline-flex cursor-pointer items-center gap-1.5 rounded-lg border px-2 py-1 text-xs ${p.souls_mode ? "border-red-500/50 bg-red-500/10 text-red-700 dark:text-red-200" : "border-stone-200 text-stone-500 dark:border-stone-700"}`} title="Same facts, told grimly" data-testid="pet-souls-toggle"><input type="checkbox" checked={p.souls_mode} onChange={(e) => souls.mutate(e.target.checked)} className="accent-red-600" /><Skull className="h-3.5 w-3.5" aria-hidden="true" />Souls mode</label>
        </div>
        {p.souls_mode && <p className="mb-3 text-xs text-red-600 dark:text-red-300" data-testid="pet-souls-line">{p.souls.deaths} deaths · {p.souls.bonfires} bonfires · {p.souls.bosses} bosses slain · {p.souls.souls} souls</p>}
        <ul className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
          {[...p.achievements].sort((a, b) => Number(b.unlocked) - Number(a.unlocked) || b.progress.percent - a.progress.percent).slice(0, 10).map((a) => (
            <li key={a.key} className={`rounded-xl border p-3 ${a.unlocked ? "border-amber-300/60 bg-amber-50/60 dark:border-amber-500/30 dark:bg-amber-500/10" : "border-stone-100 opacity-70 dark:border-stone-800"}`} title={a.description}>
              <div className="flex items-center gap-2 text-sm font-medium">{a.unlocked ? <Award className="h-4 w-4 text-amber-500" aria-hidden="true" /> : <Lock className="h-4 w-4 text-stone-300" aria-hidden="true" />}{a.title}</div>
              <p className="mt-1 text-[11px] leading-4 text-stone-500">{a.description}</p>
              {a.unlocked ? <p className="mt-1 flex items-center gap-1 text-[10px] font-semibold uppercase tracking-wider text-amber-600 dark:text-amber-300"><Check className="h-3 w-3" aria-hidden="true" />unlocked</p> : !a.hidden && a.progress.target > 1 ? <p className="mt-1 text-[10px] tabular-nums text-stone-400">{a.progress.current}/{a.progress.target}</p> : null}
            </li>
          ))}
        </ul>
        <p className="mt-3 text-[11px] text-stone-400">Ten of {p.achievements.length}. Fun ones, steady ones, hard ones, and a souls tier for the brave — <Link to="/achievements" className="text-indigo-600 hover:underline dark:text-indigo-300">see them all</Link>.</p>
      </section>
    </div>
  );
}
