/* Library health (the bib report, moved into the app 2026-09-06): the four checkers —
 * duplicates, missing required fields, DOI resolution, retractions — as one page with the
 * fixes at hand: merge duplicates in place, jump to a paper to complete it. Network checks
 * (Crossref) run only when asked, so the page opens instantly. */
import { useMemo, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link, useParams } from "react-router-dom";
import { AlertTriangle, CheckCircle2, Copy, Globe, Loader2, Merge, ShieldAlert, XCircle } from "lucide-react";
import { api } from "../api";
import { confirmDialog } from "../../components/Dialog";
import { ErrorState } from "../../components/ErrorState";

type Finding = { level: string; message: string; reference_ids: number[] };
type Report = { network_checks_included: boolean; findings: Record<string, Finding[]> };
type Ref = { id: number; bibtex_key: string; title: string; year: number | null; doi: string | null };
type Page<T> = { count: number; results: T[] };

const panel = "rise rounded-2xl border border-stone-200 bg-white/70 p-5 backdrop-blur dark:border-stone-800 dark:bg-stone-900/60";
const railH = "text-[11px] font-semibold uppercase tracking-wider text-stone-400";
const CATS: Record<string, { title: string; blurb: string; icon: typeof Copy; network?: boolean }> = {
  duplicates: { title: "Duplicates", blurb: "same DOI, or titles that read the same", icon: Copy },
  missing_fields: { title: "Missing fields", blurb: "what BibTeX needs for this entry type", icon: AlertTriangle },
  doi_resolution: { title: "DOI resolution", blurb: "every DOI answered by doi.org", icon: Globe, network: true },
  retractions: { title: "Retractions", blurb: "Crossref retraction notices", icon: ShieldAlert, network: true },
};
const LEVEL: Record<string, string> = { error: "bg-red-500/15 text-red-700 dark:text-red-300", warning: "bg-amber-500/15 text-amber-700 dark:text-amber-300", info: "bg-indigo-500/15 text-indigo-700 dark:text-indigo-300" };

