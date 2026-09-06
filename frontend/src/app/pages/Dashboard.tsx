import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router-dom";
import { Command, Sparkles } from "lucide-react";
import { api } from "../api";
import { toggleCalm, useCalm } from "../calm";
import { Skeleton, SkeletonCard, SkeletonLines } from "../../components/Skeleton";
import { ErrorState } from "../../components/ErrorState";
import { Constellation } from "../../components/Constellation";

type Attention = {
  empty: boolean;
  overdue: { title: string; due_date: string; project: string; url: string }[];
  deadlines: { title: string; deadline: string; days_to_deadline: number; project: string; url: string }[];
  inbox: { id: number; text: string }[];
};

type Dash = {
  stats: Record<string, number>;
  inbox_count: number;
  attention: Attention;
  active: {
    name: string; slug: string; url: string; color: string;
    phase: string | null; done: number; total: number; percent: number;
  }[];
  milestones: { title: string; project: string; due_date: string | null; overdue: boolean; url: string }[];
  deadlines: { title: string; deadline: string | null; url: string }[];
};

// Observatory (2026-09-06): glass panels, display numerals, orbit-ring progress, a living
// constellation of the active projects behind the greeting. Tokens do the colour work; the
// classes below only shape the panels.
const panel = "rounded-2xl border border-stone-200 bg-white p-5 dark:border-stone-800 dark:bg-stone-900";
const tile = "rounded-2xl border border-stone-200 bg-white px-5 py-4 dark:border-stone-800 dark:bg-stone-900";
const h2 = "mb-3 text-[11px] font-semibold uppercase tracking-[0.14em] text-stone-400 dark:text-stone-500";
const row = "-mx-2 flex items-baseline gap-2 rounded-lg px-2 py-1.5 transition-colors hover:bg-stone-50 hover:text-indigo-700 dark:hover:bg-stone-800 dark:hover:text-indigo-300";

function greeting(): string {
  const h = new Date().getHours();
  if (h < 5) return "Late night";
  if (h < 12) return "Good morning";
  if (h < 18) return "Good afternoon";
  return "Good evening";
}

function openCommandBar() {
  document.dispatchEvent(new KeyboardEvent("keydown", { key: "k", metaKey: true, bubbles: true }));
}

/** Inline triage on an attention inbox row (#157): file to a project or dismiss. */
function TriageControls({ id, projects }: { id: number; projects: { slug: string; name: string }[] }) {
  const queryClient = useQueryClient();
  const [slug, setSlug] = useState(projects[0]?.slug ?? "");
  const triage = useMutation({
    mutationFn: (body: { processed: boolean; project?: string }) =>
      api(`/quick-capture/${id}/`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["dashboard"] }),
  });
  return (
    <span className="flex shrink-0 items-center gap-1">
      <select
        value={slug}
        onChange={(e) => setSlug(e.target.value)}
        className="rounded-md border border-stone-200 px-1 py-0.5 text-xs text-stone-600 dark:border-stone-700 dark:bg-stone-800 dark:text-stone-300"
      >
        {projects.map((p) => (
          <option key={p.slug} value={p.slug}>{p.name.slice(0, 22)}</option>
        ))}
      </select>
      <button
        type="button"
        disabled={triage.isPending || !slug}
        onClick={() => triage.mutate({ processed: true, project: slug })}
        className="rounded-md px-1.5 py-0.5 text-xs text-indigo-600 transition-colors hover:bg-indigo-50 active:opacity-80 disabled:opacity-50 dark:text-indigo-400 dark:hover:bg-indigo-500/10"
      >
        file
      </button>
      <button
        type="button"
        title="Dismiss"
        disabled={triage.isPending}
        onClick={() => triage.mutate({ processed: true })}
        className="rounded-md px-1.5 py-0.5 text-xs text-stone-400 transition-colors hover:bg-stone-100 hover:text-stone-600 active:opacity-80 disabled:opacity-50 dark:text-stone-400 dark:hover:bg-stone-800 dark:hover:text-stone-300"
      >
        ✕
      </button>
    </span>
  );
}

