/** Research v2 (Observatory): the hypothesis ledger with evidence you can add in place (from a
 *  paper in the project's literature, a note, or plain text), an evidence balance with a
 *  suggested status, a lab-notebook experiment log linked to hypotheses, datasets, protocols.
 *  Everything here is also in the API (/hypotheses/, /evidence/, /experiments/, /datasets/) and MCP. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Check, FlaskConical, HelpCircle, Minus, Pencil, Plus, Scale, Trash2, X } from "lucide-react";
import { api, petReact } from "../api";
import { ErrorState } from "../../components/ErrorState";
import { Skeleton } from "../../components/Skeleton";
import { confirmDialog, errorDialog, promptDialog } from "../../components/Dialog";
import { Kebab, type MenuItem } from "../../components/Menu";
import { Prose } from "../../components/Prose";

type Evidence = { id: number; direction: "supports" | "contradicts" | "mixed"; summary: string; reference: number | null; reference_detail: { id: number; bibtex_key: string; title: string } | null; note: number | null; note_title: string; created_at: string };
type Hypothesis = { id: number; statement: string; status: string; supports: number; contradicts: number; mixed: number; suggested_status: string | null; evidence: Evidence[] };
type Experiment = { id: number; date: string; title: string; body: string; body_html: string; commit_url: string; commit_label: string; hypotheses: number[] };
type Dataset = { id: number; name: string; location: string; version: string; description: string };
type Question = { id: number; question: string; status: string; phases: number[] };
const Q_STATUSES = ["open", "partially_answered", "answered", "abandoned"];
const qCls: Record<string, string> = { open: "bg-indigo-500/15 text-indigo-700 dark:text-indigo-200", partially_answered: "bg-amber-500/15 text-amber-700 dark:text-amber-300", answered: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300", abandoned: "bg-stone-100 text-stone-400 line-through dark:bg-stone-800" };
type Protocol = { id: number; title: string; body: string; body_html: string; version: number; is_current: boolean };
type Page<T> = { count: number; results: T[] };
type Suggestion = { id: number; label: string; sublabel: string };

const panel = "rounded-2xl border border-stone-200 bg-white dark:border-stone-800 dark:bg-stone-900";
const railH = "mb-2 text-[10px] font-semibold uppercase tracking-[0.14em] text-stone-400 dark:text-stone-500";
const JSON_H = { "Content-Type": "application/json" };
const STATUSES = ["proposed", "testing", "supported", "contradicted", "inconclusive", "abandoned"];
const statusCls: Record<string, string> = { supported: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300", contradicted: "bg-red-500/15 text-red-700 dark:text-red-300", testing: "bg-indigo-500/15 text-indigo-700 dark:text-indigo-200", proposed: "bg-stone-100 text-stone-600 dark:bg-stone-800 dark:text-stone-300", inconclusive: "bg-amber-500/15 text-amber-700 dark:text-amber-300", abandoned: "bg-stone-100 text-stone-400 line-through dark:bg-stone-800" };
const DIR: Record<string, { label: string; cls: string; bar: string }> = { supports: { label: "supports", cls: "bg-emerald-500/15 text-emerald-700 dark:text-emerald-300", bar: "bg-emerald-500" }, contradicts: { label: "contradicts", cls: "bg-red-500/15 text-red-700 dark:text-red-300", bar: "bg-red-500" }, mixed: { label: "mixed", cls: "bg-amber-500/15 text-amber-700 dark:text-amber-300", bar: "bg-amber-500" } };
function useDebounced<T>(value: T, ms: number): T { const [v, setV] = useState(value); useEffect(() => { const t = setTimeout(() => setV(value), ms); return () => clearTimeout(t); }, [value, ms]); return v; }

export default function Research() {
  const { slug } = useParams();
  const queryClient = useQueryClient();
  const hyps = useQuery({ queryKey: ["hypotheses", slug], queryFn: () => api<Page<Hypothesis>>(`/hypotheses/?project=${slug}&page_size=100`) });
  const exps = useQuery({ queryKey: ["experiments", slug], queryFn: () => api<Page<Experiment>>(`/experiments/?project=${slug}&page_size=50`) });
  const dsets = useQuery({ queryKey: ["datasets", slug], queryFn: () => api<Page<Dataset>>(`/datasets/?project=${slug}&page_size=50`) });
  const protos = useQuery({ queryKey: ["protocols", slug], queryFn: () => api<Page<Protocol>>(`/protocols/?project=${slug}&page_size=50`) });
  const refresh = () => { queryClient.invalidateQueries({ queryKey: ["hypotheses", slug] }); queryClient.invalidateQueries({ queryKey: ["experiments", slug] }); queryClient.invalidateQueries({ queryKey: ["overview", slug] }); };
  const [statement, setStatement] = useState("");
  const addHyp = useMutation({ mutationFn: () => api("/hypotheses/", { method: "POST", headers: JSON_H, body: JSON.stringify({ project: slug, statement: statement.trim() }) }), onSuccess: () => { setStatement(""); refresh(); } });
  const setStatus = useMutation({ mutationFn: ({ id, status }: { id: number; status: string }) => api(`/hypotheses/${id}/`, { method: "PATCH", headers: JSON_H, body: JSON.stringify({ status }) }), onSettled: refresh });
  const delHyp = useMutation({ mutationFn: (id: number) => api(`/hypotheses/${id}/`, { method: "DELETE" }), onSuccess: refresh });
  const addEv = useMutation({ mutationFn: (body: Record<string, unknown>) => api("/evidence/", { method: "POST", headers: JSON_H, body: JSON.stringify(body) }), onSuccess: () => { petReact("paper"); refresh(); } });
  const delEv = useMutation({ mutationFn: (id: number) => api(`/evidence/${id}/`, { method: "DELETE" }), onSuccess: refresh });
  const addExp = useMutation({ mutationFn: (body: Record<string, unknown>) => api("/experiments/", { method: "POST", headers: JSON_H, body: JSON.stringify({ project: slug, ...body }) }), onSuccess: refresh });
  const fail = (title: string) => (e: unknown) => void errorDialog(title, e);
  const editHyp = useMutation({ mutationFn: ({ id, statement }: { id: number; statement: string }) => api(`/hypotheses/${id}/`, { method: "PATCH", headers: JSON_H, body: JSON.stringify({ statement }) }), onSettled: refresh, onError: fail("Couldn't save the hypothesis") });
  const patchExp = useMutation({ mutationFn: ({ id, ...body }: { id: number } & Record<string, unknown>) => api(`/experiments/${id}/`, { method: "PATCH", headers: JSON_H, body: JSON.stringify(body) }), onSuccess: refresh, onError: fail("Couldn't save the entry") });
  const delExp = useMutation({ mutationFn: (id: number) => api(`/experiments/${id}/`, { method: "DELETE" }), onSuccess: refresh, onError: fail("Couldn't delete the entry") });
  const patchDs = useMutation({ mutationFn: ({ id, ...body }: { id: number } & Record<string, unknown>) => api(`/datasets/${id}/`, { method: "PATCH", headers: JSON_H, body: JSON.stringify(body) }), onSuccess: () => queryClient.invalidateQueries({ queryKey: ["datasets", slug] }), onError: fail("Couldn't save the dataset") });
  const delDs = useMutation({ mutationFn: (id: number) => api(`/datasets/${id}/`, { method: "DELETE" }), onSuccess: () => queryClient.invalidateQueries({ queryKey: ["datasets", slug] }), onError: fail("Couldn't delete the dataset") });
  const addDs = useMutation({ mutationFn: (body: Record<string, unknown>) => api("/datasets/", { method: "POST", headers: JSON_H, body: JSON.stringify({ project: slug, ...body }) }), onSuccess: () => queryClient.invalidateQueries({ queryKey: ["datasets", slug] }) });

  if (hyps.isLoading) return <div className="space-y-3"><Skeleton className="h-8 w-56" /><Skeleton className="h-40 w-full" /></div>;
  if (hyps.error) return <ErrorState message="Couldn't load the research tools." onRetry={() => hyps.refetch()} />;
  const list = hyps.data?.results ?? [];
  const experiments = exps.data?.results ?? [];
  const datasets = dsets.data?.results ?? [];
  const protocols = (protos.data?.results ?? []).filter((p) => p.is_current);
  const evidenceTotal = list.reduce((n, h) => n + h.evidence.length, 0);
  return (
    <div>
      <nav className="mb-4 text-sm text-stone-500 dark:text-stone-400"><Link to="/projects" className="hover:underline">Projects</Link> / <Link to={`/projects/${slug}`} className="hover:underline">{slug}</Link> / Research</nav>
      <div className="mb-4 flex flex-wrap items-baseline gap-3">
        <h1 className="font-display text-3xl font-bold tracking-tight dark:text-stone-100">Research <span className="text-gradient">· {list.length} hypothes{list.length === 1 ? "is" : "es"}</span></h1>
        <p className="text-sm text-stone-400">{evidenceTotal} piece{evidenceTotal === 1 ? "" : "s"} of evidence · {experiments.length} experiment{experiments.length === 1 ? "" : "s"} · {datasets.length} dataset{datasets.length === 1 ? "" : "s"}</p>
      </div>
      <form onSubmit={(e) => { e.preventDefault(); if (statement.trim()) addHyp.mutate(); }} className={`${panel} hairline-gradient rise mb-4 flex items-center gap-2 p-2 pl-4`} data-testid="new-hypothesis">
        <FlaskConical className="h-4 w-4 shrink-0 text-indigo-400" aria-hidden="true" />
        <input value={statement} onChange={(e) => setStatement(e.target.value)} placeholder="Propose a hypothesis — a falsifiable sentence…" className="min-w-0 flex-1 bg-transparent py-2 text-base placeholder:text-stone-400 focus:outline-none dark:text-stone-100" aria-label="New hypothesis" />
        <button type="submit" disabled={!statement.trim() || addHyp.isPending} className="rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-40">Propose</button>
      </form>
      {list.length === 0 ? (
        <div className={`${panel} rise mb-4 p-8 text-center`} style={{ ["--i" as string]: 1 }}>
          <Scale className="mx-auto mb-2 h-7 w-7 text-indigo-400" aria-hidden="true" />
          <p className="font-medium text-stone-700 dark:text-stone-100">No hypotheses yet.</p>
          <p className="mx-auto mt-1 max-w-md text-sm text-stone-400">Write the claim you are betting on, then attach evidence from papers, notes and experiments as it comes in. The ledger keeps the balance honest.</p>
        </div>
      ) : (
        <div className="mb-4 space-y-3">
          {list.map((h, i) => <HypothesisCard key={h.id} h={h} i={i} slug={slug!} onStatus={(status) => setStatus.mutate({ id: h.id, status })} onEdit={async () => { const v = await promptDialog({ title: "Edit hypothesis", label: "Statement", initial: h.statement, multiline: true, validate: (x) => (x.trim() ? null : "Write the claim.") }); if (v && v.trim() !== h.statement) editHyp.mutate({ id: h.id, statement: v.trim() }); }} onDelete={async () => { if (await confirmDialog({ title: "Delete this hypothesis?", body: h.evidence.length ? `Its ${h.evidence.length} evidence row${h.evidence.length === 1 ? "" : "s"} go with it.` : undefined, danger: true, confirmLabel: "Delete hypothesis" })) delHyp.mutate(h.id); }} onAddEvidence={(body) => addEv.mutate({ hypothesis: h.id, ...body })} onDeleteEvidence={async (id) => { if (await confirmDialog({ title: "Remove this evidence row?", danger: true, confirmLabel: "Remove" })) delEv.mutate(id); }} busy={addEv.isPending} />)}
        </div>
      )}
      <div className="grid gap-4 lg:grid-cols-3">
        <ExperimentLog experiments={experiments} hypotheses={list} onAdd={(body) => addExp.mutate(body)} onSave={(id, body) => patchExp.mutate({ id, ...body })} onDelete={async (e) => { if (await confirmDialog({ title: `Delete “${e.title}”?`, body: "The log entry is removed.", danger: true, confirmLabel: "Delete entry" })) delExp.mutate(e.id); }} busy={addExp.isPending || patchExp.isPending} />
        <section className={`${panel} rise p-4`} style={{ ["--i" as string]: 3 }}>
          <p className={railH}>Datasets <span className="normal-case tracking-normal text-stone-400">{datasets.length}</span></p>
          <ul className="mb-3 space-y-1.5 text-sm">{datasets.map((d) => <li key={d.id} className="group"><p className="flex items-baseline gap-2"><span className="min-w-0 flex-1 truncate font-medium text-stone-800 dark:text-stone-100">{d.name}</span>{d.version && <span className="text-[11px] text-stone-400">v{d.version}</span>}<Kebab label={`Actions for ${d.name}`} className="-my-1 opacity-0 group-hover:opacity-100 focus:opacity-100" items={[
            { label: "Rename…", icon: <Pencil className="h-3.5 w-3.5" />, onSelect: async () => { const v = await promptDialog({ title: "Rename dataset", label: "Name", initial: d.name }); if (v && v.trim() && v.trim() !== d.name) patchDs.mutate({ id: d.id, name: v.trim() }); } },
            { label: "Change location…", onSelect: async () => { const v = await promptDialog({ title: "Dataset location", label: "Path or URL", initial: d.location }); if (v && v.trim() && v.trim() !== d.location) patchDs.mutate({ id: d.id, location: v.trim() }); } },
            { label: "Set version…", onSelect: async () => { const v = await promptDialog({ title: "Dataset version", label: "Version", initial: d.version, placeholder: "e.g. 2.1 or a git tag" }); if (v !== null && v.trim() !== d.version) patchDs.mutate({ id: d.id, version: v.trim() }); } },
            "-",
            { label: "Delete…", icon: <Trash2 className="h-3.5 w-3.5" />, danger: true, onSelect: async () => { if (await confirmDialog({ title: `Delete the dataset “${d.name}”?`, body: "Only the registry entry goes — the data itself is untouched.", danger: true, confirmLabel: "Delete" })) delDs.mutate(d.id); } },
          ]} /></p><p className="truncate font-mono text-[11px] text-stone-400" title={d.location}>{d.location}</p></li>)}</ul>
          <DatasetForm onAdd={(b) => addDs.mutate(b)} busy={addDs.isPending} />
        </section>
        <QuestionsPanel slug={slug!} />
        <ProtocolPanel slug={slug!} protocols={protocols} onChange={() => queryClient.invalidateQueries({ queryKey: ["protocols", slug] })} />
      </div>
    </div>
  );
}

function HypothesisCard({ h, i, slug, onStatus, onEdit, onDelete, onAddEvidence, onDeleteEvidence, busy }: { h: Hypothesis; i: number; slug: string; onStatus: (s: string) => void; onEdit: () => void; onDelete: () => void; onAddEvidence: (body: Record<string, unknown>) => void; onDeleteEvidence: (id: number) => void; busy: boolean }) {
  const [adding, setAdding] = useState(false);
  const total = h.supports + h.contradicts + h.mixed;
  return (
    <section className={`${panel} rise p-4`} style={{ ["--i" as string]: i + 1 }} data-testid="hypothesis-card">
      <div className="flex flex-wrap items-start gap-3">
        <p className="min-w-0 flex-1 text-base leading-snug text-stone-900 dark:text-stone-100">{h.statement}</p>
        <select value={h.status} onChange={(e) => onStatus(e.target.value)} className={`rounded-full border-0 px-2.5 py-1 text-xs font-medium ${statusCls[h.status] ?? statusCls.proposed}`} aria-label="Hypothesis status">{STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}</select>
        <Kebab label="Hypothesis actions" items={[{ label: "Edit statement…", icon: <Pencil className="h-3.5 w-3.5" />, onSelect: onEdit }, "-", { label: "Delete…", icon: <Trash2 className="h-3.5 w-3.5" />, danger: true, onSelect: onDelete }]} />
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-3 text-[11px]">
        <div className="flex h-1.5 w-40 overflow-hidden rounded-full bg-stone-100 dark:bg-stone-800" title={`${h.supports} supports · ${h.contradicts} contradicts · ${h.mixed} mixed`}>
          {total > 0 && <><span className="h-full bg-emerald-500" style={{ width: `${(100 * h.supports) / total}%` }} /><span className="h-full bg-amber-500" style={{ width: `${(100 * h.mixed) / total}%` }} /><span className="h-full bg-red-500" style={{ width: `${(100 * h.contradicts) / total}%` }} /></>}
        </div>
        <span className="tabular-nums text-stone-500 dark:text-stone-400"><span className="text-emerald-600 dark:text-emerald-300">+{h.supports}</span> · <span className="text-amber-600 dark:text-amber-300">~{h.mixed}</span> · <span className="text-red-600 dark:text-red-300">−{h.contradicts}</span></span>
        {h.suggested_status && h.suggested_status !== h.status && <button type="button" onClick={() => onStatus(h.suggested_status!)} className="rounded-full bg-indigo-500/10 px-2 py-0.5 text-indigo-700 hover:bg-indigo-500/20 dark:text-indigo-200" title="The evidence balance suggests this status — click to accept" data-testid="suggested-status">evidence says {h.suggested_status} →</button>}
        <button type="button" onClick={() => setAdding((v) => !v)} className="ml-auto inline-flex items-center gap-1 rounded-md border border-stone-300 px-2 py-0.5 text-stone-600 hover:border-indigo-300 dark:border-stone-700 dark:text-stone-300">{adding ? <X className="h-3 w-3" aria-hidden="true" /> : <Plus className="h-3 w-3" aria-hidden="true" />}{adding ? "close" : "Add evidence"}</button>
      </div>
      {adding && <EvidenceForm slug={slug} busy={busy} onSubmit={(body) => { onAddEvidence(body); setAdding(false); }} />}
      {h.evidence.length > 0 && (
        <ul className="mt-3 space-y-1.5">
          {h.evidence.map((e) => (
            <li key={e.id} className="group flex items-start gap-2 text-sm">
              <span className={`mt-0.5 shrink-0 rounded-full px-1.5 py-px text-[10px] ${DIR[e.direction]?.cls ?? ""}`}>{e.direction}</span>
              <span className="min-w-0 flex-1 leading-relaxed text-stone-700 dark:text-stone-200">{e.summary}
                {e.reference_detail && <Link to={`/references/${e.reference_detail.id}`} className="ml-1.5 font-mono text-[11px] text-indigo-600 hover:underline dark:text-indigo-300" title={e.reference_detail.title}>@{e.reference_detail.bibtex_key}</Link>}
                {e.note && <Link to={`/projects/${slug}/notes/${e.note}`} className="ml-1.5 text-[11px] text-indigo-600 hover:underline dark:text-indigo-300">[[{e.note_title}]]</Link>}
              </span>
              <button type="button" onClick={() => onDeleteEvidence(e.id)} className="text-stone-300 opacity-0 hover:text-red-500 group-hover:opacity-100" aria-label="Delete evidence"><X className="h-3.5 w-3.5" aria-hidden="true" /></button>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}

function EvidenceForm({ slug, busy, onSubmit }: { slug: string; busy: boolean; onSubmit: (body: Record<string, unknown>) => void }) {
  const [direction, setDirection] = useState<"supports" | "contradicts" | "mixed">("supports");
  const [summary, setSummary] = useState("");
  const [paperQ, setPaperQ] = useState("");
  const [paper, setPaper] = useState<Suggestion | null>(null);
  const [noteQ, setNoteQ] = useState("");
  const [note, setNote] = useState<Suggestion | null>(null);
  const dpq = useDebounced(paperQ, 150); const dnq = useDebounced(noteQ, 150);
  const papers = useQuery({ queryKey: ["note-suggest", slug, "reference", dpq], queryFn: () => api<Suggestion[]>(`/notes/suggest/?project=${slug}&kind=reference&q=${encodeURIComponent(dpq)}`), enabled: paperQ.length > 0 && !paper });
  const notes = useQuery({ queryKey: ["note-suggest", slug, "note", dnq], queryFn: () => api<Suggestion[]>(`/notes/suggest/?project=${slug}&kind=note&q=${encodeURIComponent(dnq)}`), enabled: noteQ.length > 0 && !note });
  return (
    <form onSubmit={(e) => { e.preventDefault(); if (!summary.trim()) return; onSubmit({ direction, summary: summary.trim(), reference: paper?.id ?? null, note: note?.id ?? null }); }} className="mt-3 rounded-xl border border-stone-200 bg-stone-50/60 p-3 text-xs dark:border-stone-800 dark:bg-stone-950/30" data-testid="evidence-form">
      <div className="mb-2 flex flex-wrap items-center gap-1.5">
        {(["supports", "contradicts", "mixed"] as const).map((d) => <button key={d} type="button" onClick={() => setDirection(d)} className={`rounded-full px-2.5 py-1 font-medium transition-colors ${direction === d ? DIR[d].cls + " ring-1 ring-current" : "bg-stone-100 text-stone-500 dark:bg-stone-800 dark:text-stone-400"}`}>{d === "supports" ? <Check className="mr-1 inline h-3 w-3" aria-hidden="true" /> : d === "contradicts" ? <Minus className="mr-1 inline h-3 w-3" aria-hidden="true" /> : null}{d}</button>)}
      </div>
      <input value={summary} onChange={(e) => setSummary(e.target.value)} placeholder="What does the evidence show? One line." className="mb-2 w-full rounded-md border border-stone-200 bg-white px-2 py-1.5 text-sm dark:border-stone-700 dark:bg-stone-800 dark:text-stone-100" aria-label="Evidence summary" autoFocus />
      <div className="grid gap-2 sm:grid-cols-2">
        <div className="relative">
          {paper ? <span className="inline-flex items-center gap-1 rounded-full bg-indigo-500/10 px-2 py-1 font-mono text-indigo-700 dark:text-indigo-200">@{paper.label}<button type="button" onClick={() => setPaper(null)} aria-label="Remove paper"><X className="h-3 w-3" aria-hidden="true" /></button></span> : <input value={paperQ} onChange={(e) => setPaperQ(e.target.value)} placeholder="From a paper — cite key or title…" className="w-full rounded-md border border-stone-200 bg-white px-2 py-1.5 dark:border-stone-700 dark:bg-stone-800 dark:text-stone-100" aria-label="Evidence paper" />}
          {paperQ && !paper && papers.data && <ul className="absolute left-0 right-0 top-full z-20 mt-1 max-h-40 overflow-auto rounded-lg border border-stone-200 bg-white shadow-lg dark:border-stone-700 dark:bg-stone-900">{papers.data.map((s) => <li key={s.id}><button type="button" onClick={() => { setPaper(s); setPaperQ(""); }} className="block w-full truncate px-2 py-1 text-left hover:bg-indigo-500/10"><span className="font-mono text-indigo-500">@{s.label}</span> <span className="text-stone-500">{s.sublabel}</span></button></li>)}{papers.data.length === 0 && <li className="px-2 py-1 text-stone-400">No paper in this project matches.</li>}</ul>}
        </div>
        <div className="relative">
          {note ? <span className="inline-flex items-center gap-1 rounded-full bg-indigo-500/10 px-2 py-1 text-indigo-700 dark:text-indigo-200">[[{note.label}]]<button type="button" onClick={() => setNote(null)} aria-label="Remove note"><X className="h-3 w-3" aria-hidden="true" /></button></span> : <input value={noteQ} onChange={(e) => setNoteQ(e.target.value)} placeholder="From a note — title…" className="w-full rounded-md border border-stone-200 bg-white px-2 py-1.5 dark:border-stone-700 dark:bg-stone-800 dark:text-stone-100" aria-label="Evidence note" />}
          {noteQ && !note && notes.data && <ul className="absolute left-0 right-0 top-full z-20 mt-1 max-h-40 overflow-auto rounded-lg border border-stone-200 bg-white shadow-lg dark:border-stone-700 dark:bg-stone-900">{notes.data.map((s) => <li key={s.id}><button type="button" onClick={() => { setNote(s); setNoteQ(""); }} className="block w-full truncate px-2 py-1 text-left hover:bg-indigo-500/10">{s.label}</button></li>)}</ul>}
        </div>
      </div>
      <button type="submit" disabled={busy || !summary.trim()} className="mt-2 rounded-md bg-indigo-600 px-2.5 py-1 font-medium text-white hover:bg-indigo-700 disabled:opacity-40">Attach evidence</button>
    </form>
  );
}

function ExperimentLog({ experiments, hypotheses, onAdd, onSave, onDelete, busy }: { experiments: Experiment[]; hypotheses: Hypothesis[]; onAdd: (body: Record<string, unknown>) => void; onSave: (id: number, body: Record<string, unknown>) => void; onDelete: (e: Experiment) => void; busy: boolean }) {
  const [shown, setShown] = useState<number | null>(null);
  const [open, setOpen] = useState(false);
  const [editing, setEditing] = useState<Experiment | null>(null);
  const [title, setTitle] = useState(""); const [body, setBody] = useState(""); const [picked, setPicked] = useState<number[]>([]);
  const startEdit = (e: Experiment) => { setEditing(e); setTitle(e.title); setBody(e.body); setPicked(e.hypotheses); setOpen(true); };
  const itemsFor = (e: Experiment): MenuItem[] => [
    { label: "Edit…", icon: <Pencil className="h-3.5 w-3.5" />, onSelect: () => startEdit(e) },
    "-",
    { label: "Delete…", icon: <Trash2 className="h-3.5 w-3.5" />, danger: true, onSelect: () => onDelete(e) },
  ];
  return (
    <section className={`${panel} rise p-4 lg:col-span-1`} style={{ ["--i" as string]: 2 }} data-testid="experiment-log">
      <div className="mb-2 flex items-baseline justify-between"><p className={`${railH} mb-0`}>Experiment log <span className="normal-case tracking-normal text-stone-400">{experiments.length}</span></p><button type="button" onClick={() => setOpen((v) => !v)} className="text-[11px] text-indigo-600 hover:underline dark:text-indigo-300">{open ? "close" : "+ log an experiment"}</button></div>
      {open && (
        <form onSubmit={(e) => { e.preventDefault(); if (!title.trim()) return; if (editing) onSave(editing.id, { title: title.trim(), body, hypotheses: picked }); else onAdd({ title: title.trim(), body, hypotheses: picked }); setTitle(""); setBody(""); setPicked([]); setEditing(null); setOpen(false); }} className="mb-3 space-y-2 rounded-xl border border-stone-200 bg-stone-50/60 p-3 text-xs dark:border-stone-800 dark:bg-stone-950/30">
          <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Title — e.g. Pilot session 3" className="w-full rounded-md border border-stone-200 bg-white px-2 py-1.5 text-sm dark:border-stone-700 dark:bg-stone-800 dark:text-stone-100" aria-label="Experiment title" autoFocus />
          <textarea value={body} onChange={(e) => setBody(e.target.value)} rows={3} placeholder="Setup, what happened, outcome (Markdown)" className="w-full rounded-md border border-stone-200 bg-white px-2 py-1.5 dark:border-stone-700 dark:bg-stone-800 dark:text-stone-100" aria-label="Experiment body" />
          {hypotheses.length > 0 && <div className="flex flex-wrap gap-1.5">{hypotheses.map((h) => <label key={h.id} className={`inline-flex cursor-pointer items-center gap-1 rounded-full px-2 py-0.5 ${picked.includes(h.id) ? "bg-indigo-500/15 text-indigo-700 dark:text-indigo-200" : "bg-stone-100 text-stone-500 dark:bg-stone-800 dark:text-stone-400"}`}><input type="checkbox" className="hidden" checked={picked.includes(h.id)} onChange={() => setPicked((p) => (p.includes(h.id) ? p.filter((x) => x !== h.id) : [...p, h.id]))} />{h.statement.slice(0, 40)}{h.statement.length > 40 ? "…" : ""}</label>)}</div>}
          <button type="submit" disabled={busy || !title.trim()} className="rounded-md bg-indigo-600 px-2.5 py-1 font-medium text-white hover:bg-indigo-700 disabled:opacity-40">{editing ? "Save changes" : "Log"}</button>
        </form>
      )}
      {experiments.length === 0 && !open && <p className="text-xs text-stone-400">Nothing logged yet — dated entries: setup, what happened, outcome.</p>}
      <ul className="divide-y divide-stone-100 dark:divide-stone-800">
        {experiments.map((e) => (
          <li key={e.id} className="group py-2 text-sm first:pt-0" data-testid="experiment">
            <div className="flex items-baseline gap-2"><span className="min-w-0 flex-1 truncate font-medium text-stone-800 dark:text-stone-100">{e.title}</span><span className="shrink-0 text-[11px] tabular-nums text-stone-400">{e.date}</span><Kebab items={itemsFor(e)} label={`Actions for ${e.title}`} className="-my-1 opacity-0 group-hover:opacity-100 focus:opacity-100" /></div>
            {e.body && (
              // #407: the entry renders as markdown with mentions; click the preview to read it all
              shown === e.id
                ? <Prose html={e.body_html} className="mt-1 text-xs" testId="experiment-body" />
                : <button type="button" onClick={() => setShown(e.id)} className="mt-0.5 block w-full text-left text-xs leading-relaxed text-stone-500 hover:text-stone-700 dark:text-stone-400 dark:hover:text-stone-200" title="Read the whole entry"><span className="line-clamp-2">{e.body.replace(/[*_`#>]+/g, "")}</span></button>
            )}
            <p className="mt-0.5 flex flex-wrap gap-1 text-[10px] text-stone-400">{e.commit_url && <a href={e.commit_url} target="_blank" rel="noopener" className="font-mono text-indigo-600 hover:underline dark:text-indigo-300">⎇ {e.commit_label}</a>}{e.hypotheses.map((id) => { const h = hypotheses.find((x) => x.id === id); return h ? <span key={id} className="rounded-full bg-stone-100 px-1.5 py-px dark:bg-stone-800" title={h.statement}>H{id}</span> : null; })}</p>
          </li>
        ))}
      </ul>
    </section>
  );
}

function DatasetForm({ onAdd, busy }: { onAdd: (body: Record<string, unknown>) => void; busy: boolean }) {
  const [name, setName] = useState(""); const [location, setLocation] = useState("");
  return (
    <form onSubmit={(e) => { e.preventDefault(); if (name.trim() && location.trim()) { onAdd({ name: name.trim(), location: location.trim() }); setName(""); setLocation(""); } }} className="flex flex-wrap gap-1.5 text-xs">
      <input value={name} onChange={(e) => setName(e.target.value)} placeholder="name" className="min-w-0 flex-1 rounded-md border border-stone-200 bg-white px-2 py-1 dark:border-stone-700 dark:bg-stone-800 dark:text-stone-100" aria-label="Dataset name" />
      <input value={location} onChange={(e) => setLocation(e.target.value)} placeholder="path or URL" className="min-w-0 flex-[2] rounded-md border border-stone-200 bg-white px-2 py-1 font-mono dark:border-stone-700 dark:bg-stone-800 dark:text-stone-100" aria-label="Dataset location" />
      <button type="submit" disabled={busy || !name.trim() || !location.trim()} className="rounded-md bg-indigo-600 px-2 py-1 font-medium text-white hover:bg-indigo-700 disabled:opacity-40">Register</button>
    </form>
  );
}


/* Protocols (moved in-app 2026-09-06): versioned method write-ups. A new version keeps the
   old one in the chain (is_current flips), so a paper can cite exactly the protocol it ran. */