export default function Report() {
  const { slug } = useParams();
  const qc = useQueryClient();
  const [network, setNetwork] = useState(false);
  const report = useQuery({ queryKey: ["bib-report", slug, network], queryFn: () => api<Report>(`/projects/${slug}/bib-report/${network ? "?network=1" : ""}`) });
  const refs = useQuery({ queryKey: ["report-refs", slug], queryFn: () => api<Page<Ref>>(`/references/?project=${slug}&page_size=500`) });
  const byId = useMemo(() => new Map((refs.data?.results ?? []).map((r) => [r.id, r])), [refs.data]);
  const merge = useMutation({ mutationFn: (body: { keep: number; merge: number[] }) => api("/references/merge/", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) }), onSuccess: () => { qc.invalidateQueries({ queryKey: ["bib-report", slug] }); qc.invalidateQueries({ queryKey: ["report-refs", slug] }); } });
  const total = Object.values(report.data?.findings ?? {}).reduce((n, f) => n + f.length, 0);
  const cats = Object.keys(CATS).filter((c) => !CATS[c].network || network || (report.data?.findings[c]?.length ?? 0) > 0);

  return (
    <div>
      <nav className="mb-4 text-sm text-stone-400" aria-label="Breadcrumb"><Link to="/projects" className="hover:underline">Projects</Link> / <Link to={`/projects/${slug}`} className="hover:underline">{slug}</Link> / <Link to={`/projects/${slug}/literature`} className="hover:underline">Literature</Link> / Health</nav>
      <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
        <div>
          <h1 className="text-3xl font-semibold tracking-tight">Library health{report.data && <> · <span className={total ? "text-gradient" : "text-emerald-500"}>{total ? `${total} finding${total === 1 ? "" : "s"}` : "clean"}</span></>}</h1>
          <p className="mt-1 text-sm text-stone-500">Duplicates, incomplete entries, dead DOIs and retractions across this project's {refs.data?.count ?? "…"} papers. Fix them here before they reach a manuscript.</p>
        </div>
        <label className="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-stone-200 bg-white px-3 py-1.5 text-sm dark:border-stone-700 dark:bg-stone-900" title="Ask doi.org and Crossref about every DOI — takes a few seconds per paper">
          <input type="checkbox" checked={network} onChange={(e) => setNetwork(e.target.checked)} className="accent-indigo-600" />
          <Globe className="h-4 w-4 text-stone-400" aria-hidden="true" />Run network checks
        </label>
      </div>

      {report.isLoading && <p className="flex items-center gap-2 text-sm text-stone-400"><Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />{network ? "Asking doi.org and Crossref about every DOI…" : "Checking the library…"}</p>}
      {report.isError && <ErrorState message="Couldn't run the bib report." onRetry={() => void report.refetch()} />}
      {report.error && <p className="text-sm text-red-500">The report could not be built.</p>}

      {report.data && (
        <div className="grid gap-5 lg:grid-cols-2">
          {cats.map((cat, i) => {
            const meta = CATS[cat]; const Icon = meta.icon; const rows = report.data.findings[cat] ?? [];
            return (
              <section key={cat} className={panel} style={{ ["--i" as string]: i + 1 }} data-testid={`report-${cat}`}>
                <div className="mb-3 flex items-center gap-2"><Icon className="h-4 w-4 text-stone-400" aria-hidden="true" /><p className={`${railH} mb-0`}>{meta.title} <span className="normal-case tracking-normal text-stone-400">{rows.length}</span></p><span className="ml-auto text-[11px] text-stone-400">{meta.blurb}</span></div>
                {rows.length === 0 ? (
                  <p className="flex items-center gap-1.5 text-sm text-emerald-600 dark:text-emerald-400"><CheckCircle2 className="h-4 w-4" aria-hidden="true" />{meta.network && !network ? "Not checked yet — turn on network checks." : "Nothing to fix."}</p>
                ) : (
                  <ul className="divide-y divide-stone-100 dark:divide-stone-800">
                    {rows.map((f, j) => (
                      <li key={j} className="py-2.5 text-sm">
                        <div className="flex items-start gap-2">
                          <span className={`mt-0.5 shrink-0 rounded-full px-1.5 py-0.5 text-[10px] font-semibold uppercase ${LEVEL[f.level] ?? LEVEL.info}`}>{f.level}</span>
                          <p className="min-w-0 flex-1 text-stone-700 dark:text-stone-200">{f.message}</p>
                          {cat === "duplicates" && f.reference_ids.length > 1 && (
                            <button type="button" onClick={async () => { const [keep, ...rest] = f.reference_ids; const k = byId.get(keep); if (await confirmDialog({ title: `Merge ${rest.length} duplicate${rest.length === 1 ? "" : "s"} into “${k?.title ?? keep}”?`, body: "Project links, notes and highlights move over to the kept entry.", confirmLabel: "Merge" })) merge.mutate({ keep, merge: rest }); }} disabled={merge.isPending} className="inline-flex shrink-0 items-center gap-1 rounded-md bg-indigo-600 px-2 py-1 text-xs font-medium text-white hover:bg-indigo-700 disabled:opacity-50"><Merge className="h-3 w-3" aria-hidden="true" />Merge into first</button>
                          )}
                        </div>
                        <ul className="mt-1.5 flex flex-wrap gap-x-3 gap-y-1 pl-1 text-xs">
                          {f.reference_ids.map((id) => { const r = byId.get(id); return <li key={id}><Link to={`/references/${id}`} className="text-indigo-600 hover:underline dark:text-indigo-300" title={r?.title}>@{r?.bibtex_key ?? id}</Link>{r?.year ? <span className="text-stone-400"> · {r.year}</span> : null}</li>; })}
                        </ul>
                      </li>
                    ))}
                  </ul>
                )}
              </section>
            );
          })}
        </div>
      )}
      {merge.error && <p className="mt-3 flex items-center gap-1 text-sm text-red-500"><XCircle className="h-4 w-4" aria-hidden="true" />The merge failed.</p>}
      <p className="mt-6 text-xs text-stone-400">Also from Claude Code: <em>“run a bib check on this project”</em> (`run_bib_check`).</p>
    </div>
  );
}