/** Orbit ring: an SVG progress ring in the project's accent colour with a soft glow. */
function OrbitRing({ percent, color, size = 44 }: { percent: number; color: string; size?: number }) {
  const r = (size - 6) / 2;
  const c = 2 * Math.PI * r;
  const off = c * (1 - Math.max(0, Math.min(100, percent)) / 100);
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} className="orbit-ring shrink-0" aria-hidden="true">
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="currentColor" strokeWidth="3" className="text-stone-100 dark:text-stone-800" />
      <circle
        cx={size / 2} cy={size / 2} r={r} fill="none" stroke={color} strokeWidth="3" strokeLinecap="round"
        strokeDasharray={c} strokeDashoffset={off} transform={`rotate(-90 ${size / 2} ${size / 2})`}
        style={{ transition: "stroke-dashoffset 900ms cubic-bezier(.2,.7,.2,1)" }}
      />
    </svg>
  );
}

function Stat({ value, label, i, to }: { value: number; label: string; i: number; to?: string }) {
  const inner = (
    <>
      <p className="font-display text-gradient text-4xl font-bold tabular-nums leading-none">{value}</p>
      <p className="mt-2 text-xs text-stone-400 dark:text-stone-400">{label}</p>
    </>
  );
  return (
    <div className={`${tile} rise`} style={{ ["--i" as string]: i }}>
      {to ? <Link to={to} className="block hover:opacity-90">{inner}</Link> : inner}
    </div>
  );
}

