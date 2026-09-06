/** Literature review matrix v2 (Observatory) — an extraction table: papers × themes. Click a
 *  cell to mark it, type the extracted finding into it, add or rename themes in place, filter
 *  papers, copy the table as Markdown, and draft a synthesis note. Claude fills the same cells
 *  through set_review_mark / add_review_theme. API: /projects/{slug}/review-matrix/… */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate, useParams } from "react-router-dom";
import { Check, Copy, FileText, Plus, Search, Sparkles, X } from "lucide-react";
import { api, csrfToken, petReact } from "../api";
import { Skeleton } from "../../components/Skeleton";
import { ErrorState } from "../../components/ErrorState";

type Theme = { id: number; name: string; order: number; covered: number; total: number };
type Row = { link_id: number; reference_id: number; bibtex_key: string; title: string; year: number | null; authors: string; reading_status: string; has_pdf: boolean; cells: Record<string, { mark_id: number; note: string }>; covered: number };
type Table = { project: string; themes: Theme[]; rows: Row[]; papers: number; unmarked: number };
type Payload = { themes: string[]; papers: unknown[]; coverage: unknown; table: Table };

const panel = "rounded-2xl border border-stone-200 bg-white dark:border-stone-800 dark:bg-stone-900";
const JSON_H = { "Content-Type": "application/json" };
const STATUS_DOT: Record<string, string> = { to_read: "#f59e0b", skimmed: "#a5b4fc", read: "#7c6cff", annotated: "#34d399" };