function ProtocolPanel({ slug, protocols, onChange }: { slug: string; protocols: Protocol[]; onChange: () => void }) {
  const [open, setOpen] = useState<Protocol | null>(null);
  const [writing, setWriting] = useState(false);
  const [title, setTitle] = useState("");
  const [body, setBody] = useState("");
  const [busy, setBusy] = useState(false);
  const JSON_H = { "Content-Type": "application/json" };
  const create = async () => { setBusy(true); try { await api("/protocols/", { method: "POST", headers: JSON_H, body: JSON.stringify({ project: slug, title: title.trim(), body }) }); setTitle(""); setBody(""); setWriting(false); onChange(); } finally { setBusy(false); } };
  const revise = async () => { if (!open) return; setBusy(true); try { const next = await api<Protocol>(`/protocols/${open.id}/new-version/`, { method: "POST", headers: JSON_H, body: JSON.stringify({ title: title.trim() || open.title, body }) }); setOpen(next); setWriting(false); onChange(); } finally { setBusy(false); } };
  return (
    <section className={`${panel} rise p-4`} style={{ ["--i" as string]: 4 }} data-testid="protocols">
      <div className="mb-2 flex items-baseline justify-between"><p className={`${railH} mb-0`}>Protocols <span className="normal-case tracking-normal text-stone-400">{protocols.length}</span></p><button type="button" onClick={() => { setOpen(null); setTitle(""); setBody(""); setWriting((v) => !v); }} className="text-[11px] text-indigo-600 hover:underline dark:text-indigo-300">{writing && !open ? "close" : "+ write a protocol"}</button></div>
      {writing && !open && (
        <form onSubmit={(e) => { e.preventDefault(); void create(); }} className="mb-3 space-y-2 text-xs">
          <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Title — e.g. Dual-task procedure" className="w-full rounded-md border border-stone-200 bg-white px-2 py-1.5 text-sm dark:border-stone-700 dark:bg-stone-800 dark:text-stone-100" aria-label="Protocol title" autoFocus />
          <textarea value={body} onChange={(e) => setBody(e.target.value)} rows={5} placeholder="Steps, materials, timing (Markdown)" className="w-full rounded-md border border-stone-200 bg-white px-2 py-1.5 dark:border-stone-700 dark:bg-stone-800 dark:text-stone-100" aria-label="Protocol body" />
          <button type="submit" disabled={busy || !title.trim()} className="rounded-md bg-indigo-600 px-2.5 py-1 font-medium text-white hover:bg-indigo-700 disabled:opacity-40">Save v1</button>
        </form>
      )}
      {protocols.length === 0 && !writing ? <p className="text-xs text-stone-400">No protocols yet — write one; every revision is kept as a version.</p> : (
        <ul className="space-y-1 text-sm">{protocols.map((p) => <li key={p.id} className="flex items-baseline gap-2"><button type="button" onClick={() => { setOpen(open?.id === p.id ? null : p); setWriting(false); }} className="min-w-0 flex-1 truncate text-left text-stone-800 hover:text-indigo-600 dark:text-stone-100 dark:hover:text-indigo-300">{p.title}</button><span className="rounded bg-stone-100 px-1.5 py-0.5 font-mono text-[10px] text-stone-500 dark:bg-stone-800">v{p.version}</span></li>)}</ul>
      )}
      {open && (
        <div className="mt-3 rounded-lg border border-stone-200 p-3 text-sm dark:border-stone-700" data-testid="protocol-open">
          <div className="mb-1 flex items-center justify-between gap-2"><p className="font-medium">{open.title} <span className="font-mono text-[10px] text-stone-400">v{open.version}</span></p><span className="flex gap-2 text-[11px]"><button type="button" onClick={() => { setTitle(open.title); setBody(open.body); setWriting(true); }} className="text-indigo-600 hover:underline dark:text-indigo-300">new version</button><button type="button" onClick={() => setOpen(null)} className="text-stone-400 hover:underline">close</button></span></div>
          {writing ? (
            <form onSubmit={(e) => { e.preventDefault(); void revise(); }} className="space-y-2 text-xs">
              <input value={title} onChange={(e) => setTitle(e.target.value)} className="w-full rounded-md border border-stone-200 bg-white px-2 py-1.5 text-sm dark:border-stone-700 dark:bg-stone-800 dark:text-stone-100" aria-label="Protocol title" />
              <textarea value={body} onChange={(e) => setBody(e.target.value)} rows={8} className="w-full rounded-md border border-stone-200 bg-white px-2 py-1.5 dark:border-stone-700 dark:bg-stone-800 dark:text-stone-100" aria-label="Protocol body" autoFocus />
              <button type="submit" disabled={busy} className="rounded-md bg-indigo-600 px-2.5 py-1 font-medium text-white hover:bg-indigo-700 disabled:opacity-40">Save as v{open.version + 1}</button>
            </form>
          ) : open.body ? <Prose html={open.body_html} className="text-xs" testId="protocol-body" /> : <p className="text-xs text-stone-400">(empty)</p>}
        </div>
      )}
    </section>
  );
}