export default function Dashboard() {
  // Calm mode (#274) lives in ../calm so the ⌘K palette verb (#277) can flip it and this
  // page updates live (#278) — no remount, no settings page.
  const calm = useCalm();

  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["dashboard"],
    queryFn: () => api<Dash>("/dashboard/"),
  });

  if (isLoading)
    return (
      <div role="status" aria-label="Loading" className="space-y-6">
        <Skeleton className="h-56 w-full rounded-2xl" />
        <SkeletonLines lines={3} />
        <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
          {Array.from({ length: 4 }).map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
        <div className="grid gap-4 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <SkeletonCard key={i} />
          ))}
        </div>
      </div>
    );
  if (error || !data) return <ErrorState message="Couldn't load the dashboard." onRetry={() => refetch()} />;

  const attention = data.attention;
  const needs = attention.overdue.length + attention.deadlines.length + attention.inbox.length;
  const anchors = data.active.map((p) => ({ label: p.name, color: p.color, weight: 0.35 + p.percent / 150 }));

  return (
    <div>
      {/* Hero: the constellation of your active projects, the greeting, and the spotlight. */}
      <section
        className="hairline-gradient rise relative mb-5 overflow-hidden rounded-3xl border border-stone-200 bg-white dark:border-transparent dark:bg-stone-900"
        style={{ ["--i" as string]: 0 }}
      >
        <div className="absolute inset-0 hidden dark:block">
          <Constellation anchors={anchors} density={0.9} />
        </div>
        <div className="pointer-events-none absolute inset-0 hidden bg-gradient-to-r from-stone-950/70 via-stone-950/20 to-transparent dark:block" />
        <div className="relative flex min-h-[15rem] flex-col justify-between p-7">
          <div className="flex items-start justify-between gap-4">
            <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-stone-400 dark:text-stone-400">
              {new Date().toLocaleDateString(undefined, { weekday: "long", month: "long", day: "numeric" })}
            </p>
            <button
              type="button"
              onClick={toggleCalm}
              aria-pressed={calm}
              title={calm ? "Show the monthly stats" : "Hide the monthly stats — show only what needs you"}
              className="shrink-0 rounded-full border border-stone-200 px-3 py-1 text-xs text-stone-500 transition-colors hover:border-stone-300 hover:text-stone-700 dark:border-stone-700 dark:bg-stone-950/40 dark:text-stone-300 dark:hover:text-stone-100"
            >
              {calm ? "Full view" : "Calm mode"}
            </button>
          </div>
          <div className="max-w-2xl">
            <h1 className="font-display text-4xl font-bold leading-[1.05] tracking-tight text-stone-900 dark:text-stone-100 sm:text-5xl">
              {greeting()}.
              <br />
              <span className="text-gradient">
                {needs === 0 ? "All clear, everywhere." : `${needs} thing${needs === 1 ? "" : "s"} need${needs === 1 ? "s" : ""} you.`}
              </span>
            </h1>
            <p className="mt-3 text-sm text-stone-500 dark:text-stone-300">
              {data.active.length} active project{data.active.length === 1 ? "" : "s"} · {data.milestones.length} upcoming milestone{data.milestones.length === 1 ? "" : "s"} · {data.inbox_count} in the inbox
            </p>
            <button
              type="button"
              onClick={openCommandBar}
              className="glow-accent mt-5 inline-flex items-center gap-3 rounded-full border border-indigo-200 bg-white/80 py-2 pl-4 pr-2 text-sm text-stone-600 transition-all hover:-translate-y-0.5 dark:border-indigo-500/40 dark:bg-stone-950/60 dark:text-stone-200"
            >
              <Sparkles className="h-4 w-4 text-indigo-500" aria-hidden="true" />
              <span>Jump anywhere, capture an idea, complete a milestone…</span>
              <kbd className="ml-2 inline-flex items-center gap-1 rounded-full border border-stone-200 bg-stone-50 px-2 py-0.5 font-sans text-[11px] text-stone-500 dark:border-stone-700 dark:bg-stone-900 dark:text-stone-300">
                <Command className="h-3 w-3" aria-hidden="true" />K
              </kbd>
            </button>
          </div>
        </div>
      </section>

      {/* the answer first ([REV] cycle 145 → SPA #156): what needs me today */}
      {attention.empty ? (
        <div className="rise mb-5 rounded-2xl border border-dashed border-stone-300 bg-white px-5 py-4 text-sm text-stone-500 dark:border-stone-700 dark:bg-stone-900 dark:text-stone-300" style={{ ["--i" as string]: 1 }}>
          All clear — nothing overdue, no deadlines inside two weeks, inbox triaged.
        </div>
      ) : (
        <section className={`${panel} rise mb-5 border-l-2 border-l-red-400 dark:border-l-red-400/80 dark:shadow-[inset_12px_0_28px_-24px_rgba(248,113,113,0.9)]`} style={{ ["--i" as string]: 1 }}>
          <h2 className={`${h2} mb-2.5`}>Needs attention</h2>
          <ul className="space-y-1.5 text-sm">
            {attention.overdue.map((m) => (
              <li key={`o${m.url}${m.title}`} className="flex items-baseline gap-2">
                <span className="shrink-0 rounded-full bg-red-500/10 px-2 py-0.5 text-[11px] font-medium text-red-600 dark:text-red-300">overdue</span>
                <a href={m.url} className="min-w-0 flex-1 truncate hover:underline dark:text-stone-100">{m.title}</a>
                <span className="shrink-0 text-xs text-stone-400 dark:text-stone-400">{m.project} · due {m.due_date}</span>
              </li>
            ))}
            {attention.deadlines.map((d) => (
              <li key={`d${d.url}${d.title}`} className="flex items-baseline gap-2">
                <span className={`shrink-0 rounded-full px-2 py-0.5 text-[11px] font-medium ${d.days_to_deadline < 7 ? "bg-red-500/10 text-red-600 dark:text-red-300" : "bg-amber-500/10 text-amber-600 dark:text-amber-300"}`}>deadline</span>
                <a href={d.url} className="min-w-0 flex-1 truncate hover:underline dark:text-stone-100">{d.title}</a>
                <span className="shrink-0 text-xs text-stone-400 dark:text-stone-400">
                  {d.project} · {d.days_to_deadline < 0 ? "passed" : `${d.days_to_deadline} day${d.days_to_deadline === 1 ? "" : "s"}`} ({d.deadline})
                </span>
              </li>
            ))}
            {attention.inbox.map((q) => (
              <li key={`q${q.id}`} className="flex items-baseline gap-2">
                <span className="shrink-0 rounded-full bg-indigo-500/10 px-2 py-0.5 text-[11px] font-medium text-indigo-600 dark:text-indigo-300">inbox</span>
                <span className="min-w-0 flex-1 truncate text-stone-600 dark:text-stone-300">{q.text}</span>
                <TriageControls id={q.id} projects={data.active} />
                <Link to="/inbox" className="shrink-0 text-xs text-stone-400 hover:underline dark:text-stone-400" title="Open the full inbox">all →</Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      {!calm && (
        <div className="mb-5 grid grid-cols-2 gap-4 sm:grid-cols-4">
          <Stat value={data.stats.papers_read} label="papers read this month" i={2} />
          <Stat value={data.stats.notes_written} label="notes written this month" i={3} />
          <Stat value={data.stats.milestones_done} label="milestones completed" i={4} />
          <Stat value={data.inbox_count} label="inbox items to triage" i={5} to="/inbox" />
        </div>
      )}

      <div className="grid gap-4 lg:grid-cols-3">
        <section className={`${panel} rise`} style={{ ["--i" as string]: 6 }}>
          <h2 className={h2}>Active projects</h2>
          <div className="space-y-3">
            {data.active.map((p) => (
              <Link key={p.slug} to={`/projects/${p.slug}`} className="group -mx-2 flex items-center gap-3 rounded-xl px-2 py-1.5 transition-colors hover:bg-stone-50 dark:hover:bg-stone-800">
                <OrbitRing percent={p.percent} color={p.color} />
                <span className="min-w-0 flex-1">
                  <span className="block truncate text-sm font-medium group-hover:text-indigo-700 dark:text-stone-100 dark:group-hover:text-indigo-300">{p.name}</span>
                  <span className="block truncate text-xs text-stone-400 dark:text-stone-400">
                    {p.phase ? `${p.phase} · ` : ""}{p.done}/{p.total} milestones
                  </span>
                </span>
                <span className="font-display shrink-0 text-sm font-semibold tabular-nums text-stone-500 dark:text-stone-300">{p.percent}%</span>
              </Link>
            ))}
            {data.active.length === 0 && (
              <p className="text-sm text-stone-400 dark:text-stone-400">
                No active projects. <Link to="/projects" className="text-indigo-600 hover:text-indigo-700 dark:text-indigo-400 dark:hover:text-indigo-300">Start one →</Link>
              </p>
            )}
          </div>
        </section>

        <section className={`${panel} rise`} style={{ ["--i" as string]: 7 }}>
          <h2 className={h2}>Deadlines</h2>
          <ul className="space-y-0.5 text-sm">
            {data.deadlines.map((d) => (
              <li key={d.url + d.title}>
                <a href={d.url} className={row}>
                  <span aria-hidden="true" className="text-stone-300 dark:text-stone-500">✍</span>
                  <span className="min-w-0 flex-1 truncate font-medium dark:text-stone-100">{d.title}</span>
                  <span className="shrink-0 text-xs tabular-nums text-stone-400 dark:text-stone-400">{d.deadline}</span>
                </a>
              </li>
            ))}
            {data.deadlines.length === 0 && (
              <li className="text-sm text-stone-400 dark:text-stone-400">
                Manuscript deadlines show up here. <Link to="/writing" className="text-indigo-600 hover:text-indigo-700 dark:text-indigo-400 dark:hover:text-indigo-300">Open Writing →</Link>
              </li>
            )}
          </ul>
        </section>

        <section className={`${panel} rise`} style={{ ["--i" as string]: 8 }}>
          <h2 className={h2}>Upcoming milestones</h2>
          <ul className="space-y-0.5 text-sm">
            {data.milestones.map((m) => (
              <li key={m.url + m.title}>
                <a href={m.url} className={row}>
                  <span aria-hidden="true" className={`h-1.5 w-1.5 shrink-0 self-center rounded-full ${m.overdue ? "bg-red-400 shadow-[0_0_8px_rgba(248,113,113,0.8)]" : "bg-indigo-400 shadow-[0_0_8px_rgba(139,124,255,0.7)]"}`} />
                  <span className="min-w-0 flex-1 truncate dark:text-stone-100">{m.title}</span>
                  <span className={`shrink-0 text-xs tabular-nums ${m.overdue ? "font-medium text-red-600 dark:text-red-300" : "text-stone-400 dark:text-stone-400"}`}>
                    {m.due_date}{m.overdue ? " · overdue" : ""}
                  </span>
                </a>
              </li>
            ))}
            {data.milestones.length === 0 && (
              <li className="text-sm text-stone-400 dark:text-stone-400">Nothing scheduled — add milestones inside a project plan.</li>
            )}
          </ul>
        </section>
      </div>
    </div>
  );
}