export default function Matrix() {
  const { slug } = useParams();
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const { data, isLoading, error, refetch } = useQuery({ queryKey: ["matrix", slug], queryFn: () => api<Payload>(`/projects/${slug}/review-matrix/`).then((p) => p.table) });
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["matrix", slug] });
  const [q, setQ] = useState("");
  const [onlyUnmarked, setOnlyUnmarked] = useState(false);
  const [newTheme, setNewTheme] = useState("");
  const [editing, setEditing] = useState<{ ref: number; theme: number } | null>(null);
  const [draft, setDraft] = useState("");
  const [toast, setToast] = useState("");
  const flash = (m: string) => { setToast(m); setTimeout(() => setToast(""), 3500); };

  const setMark = useMutation({
    mutationFn: (v: { reference: number; theme: number; marked: boolean; note?: string }) => api(`/projects/${slug}/review-matrix/mark/`, { method: "POST", headers: JSON_H, body: JSON.stringify({ reference: String(v.reference), theme: String(v.theme), marked: v.marked, note: v.note ?? null }) }),
    onMutate: (v) => {
      queryClient.setQueryData<Table>(["matrix", slug], (old) => {
        if (!old) return old;
        const rows = old.rows.map((r) => {
          if (r.reference_id !== v.reference) return r;
          const cells = { ...r.cells };
          if (v.marked) cells[String(v.theme)] = { mark_id: cells[String(v.theme)]?.mark_id ?? 0, note: v.note ?? cells[String(v.theme)]?.note ?? "" };
          else delete cells[String(v.theme)];
          return { ...r, cells, covered: Object.keys(cells).length };
        });
        const themes = old.themes.map((t) => ({ ...t, covered: rows.filter((r) => String(t.id) in r.cells).length }));
        return { ...old, rows, themes, unmarked: rows.filter((r) => r.covered === 0).length };
      });
    },
    onSettled: refresh,
  });
  const addTheme = useMutation({ mutationFn: (name: string) => api(`/projects/${slug}/review-matrix/themes/`, { method: "POST", headers: JSON_H, body: JSON.stringify({ name }) }), onSuccess: () => { setNewTheme(""); refresh(); } });
  const renameTheme = useMutation({ mutationFn: ({ id, name }: { id: number; name: string }) => api(`/projects/${slug}/review-matrix/themes/${id}/`, { method: "PATCH", headers: JSON_H, body: JSON.stringify({ name }) }), onSuccess: refresh });
  const deleteTheme = useMutation({ mutationFn: (id: number) => api(`/projects/${slug}/review-matrix/themes/${id}/`, { method: "DELETE" }), onSuccess: refresh });
  const synth = useMutation({
    mutationFn: async () => { const res = await fetch(`/projects/${slug}/literature/synthesis/`, { method: "POST", headers: { "X-CSRFToken": csrfToken(), "X-SPA": "1" }, credentials: "same-origin" }); if (!res.ok) throw new Error(String(res.status)); return (await res.json()) as { note_id: number }; },
    onSuccess: (out) => { petReact("note"); navigate(`/projects/${slug}/notes/${out.note_id}`); },
    onError: () => flash("Could not draft the synthesis note."),
  });

  const rows = useMemo(() => {
    const needle = q.trim().toLowerCase();
    return (data?.rows ?? []).filter((r) => (!needle || r.title.toLowerCase().includes(needle) || r.bibtex_key.toLowerCase().includes(needle) || r.authors.toLowerCase().includes(needle)) && (!onlyUnmarked || r.covered === 0));
  }, [data, q, onlyUnmarked]);
  useEffect(() => { if (editing) { const row = data?.rows.find((r) => r.reference_id === editing.ref); setDraft(row?.cells[String(editing.theme)]?.note ?? ""); } }, [editing]); // eslint-disable-line react-hooks/exhaustive-deps

  const copyMarkdown = async () => {
    if (!data) return;
    const head = `| Paper | ${data.themes.map((t) => t.name).join(" | ")} |\n|${"---|".repeat(data.themes.length + 1)}`;
    const body = rows.map((r) => `| ${r.bibtex_key} | ${data.themes.map((t) => { const c = r.cells[String(t.id)]; return c ? (c.note || "✓") : ""; }).join(" | ")} |`).join("\n");
    await navigator.clipboard?.writeText(`${head}\n${body}\n`);
    flash("Copied the matrix as Markdown.");
  };

  if (isLoading) return <div className="space-y-3"><Skeleton className="h-8 w-56" /><Skeleton className="h-64 w-full" /></div>;
  if (error || !data) return <ErrorState message="Couldn't load the review matrix." onRetry={() => refetch()} />;
  const filled = data.rows.reduce((n, r) => n + r.covered, 0);
  return (
    <div>
      <nav className="mb-4 text-sm text-stone-500 dark:text-stone-400"><Link to="/projects" className="hover:underline">Projects</Link> / <Link to={`/projects/${slug}`} className="hover:underline">{slug}</Link> / Review matrix</nav>
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <h1 className="font-display text-3xl font-bold tracking-tight dark:text-stone-100">Review matrix <span className="text-gradient">· {data.papers} papers × {data.themes.length} themes</span></h1>
        <p className="text-sm text-stone-400">{filled} cells filled{data.unmarked ? ` · ${data.unmarked} paper${data.unmarked === 1 ? "" : "s"} untouched` : ""}</p>
        <span className="ml-auto flex items-center gap-2 text-xs">
          <button type="button" onClick={() => void copyMarkdown()} className="inline-flex items-center gap-1 rounded-lg border border-stone-300 px-2.5 py-1.5 text-stone-600 hover:border-indigo-300 dark:border-stone-700 dark:text-stone-300"><Copy className="h-3.5 w-3.5" aria-hidden="true" />Copy as Markdown</button>
          <button type="button" onClick={() => { const esc = (v: string | number) => `"${String(v).replace(/"/g, '""')}"`; const head = ["key", "title", "year", ...data.themes.map((t) => t.name)].map(esc).join(","); const body = data.rows.map((r) => [r.bibtex_key, r.title, r.year ?? "", ...data.themes.map((t) => { const c = r.cells[String(t.id)]; return c ? (c.note || "x") : ""; })].map(esc).join(",")).join("\n"); const blob = new Blob([`${head}\n${body}\n`], { type: "text/csv" }); const a = document.createElement("a"); a.href = URL.createObjectURL(blob); a.download = `${slug}-review-matrix.csv`; a.click(); URL.revokeObjectURL(a.href); flash("CSV downloaded — opens in Excel or R."); }} className="inline-flex items-center gap-1 rounded-lg border border-stone-300 px-2.5 py-1.5 text-stone-600 hover:border-indigo-300 dark:border-stone-700 dark:text-stone-300" title="Papers × themes as a spreadsheet"><FileText className="h-3.5 w-3.5" aria-hidden="true" />CSV</button>
          <a href={`/api/v1/projects/${slug}/review-matrix/markdown/`} className="inline-flex items-center gap-1 rounded-lg border border-stone-300 px-2.5 py-1.5 text-stone-600 hover:border-indigo-300 dark:border-stone-700 dark:text-stone-300"><FileText className="h-3.5 w-3.5" aria-hidden="true" />.md</a>
          <button type="button" onClick={() => synth.mutate()} disabled={synth.isPending || data.themes.length === 0} className="inline-flex items-center gap-1 rounded-lg bg-indigo-600 px-2.5 py-1.5 font-medium text-white hover:bg-indigo-700 disabled:opacity-40" title="Create a synthesis note organised by theme from the marked papers"><Sparkles className="h-3.5 w-3.5" aria-hidden="true" />Draft synthesis note</button>
        </span>
      </div>
      <div className={`${panel} rise mb-3 flex flex-wrap items-center gap-3 px-3 py-2 text-xs`} style={{ ["--i" as string]: 0 }}>
        <label className="relative"><Search className="pointer-events-none absolute left-2 top-1/2 h-3.5 w-3.5 -translate-y-1/2 text-stone-400" aria-hidden="true" /><input type="search" value={q} onChange={(e) => setQ(e.target.value)} placeholder="Filter papers…" className="w-56 rounded-lg border border-stone-200 bg-white py-1.5 pl-7 pr-2 placeholder:text-stone-400 focus:border-indigo-400 focus:outline-none dark:border-stone-700 dark:bg-stone-800" aria-label="Filter papers" /></label>
        <label className="flex items-center gap-1.5 text-stone-500"><input type="checkbox" checked={onlyUnmarked} onChange={(e) => setOnlyUnmarked(e.target.checked)} className="accent-indigo-500" />only untouched papers</label>
        <form onSubmit={(e) => { e.preventDefault(); if (newTheme.trim()) addTheme.mutate(newTheme.trim()); }} className="ml-auto flex items-center gap-1.5">
          <input value={newTheme} onChange={(e) => setNewTheme(e.target.value)} placeholder="New theme — e.g. Sample size" className="w-52 rounded-lg border border-stone-200 bg-white px-2 py-1.5 placeholder:text-stone-400 focus:border-indigo-400 focus:outline-none dark:border-stone-700 dark:bg-stone-800" aria-label="New theme" />
          <button type="submit" disabled={!newTheme.trim() || addTheme.isPending} className="inline-flex items-center gap-1 rounded-lg bg-indigo-600 px-2.5 py-1.5 font-medium text-white hover:bg-indigo-700 disabled:opacity-40"><Plus className="h-3.5 w-3.5" aria-hidden="true" />Theme</button>
        </form>
        <span className="text-stone-400">click a cell to mark · click again to write the finding · Esc closes</span>
      </div>
      {data.themes.length === 0 && (
        <div className={`${panel} rise mb-3 p-6 text-center`} style={{ ["--i" as string]: 1 }}>
          <p className="font-medium text-stone-700 dark:text-stone-100">Start with the themes you are extracting.</p>
          <p className="mx-auto mt-1 max-w-lg text-sm text-stone-400">Columns like <em>Sample size</em>, <em>Load manipulation</em>, <em>Main finding</em>, <em>Limitation</em>. Then click a cell per paper and type what that paper says — or ask Claude to fill the matrix from the PDFs (<span className="font-mono">set_review_mark</span>).</p>
        </div>
      )}
      <div className={`${panel} rise overflow-auto`} style={{ ["--i" as string]: 2 }} data-testid="matrix">
        <table className="w-full min-w-[40rem] border-separate border-spacing-0 text-sm">
          <thead>
            <tr>
              <th className="sticky left-0 top-0 z-20 border-b border-r border-stone-200 bg-white px-3 py-2 text-left text-[10px] font-semibold uppercase tracking-[0.14em] text-stone-400 dark:border-stone-800 dark:bg-stone-900">Paper</th>
              {data.themes.map((t) => <ThemeHead key={t.id} t={t} onRename={(name) => renameTheme.mutate({ id: t.id, name })} onDelete={() => { if (window.confirm(`Delete the theme “${t.name}” and its ${t.covered} mark${t.covered === 1 ? "" : "s"}?`)) deleteTheme.mutate(t.id); }} />)}
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.link_id} className="group" data-testid="matrix-row">
                <th scope="row" className="sticky left-0 z-10 max-w-[18rem] border-b border-r border-stone-100 bg-white px-3 py-1.5 text-left font-normal dark:border-stone-800 dark:bg-stone-900">
                  <Link to={`/references/${r.reference_id}`} className="block truncate text-stone-800 hover:text-indigo-700 dark:text-stone-100 dark:hover:text-indigo-300" title={r.title}>{r.title}</Link>
                  <p className="flex items-center gap-1.5 text-[11px] text-stone-400"><span className="inline-block h-1.5 w-1.5 rounded-full" style={{ background: STATUS_DOT[r.reading_status] ?? "#a8a29e" }} aria-hidden="true" /><span className="font-mono">{r.bibtex_key}</span>{r.authors && <span>· {r.authors}{r.year ? ` ${r.year}` : ""}</span>}</p>
                </th>
                {data.themes.map((t) => {
                  const cell = r.cells[String(t.id)];
                  const isEditing = editing?.ref === r.reference_id && editing.theme === t.id;
                  return (
                    <td key={t.id} className={`relative border-b border-stone-100 p-0 align-top dark:border-stone-800 ${cell ? "bg-indigo-500/5" : ""}`} data-testid="matrix-cell" data-marked={cell ? "1" : "0"}>
                      {isEditing ? (
                        <textarea autoFocus value={draft} onChange={(e) => setDraft(e.target.value)} onBlur={() => { setMark.mutate({ reference: r.reference_id, theme: t.id, marked: true, note: draft }); setEditing(null); }} onKeyDown={(e) => { if (e.key === "Escape") { setEditing(null); } if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); (e.target as HTMLTextAreaElement).blur(); } }} rows={3} maxLength={300} placeholder="What does this paper say about it?" className="block w-full min-w-[12rem] resize-none bg-indigo-50 px-2 py-1.5 text-xs leading-relaxed focus:outline-none dark:bg-indigo-500/15 dark:text-stone-100" aria-label={`${r.bibtex_key} · ${t.name}`} />
                      ) : (
                        <button type="button" onClick={() => { if (!cell) setMark.mutate({ reference: r.reference_id, theme: t.id, marked: true }); else setEditing({ ref: r.reference_id, theme: t.id }); }} onContextMenu={(e) => { if (cell) { e.preventDefault(); setMark.mutate({ reference: r.reference_id, theme: t.id, marked: false }); } }} className={`block h-full min-h-[2.75rem] w-full px-2 py-1.5 text-left text-xs leading-relaxed transition-colors hover:bg-indigo-500/10 ${cell ? "text-stone-700 dark:text-stone-200" : "text-transparent"}`} title={cell ? "Click to edit the finding · right-click to clear" : "Click to mark"} aria-label={`${r.bibtex_key} · ${t.name}${cell ? ": marked" : ""}`}>
                          {cell ? (cell.note ? cell.note : <Check className="h-4 w-4 text-indigo-500" aria-hidden="true" />) : "·"}
                        </button>
                      )}
                    </td>
                  );
                })}
              </tr>
            ))}
            {rows.length === 0 && <tr><td colSpan={data.themes.length + 1} className="px-3 py-6 text-center text-xs text-stone-400">{data.rows.length === 0 ? "No papers filed in this project yet." : "No paper matches the filter."}</td></tr>}
          </tbody>
        </table>
      </div>
      {toast && <div role="status" className="fixed bottom-5 right-5 z-30 rounded-xl border border-stone-200 bg-white px-4 py-2.5 text-sm shadow-lg dark:border-stone-700 dark:bg-stone-900 dark:text-stone-100">{toast}</div>}
    </div>
  );
}

