/** #521 — the phase report card: planned vs actual window, how every milestone landed,
 *  drift and moves, the questions the phase carried — and "Close phase", which sets the
 *  status to done and files the report with the lessons as a decision record.
 *  Data: GET /phases/{id}/report/; closing: POST /phases/{id}/close/ {lessons}. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Check, ClipboardCopy, FileCheck, X } from "lucide-react";
import { api } from "../../api";
import { ErrorState } from "../../../components/ErrorState";
import { Skeleton } from "../../../components/Skeleton";

type Row = { id: number; title: string; due_date: string | null; baseline: string | null; landed: string | null; late: number | null; late_first: number | null; bucket: string | null; moves: number; done: boolean };
export type PhaseReportData = { id: number; name: string; status: string; objective: string; planned_start: string | null; planned_end: string | null; actual_end: string | null; overrun: number | null; counts: { total: number; done: number; open: number; on_time: number }; median_late: number | null; drift: number; moves: number; milestones: Row[]; questions: { id: number; question: string; status: string }[]; closable: boolean; markdown: string };

const days = (n: number | null, late = "late", early = "early") => (n == null ? "—" : n === 0 ? "on the day" : n > 0 ? `${n} d ${late}` : `${-n} d ${early}`);
const lateCls = (n: number | null) => (n == null ? "text-stone-400" : n <= 0 ? "text-emerald-600 dark:text-emerald-300" : n <= 7 ? "text-stone-600 dark:text-stone-300" : "text-amber-700 dark:text-amber-300");

export default function PhaseReport({ slug, phaseId, onClose, onClosed }: { slug: string; phaseId: number; onClose: () => void; onClosed: (name: string, decisionId: number) => void }) {
  const queryClient = useQueryClient();
  const { data, isLoading, error, refetch } = useQuery({ queryKey: ["phase-report", phaseId], queryFn: () => api<PhaseReportData>(`/phases/${phaseId}/report/`) });
  const [lessons, setLessons] = useState("");
  const [copied, setCopied] = useState(false);
  const close = useMutation({
    mutationFn: () => api<{ report: PhaseReportData; decision_id: number }>(`/phases/${phaseId}/close/`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ lessons }) }),
    onSuccess: (out) => { queryClient.invalidateQueries({ queryKey: ["plan", slug] }); queryClient.invalidateQueries({ queryKey: ["roadmap", slug] }); queryClient.invalidateQueries({ queryKey: ["overview", slug] }); queryClient.invalidateQueries({ queryKey: ["phase-report", phaseId] }); onClosed(out.report.name, out.decision_id); },
  });
  useEffect(() => { const onKey = (e: KeyboardEvent) => { if (e.key === "Escape") onClose(); }; window.addEventListener("keydown", onKey); return () => window.removeEventListener("keydown", onKey); }, [onClose]);
  const copy = async () => { if (!data) return; try { await navigator.clipboard.writeText(data.markdown); setCopied(true); setTimeout(() => setCopied(false), 1500); } catch { /* clipboard unavailable */ } };
  return (
    <aside className="drawer-solid rise fixed inset-y-0 right-0 z-30 w-full max-w-lg overflow-y-auto border-l border-stone-200 p-5 shadow-2xl dark:border-stone-800" role="dialog" aria-label={data ? `Phase report: ${data.name}` : "Phase report"} data-testid="phase-report">
      <div className="mb-3 flex items-center justify-between text-[10px] font-semibold uppercase tracking-[0.14em] text-stone-400">
        <span><FileCheck className="mr-1 inline h-3 w-3" aria-hidden="true" />Phase report</span>
        <span className="flex items-center gap-2 normal-case tracking-normal">
          {data && <button type="button" onClick={() => void copy()} className="inline-flex items-center gap-1 rounded-md px-1.5 py-0.5 text-[11px] text-stone-500 hover:bg-stone-100 dark:hover:bg-stone-800" title="Copy the report as Markdown"><ClipboardCopy className="h-3 w-3" aria-hidden="true" />{copied ? "copied" : "copy"}</button>}
          <button type="button" onClick={onClose} aria-label="Close" className="rounded-md p-1 hover:bg-stone-100 dark:hover:bg-stone-800"><X className="h-4 w-4" aria-hidden="true" /></button>
        </span>
      </div>
      {error ? (
        <ErrorState message="Couldn't load the phase report." onRetry={() => refetch()} />
      ) : isLoading || !data ? (
        <div className="space-y-3"><Skeleton className="h-7 w-2/3" /><Skeleton className="h-16 w-full" /><Skeleton className="h-32 w-full" /></div>
      ) : (
        <>
          <h2 className="font-display text-xl font-semibold leading-snug text-stone-900 dark:text-stone-100">{data.name}</h2>
          {data.objective && <p className="mt-1 text-sm text-stone-500 dark:text-stone-400">{data.objective}</p>}
          <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-2 text-sm" data-testid="report-facts">
            <div><dt className="text-[10px] font-semibold uppercase tracking-[0.14em] text-stone-400">Milestones</dt><dd className="text-stone-800 dark:text-stone-100">{data.counts.done}/{data.counts.total} done <span className="text-stone-400">· {data.counts.on_time} on time</span></dd></div>
            <div><dt className="text-[10px] font-semibold uppercase tracking-[0.14em] text-stone-400">Landing</dt><dd className={lateCls(data.median_late)}>median {days(data.median_late)}</dd></div>
            <div><dt className="text-[10px] font-semibold uppercase tracking-[0.14em] text-stone-400">Planned end</dt><dd className="text-stone-800 dark:text-stone-100">{data.planned_end ?? "—"}</dd></div>
            <div><dt className="text-[10px] font-semibold uppercase tracking-[0.14em] text-stone-400">Actual end</dt><dd className="text-stone-800 dark:text-stone-100">{data.actual_end ?? (data.counts.open ? `${data.counts.open} still open` : "—")} {data.overrun != null && <span className={`ml-1 rounded-md px-1.5 py-0.5 text-[11px] ${data.overrun > 0 ? "bg-amber-500/10 text-amber-800 dark:text-amber-200" : "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300"}`} data-testid="report-overrun">{days(data.overrun, "over", "under")}</span>}</dd></div>
            <div><dt className="text-[10px] font-semibold uppercase tracking-[0.14em] text-stone-400">Drift</dt><dd className="text-stone-800 dark:text-stone-100">{data.drift > 0 ? `+${data.drift}` : data.drift} d <span className="text-stone-400">· {data.moves} move{data.moves === 1 ? "" : "s"}</span></dd></div>
            <div><dt className="text-[10px] font-semibold uppercase tracking-[0.14em] text-stone-400">Questions</dt><dd className="text-stone-800 dark:text-stone-100">{data.questions.length ? `${data.questions.filter((q) => q.status === "answered").length}/${data.questions.length} answered` : "none attached"}</dd></div>
          </dl>
          <table className="mt-4 w-full text-xs" data-testid="report-table">
            <thead><tr className="text-left text-[10px] font-semibold uppercase tracking-[0.14em] text-stone-400"><th className="pb-1 font-semibold">Milestone</th><th className="pb-1 font-semibold">first</th><th className="pb-1 font-semibold">held</th><th className="pb-1 font-semibold">landed</th></tr></thead>
            <tbody className="divide-y divide-stone-100 dark:divide-stone-800">
              {data.milestones.map((m) => (
                <tr key={m.id} className="align-top">
                  <td className="py-1.5 pr-2 text-stone-800 dark:text-stone-100">{m.done && <Check className="mr-1 inline h-3 w-3 text-emerald-500" aria-hidden="true" />}{m.title}</td>
                  <td className="py-1.5 pr-2 whitespace-nowrap text-stone-400">{m.baseline ?? "—"}{m.moves > 0 && <span className="ml-1 text-[10px]">· {m.moves}×</span>}</td>
                  <td className="py-1.5 pr-2 whitespace-nowrap text-stone-500 dark:text-stone-400">{m.due_date ?? "—"}</td>
                  <td className={`py-1.5 whitespace-nowrap ${lateCls(m.late)}`}>{m.landed ? `${m.landed} · ${days(m.late)}` : "open"}</td>
                </tr>
              ))}
            </tbody>
          </table>
          {data.questions.length > 0 && (
            <ul className="mt-3 space-y-1 text-xs text-stone-600 dark:text-stone-300">
              {data.questions.map((q) => <li key={q.id} className="flex items-start gap-2"><span className={`mt-0.5 shrink-0 rounded-full px-1.5 py-px text-[10px] ${q.status === "answered" ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300" : "bg-stone-100 text-stone-500 dark:bg-stone-800 dark:text-stone-400"}`}>{q.status.replace("_", " ")}</span><span>{q.question}</span></li>)}
            </ul>
          )}
          <div className="mt-6 border-t border-stone-100 pt-4 dark:border-stone-800">
            {data.status === "done" ? (
              <p className="text-xs text-stone-400">This phase is closed. Its report lives in the decision log.</p>
            ) : (
              <>
                <p className="mb-1 text-[10px] font-semibold uppercase tracking-[0.14em] text-stone-400">What did this phase teach you?</p>
                <textarea value={lessons} onChange={(e) => setLessons(e.target.value)} rows={4} maxLength={4000} placeholder="Recruitment took two weeks longer than planned; book the lab before ethics clears next time. Markdown; becomes the decision." className="w-full resize-y rounded-lg border border-stone-200 bg-stone-50 px-3 py-2 text-sm leading-relaxed placeholder:text-stone-400 focus:border-indigo-400 focus:outline-none dark:border-stone-800 dark:bg-stone-950/40 dark:text-stone-200" aria-label="Lessons from this phase" data-testid="report-lessons" />
                {!data.closable && data.counts.open > 0 && <p className="mt-1 text-xs text-stone-400">{data.counts.open} milestone{data.counts.open === 1 ? "" : "s"} still open — closing files the report as it stands.</p>}
                <button type="button" onClick={() => close.mutate()} disabled={close.isPending} className="mt-3 inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50" data-testid="phase-close"><FileCheck className="h-4 w-4" aria-hidden="true" />{close.isPending ? "Closing…" : "Close phase"}</button>
                {close.isError && <p className="mt-2 text-xs text-red-600 dark:text-red-300" role="alert">Couldn't close the phase. Try again.</p>}
              </>
            )}
          </div>
        </>
      )}
    </aside>
  );
}
