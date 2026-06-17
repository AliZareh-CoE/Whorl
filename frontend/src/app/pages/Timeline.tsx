/**
 * Research timeline ([REV] cycle 95): one chronological stream of everything that
 * happened in a project — for reconstructing the story of the work, and for pasting
 * a chronology into a paper's methods/history section.
 *
 * Vertical layout with period grouping as the "zoom" (day/week/month); kinds are
 * color-coded and filterable. Quiet axis, content forward.
 */
import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";

type Event = { date: string; kind: string; label: string; detail: string; url: string };

const KINDS: Record<string, { label: string; dot: string }> = {
  milestone: { label: "Milestone", dot: "bg-indigo-500" },
  paper_added: { label: "Paper added", dot: "bg-sky-400" },
  paper_read: { label: "Paper read", dot: "bg-green-500" },
  note: { label: "Note", dot: "bg-amber-400" },
  decision: { label: "Decision", dot: "bg-rose-500" },
  experiment: { label: "Experiment", dot: "bg-violet-500" },
  hypothesis: { label: "Hypothesis", dot: "bg-fuchsia-400" },
  document: { label: "Document", dot: "bg-stone-400" },
  manuscript: { label: "Manuscript", dot: "bg-emerald-500" },
  manuscript_compiled: { label: "Compiled", dot: "bg-teal-500" },
};

const ZOOMS = ["month", "week", "day"] as const;
type Zoom = (typeof ZOOMS)[number];

function periodOf(date: string, zoom: Zoom): string {
  const d = new Date(`${date}T00:00:00`);
  if (zoom === "day") return date;
  if (zoom === "week") {
    const monday = new Date(d);
    monday.setDate(d.getDate() - ((d.getDay() + 6) % 7));
    return monday.toISOString().slice(0, 10);
  }
  return date.slice(0, 7);
}

function periodLabel(period: string, zoom: Zoom): string {
  if (zoom === "month")
    return new Date(`${period}-01T00:00:00`).toLocaleDateString(undefined, {
      month: "long", year: "numeric",
    });
  const d = new Date(`${period}T00:00:00`).toLocaleDateString(undefined, {
    day: "numeric", month: "short", year: "numeric",
  });
  return zoom === "week" ? `Week of ${d}` : d;
}

