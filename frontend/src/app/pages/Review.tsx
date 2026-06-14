/**
 * Weekly research review ([REV] cycle 85): a calm, skimmable "this week" digest —
 * the page you read every Friday. Cross-project (/review) or scoped
 * (/projects/:slug/review), with week-back navigation.
 */
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";

type Review = {
  start: string;
  end: string;
  weeks_back: number;
  project: string | null;
  papers_read: { key: string; title: string; project: string; project_slug: string; reference_id: number }[];
  notes_written: { id: number; title: string; project: string; project_slug: string }[];
  milestones_done: { title: string; project: string; project_slug: string }[];
  decisions: { title: string; project: string; project_slug: string }[];
  experiments: { title: string; date: string; project: string; project_slug: string }[];
};

function Section<T>({ title, items, render, empty }: {
  title: string; items: T[]; render: (x: T) => React.ReactNode; empty: string;
}) {
  return (
    <section className="rounded border border-stone-200 bg-white p-5">
      <h2 className="mb-3 flex items-baseline gap-2 text-sm font-medium uppercase tracking-wide text-stone-400">
        {title}
        {items.length > 0 && <span className="text-stone-300">{items.length}</span>}
      </h2>
      {items.length === 0 ? (
        <p className="text-sm text-stone-400">{empty}</p>
      ) : (
        <ul className="space-y-2">{items.map((x, i) => <li key={i} className="text-sm">{render(x)}</li>)}</ul>
      )}
    </section>
  );
}

export default function Review() {
  const { slug } = useParams();
  const [weeksBack, setWeeksBack] = useState(0);
  const [copied, setCopied] = useState(false);
  const qs = `?weeks_back=${weeksBack}${slug ? `&project=${slug}` : ""}`;
  const { data, isLoading } = useQuery({
    queryKey: ["review", slug ?? null, weeksBack],
    queryFn: () => api<Review>(`/weekly-review/${qs}`),
  });

  function asMarkdown(d: Review): string {
    const lines: string[] = [`# Research week: ${d.start} – ${d.end}${d.project ? ` (${d.project})` : ""}`, ""];
    const sec = (title: string, items: string[]) => {
      if (!items.length) return;
      lines.push(`## ${title}`, ...items.map((x) => `- ${x}`), "");
    };
    sec("Papers read", d.papers_read.map((p) => `${p.title} (${p.key})`));
    sec("Milestones completed", d.milestones_done.map((m) => m.title));
    sec("Notes written", d.notes_written.map((n) => n.title));
    sec("Decisions", d.decisions.map((x) => x.title));
    sec("Experiments", d.experiments.map((e) => `${e.title} (${e.date})`));
    return lines.join("\n").trim();
  }

  async function copyWeek() {
    if (!data) return;
    await navigator.clipboard.writeText(asMarkdown(data));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  if (isLoading || !data) return <p className="text-sm text-stone-400">Assembling your week…</p>;

  const total =
    data.papers_read.length + data.notes_written.length + data.milestones_done.length +
    data.decisions.length + data.experiments.length;
  const fmt = (d: string) => new Date(d + "T00:00").toLocaleDateString(undefined, { month: "short", day: "numeric" });
  const scope = slug ? <Link to={`/projects/${slug}`} className="hover:underline">{slug}</Link> : "everywhere";

  return (
    <div>
      <div className="mb-1 flex items-center justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">
          {weeksBack === 0 ? "This week" : weeksBack === 1 ? "Last week" : `${weeksBack} weeks ago`}
        </h1>
        <div className="flex items-center gap-2 text-sm">
          <button onClick={copyWeek}
                  className="rounded border border-stone-300 bg-white px-2.5 py-1 text-xs hover:border-stone-400">
            {copied ? "✓ Copied" : "⧉ Copy week"}
          </button>
          <div className="flex items-center gap-1">
            <button onClick={() => setWeeksBack((w) => w + 1)}
                    className="rounded border border-stone-300 bg-white px-2 py-1 hover:border-stone-400" aria-label="Previous week">◀</button>
            <button onClick={() => setWeeksBack((w) => Math.max(0, w - 1))} disabled={weeksBack === 0}
                    className="rounded border border-stone-300 bg-white px-2 py-1 hover:border-stone-400 disabled:opacity-40" aria-label="Next week">▶</button>
          </div>
        </div>
      </div>
      <p className="mb-6 text-sm text-stone-500">
        {fmt(data.start)} – {fmt(data.end)} · {scope}
        {total > 0 && <> · <span className="text-stone-700">{total} things happened</span></>}
      </p>

      {total === 0 ? (
        <div className="rounded border border-dashed border-stone-300 bg-white p-10 text-center">
          <p className="mb-1 text-3xl">🌤️</p>
          <p className="text-sm text-stone-500">A quiet week — nothing logged. That's allowed.</p>
        </div>
      ) : (
        <div className="grid grid-cols-2 gap-4">
          <Section title="Papers read" items={data.papers_read} empty="No papers marked read."
            render={(p) => (
              <Link to={`/references/${p.reference_id}`} className="flex items-baseline gap-2 hover:text-indigo-700">
                <span className="rounded bg-stone-100 px-1 py-0.5 font-mono text-[10px] text-stone-500">{p.key}</span>
                <span className="min-w-0 flex-1 truncate">{p.title}</span>
                {!slug && <span className="shrink-0 text-xs text-stone-400">{p.project}</span>}
              </Link>
            )} />
          <Section title="Milestones completed" items={data.milestones_done} empty="No milestones checked off."
            render={(m) => (
              <div className="flex items-baseline gap-2">
                <span aria-hidden="true">✓</span>
                <span className="min-w-0 flex-1 truncate">{m.title}</span>
                {!slug && <span className="shrink-0 text-xs text-stone-400">{m.project}</span>}
              </div>
            )} />
          <Section title="Notes written" items={data.notes_written} empty="No new notes."
            render={(n) => (
              <Link to={`/projects/${n.project_slug}/notes/${n.id}`} className="flex items-baseline gap-2 hover:text-indigo-700">
                <span className="min-w-0 flex-1 truncate">{n.title}</span>
                {!slug && <span className="shrink-0 text-xs text-stone-400">{n.project}</span>}
              </Link>
            )} />
          <Section title="Decisions" items={data.decisions} empty="No decisions recorded."
            render={(d) => (
              <div className="flex items-baseline gap-2">
                <span className="min-w-0 flex-1 truncate">{d.title}</span>
                {!slug && <span className="shrink-0 text-xs text-stone-400">{d.project}</span>}
              </div>
            )} />
          {data.experiments.length > 0 && (
            <Section title="Experiments" items={data.experiments} empty=""
              render={(e) => (
                <div className="flex items-baseline gap-2">
                  <span className="min-w-0 flex-1 truncate">{e.title}</span>
                  <span className="shrink-0 text-xs text-stone-400">{e.date}{!slug ? ` · ${e.project}` : ""}</span>
                </div>
              )} />
          )}
        </div>
      )}
    </div>
  );
}