/* Research questions (CRUD sweep 2026-09-06): the overview and the plan showed them, but
   nothing in the app let you ask, answer, reword or drop one. Phases attach them in the plan. */
function QuestionsPanel({ slug }: { slug: string }) {
  const queryClient = useQueryClient();
  const q = useQuery({ queryKey: ["questions", slug], queryFn: () => api<Page<Question>>(`/questions/?project=${slug}&page_size=100`) });
  const refresh = () => { queryClient.invalidateQueries({ queryKey: ["questions", slug] }); queryClient.invalidateQueries({ queryKey: ["overview", slug] }); queryClient.invalidateQueries({ queryKey: ["plan", slug] }); };
  const fail = (title: string) => (e: unknown) => void errorDialog(title, e);
  const [text, setText] = useState("");
  const add = useMutation({ mutationFn: () => api("/questions/", { method: "POST", headers: JSON_H, body: JSON.stringify({ project: slug, question: text.trim() }) }), onSuccess: () => { setText(""); refresh(); }, onError: fail("Couldn't add the question") });
  const patch = useMutation({ mutationFn: ({ id, ...body }: { id: number } & Record<string, unknown>) => api(`/questions/${id}/`, { method: "PATCH", headers: JSON_H, body: JSON.stringify(body) }), onSuccess: refresh, onError: fail("Couldn't save the question") });
  const remove = useMutation({ mutationFn: (id: number) => api(`/questions/${id}/`, { method: "DELETE" }), onSuccess: refresh, onError: fail("Couldn't delete the question") });
  const rows = q.data?.results ?? [];
  return (
    <section className={`${panel} rise p-4 lg:col-span-3`} style={{ ["--i" as string]: 5 }} data-testid="questions-panel">
      <p className={railH}><HelpCircle className="mr-1 inline h-3 w-3" aria-hidden="true" />Research questions <span className="normal-case tracking-normal text-stone-400">{rows.length}</span></p>
      <form onSubmit={(e) => { e.preventDefault(); if (text.trim()) add.mutate(); }} className="mb-3 flex gap-2 text-sm">
        <input value={text} onChange={(e) => setText(e.target.value)} placeholder="Ask a question the project should answer…" className="min-w-0 flex-1 rounded-md border border-stone-200 bg-white px-2.5 py-1.5 dark:border-stone-700 dark:bg-stone-800 dark:text-stone-100" aria-label="New research question" />
        <button type="submit" disabled={!text.trim() || add.isPending} className="rounded-md bg-indigo-600 px-3 py-1.5 font-medium text-white hover:bg-indigo-700 disabled:opacity-40">Ask</button>
      </form>
      {rows.length === 0 ? <p className="text-xs text-stone-400">No questions yet — the plan's phases can be attached to them once they exist.</p> : (
        <ul className="space-y-1.5 text-sm">
          {rows.map((r) => (
            <li key={r.id} className="group flex items-start gap-2" data-testid="question-row">
              <select value={r.status} onChange={(e) => patch.mutate({ id: r.id, status: e.target.value })} className={`mt-0.5 shrink-0 rounded-full border-0 px-2 py-0.5 text-[11px] font-medium ${qCls[r.status] ?? qCls.open}`} aria-label="Question status">{Q_STATUSES.map((st) => <option key={st} value={st}>{st.replace("_", " ")}</option>)}</select>
              <span className="min-w-0 flex-1 leading-snug text-stone-700 dark:text-stone-200">{r.question}{r.phases.length > 0 && <span className="ml-1.5 text-[11px] text-stone-400">· {r.phases.length} phase{r.phases.length === 1 ? "" : "s"}</span>}</span>
              <Kebab label="Question actions" className="opacity-0 group-hover:opacity-100 focus:opacity-100" items={[
                { label: "Reword…", icon: <Pencil className="h-3.5 w-3.5" />, onSelect: async () => { const v = await promptDialog({ title: "Edit question", label: "Question", initial: r.question, multiline: true, validate: (x) => (x.trim() ? null : "Write the question.") }); if (v && v.trim() !== r.question) patch.mutate({ id: r.id, question: v.trim() }); } },
                "-",
                { label: "Delete…", icon: <Trash2 className="h-3.5 w-3.5" />, danger: true, onSelect: async () => { if (await confirmDialog({ title: "Delete this question?", body: r.question, danger: true, confirmLabel: "Delete question" })) remove.mutate(r.id); } },
              ]} />
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