function ThemeHead({ t, onRename, onDelete }: { t: Theme; onRename: (name: string) => void; onDelete: () => void }) {
  const [editing, setEditing] = useState(false);
  const [name, setName] = useState(t.name);
  useEffect(() => setName(t.name), [t.name]);
  const pct = t.total ? Math.round((100 * t.covered) / t.total) : 0;
  return (
    <th className="group/th sticky top-0 z-10 min-w-[10rem] border-b border-stone-200 bg-white px-2 py-2 text-left align-bottom dark:border-stone-800 dark:bg-stone-900" data-testid="theme-head">
      {editing ? (
        <form onSubmit={(e) => { e.preventDefault(); if (name.trim() && name.trim() !== t.name) onRename(name.trim()); setEditing(false); }}><input autoFocus value={name} onChange={(e) => setName(e.target.value)} onBlur={() => { if (name.trim() && name.trim() !== t.name) onRename(name.trim()); setEditing(false); }} onKeyDown={(e) => { if (e.key === "Escape") { setName(t.name); setEditing(false); } }} className="w-full rounded-md border border-indigo-300 bg-white px-1.5 py-0.5 text-xs font-medium dark:bg-stone-800 dark:text-stone-100" aria-label="Theme name" /></form>
      ) : (
        <div className="flex items-start gap-1">
          <button type="button" onClick={() => setEditing(true)} className="min-w-0 flex-1 truncate text-left text-xs font-semibold text-stone-700 hover:text-indigo-700 dark:text-stone-100 dark:hover:text-indigo-300" title="Rename">{t.name}</button>
          <button type="button" onClick={onDelete} className="text-stone-300 opacity-0 hover:text-red-500 group-hover/th:opacity-100" aria-label={`Delete theme ${t.name}`}><X className="h-3 w-3" aria-hidden="true" /></button>
        </div>
      )}
      <div className="mt-1 h-1 w-full overflow-hidden rounded-full bg-stone-100 dark:bg-stone-800"><div className="h-1 rounded-full bg-indigo-500" style={{ width: `${pct}%` }} /></div>
      <p className="mt-0.5 text-[10px] font-normal tabular-nums text-stone-400">{t.covered}/{t.total}</p>
    </th>
  );
}