export default function Timeline() {
  const { slug } = useParams();
  const [zoom, setZoom] = useState<Zoom>("month");
  const [hidden, setHidden] = useState<Set<string>>(new Set());
  const [copied, setCopied] = useState(false);

  const { data, isLoading } = useQuery({
    queryKey: ["timeline", slug],
    queryFn: () => api<{ events: Event[] }>(`/projects/${slug}/timeline/`),
  });

  const events = useMemo(
    () => (data?.events ?? []).filter((e) => !hidden.has(e.kind)),
    [data, hidden],
  );
  const groups = useMemo(() => {
    const byPeriod = new Map<string, Event[]>();
    for (const e of events) {
      const p = periodOf(e.date, zoom);
      byPeriod.set(p, [...(byPeriod.get(p) ?? []), e]);
    }
    return [...byPeriod.entries()];
  }, [events, zoom]);
  const presentKinds = useMemo(
    () => Object.keys(KINDS).filter((k) => (data?.events ?? []).some((e) => e.kind === k)),
    [data],
  );

  async function copyMarkdown() {
    const lines = [`# Timeline — ${slug}`, ""];
    for (const e of [...events].reverse()) {
      const detail = e.detail ? ` (${e.detail})` : "";
      lines.push(`- **${e.date}** · ${KINDS[e.kind]?.label ?? e.kind}: ${e.label}${detail}`);
    }
    await navigator.clipboard.writeText(lines.join("\n"));
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  if (isLoading) return <p className="text-sm text-stone-400">Assembling the timeline…</p>;

  return (
    <div className="mx-auto max-w-3xl">
      <nav className="mb-6 text-sm text-stone-500">
        <Link to="/projects" className="hover:underline">Projects</Link> /{" "}
        <Link to={`/projects/${slug}`} className="hover:underline">{slug}</Link> / Timeline
      </nav>
      <div className="mb-2 flex items-baseline justify-between gap-4">
        <h1 className="text-2xl font-semibold tracking-tight">Timeline</h1>
        <div className="flex shrink-0 items-center gap-2 text-xs">
          <div className="flex overflow-hidden rounded border border-stone-300" role="group" aria-label="Zoom">
            {ZOOMS.map((z) => (
              <button key={z} onClick={() => setZoom(z)}
                      aria-pressed={z === zoom}
                      className={`px-2.5 py-1 capitalize transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-indigo-500 ${
                        z === zoom ? "bg-stone-800 text-white" : "bg-white text-stone-600 hover:bg-stone-50"
                      }`}>
                {z}
              </button>
            ))}
          </div>
          <button onClick={copyMarkdown}
                  className="rounded border border-stone-300 bg-white px-2.5 py-1 text-stone-600 transition-colors hover:border-stone-400 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500">
            {copied ? "✓ Copied" : "⧉ Copy as markdown"}
          </button>
        </div>
      </div>
      <p className="mb-5 text-sm text-stone-500">
        The story of the project, newest first — copy it oldest-first for a methods or history section.
      </p>

      {presentKinds.length > 0 && (
        <div className="mb-8 flex flex-wrap gap-1.5">
          {presentKinds.map((k) => {
            const off = hidden.has(k);
            return (
              <button key={k}
                      onClick={() => {
                        const next = new Set(hidden);
                        off ? next.delete(k) : next.add(k);
                        setHidden(next);
                      }}
                      aria-pressed={!off}
                      className={`flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-xs transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-1 ${
                        off
                          ? "border-stone-200 bg-stone-50 text-stone-400 hover:border-stone-300"
                          : "border-stone-300 bg-white text-stone-700 hover:border-stone-400"
                      }`}>
                <span className={`size-2 rounded-full ${off ? "bg-stone-300" : KINDS[k].dot}`} />
                {KINDS[k].label}
              </button>
            );
          })}
        </div>
      )}

      {groups.length === 0 ? (
        <div className="rounded border border-dashed border-stone-300 bg-white p-10 text-center">
          {hidden.size > 0 ? (
            <>
              <p className="mb-1 text-sm font-medium text-stone-600">Nothing matches the current filters</p>
              <p className="text-sm text-stone-400">Re-enable an event type above to see it in the timeline.</p>
            </>
          ) : (
            <>
              <p className="mb-1 text-sm font-medium text-stone-600">No dated activity yet</p>
              <p className="text-sm text-stone-400">
                Completed milestones, papers, notes, and decisions will gather here as the work unfolds.
              </p>
            </>
          )}
        </div>
      ) : (
        <div className="relative pl-7">
          <div className="absolute inset-y-1 left-[3px] w-px bg-stone-200" aria-hidden />
          {groups.map(([period, items]) => (
            <section key={period} className="mb-10 last:mb-0">
              <h2 className="sticky top-0 z-10 -ml-7 mb-4 flex items-baseline gap-2 bg-stone-50/95 py-1.5 pl-7 text-sm font-medium uppercase tracking-wide text-stone-400 backdrop-blur-sm">
                {periodLabel(period, zoom)}
                <span className="text-xs font-normal normal-case tracking-normal text-stone-300">
                  {items.length} {items.length === 1 ? "event" : "events"}
                </span>
              </h2>
              <ul className="space-y-3.5">
                {items.map((e, i) => (
                  <li key={`${e.date}-${e.kind}-${i}`} className="group relative text-sm">
                    <span className={`absolute -left-[26px] top-[7px] size-2.5 rounded-full ring-4 ring-stone-50 ${KINDS[e.kind]?.dot ?? "bg-stone-300"}`} aria-hidden />
                    <Link
                      to={e.url}
                      className="-mx-2 flex flex-col gap-0.5 rounded px-2 py-1 transition-colors hover:bg-white focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-indigo-500 focus-visible:ring-offset-1 sm:flex-row sm:items-baseline sm:gap-2"
                    >
                      <span className="font-medium text-stone-800 group-hover:text-indigo-700">
                        {e.label}
                      </span>
                      <span className="text-xs text-stone-400">
                        {KINDS[e.kind]?.label ?? e.kind}
                        {e.detail ? ` · ${e.detail}` : ""}
                        {zoom !== "day" ? ` · ${e.date}` : ""}
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      )}
    </div>
  );
}
