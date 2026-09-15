/** Import a folder of existing projects (#535, owner ask): pick the folder that holds one
 * subfolder per project, preview what each would become, tick the ones to bring in, and
 * watch them land one after the other — README → description, Markdown → notes, PDFs →
 * the library, everything else → files. Re-running adds only what is missing. */
import { useState } from "react";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { CheckCircle2, FolderInput, FolderOpen, Loader2, Search } from "lucide-react";
import { api } from "../api";
import { isDesktop, pickFolder } from "../external";

type Skip = { path: string; reason: string };
type Row = {
  folder: string; name: string; slug: string; exists: boolean; has_readme: boolean; bytes: number;
  pdfs: number; notes: number; bibs: number; files: number; skipped: Skip[];
  created?: boolean; documents?: number; references?: number; needs_metadata?: number; errors?: Skip[];
};
type Answer = { root: string; dry_run: boolean; projects: Row[] };
type State = { status: "waiting" | "importing" | "done" | "failed"; result?: Row; error?: string };

const inputClass = "w-full rounded border border-stone-300 bg-white px-3 py-2 text-sm text-stone-800 placeholder:text-stone-400 focus:border-indigo-600 focus:outline-none focus:ring-1 focus:ring-indigo-600 dark:border-stone-700 dark:bg-stone-800 dark:text-stone-100";
const labelClass = "mb-1.5 block text-xs font-medium uppercase tracking-wide text-stone-400";
const panel = "rounded-2xl border border-stone-200 bg-white/70 backdrop-blur dark:border-stone-800 dark:bg-stone-900/60";
const mb = (n: number) => (n >= 1024 * 1024 ? `${(n / 1024 / 1024).toFixed(1)} MB` : `${Math.max(1, Math.round(n / 1024))} KB`);
const plural = (n: number, w: string) => `${n} ${w}${n === 1 ? "" : "s"}`;

export default function ImportProjects() {
  const qc = useQueryClient();
  const [path, setPath] = useState("");
  const [pdfs, setPdfs] = useState<"library" | "documents">("library");
  const [markdown, setMarkdown] = useState<"notes" | "documents">("notes");
  const [preview, setPreview] = useState<Answer | null>(null);
  const [picked, setPicked] = useState<Set<string>>(new Set());
  const [states, setStates] = useState<Record<string, State>>({});
  const [running, setRunning] = useState(false);

  const body = (extra: object) => ({ method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ path, pdfs, markdown, ...extra }) });
  const look = useMutation({
    mutationFn: () => api<Answer>("/projects/import-folder/", body({ dry_run: true })),
    onSuccess: (a) => { setPreview(a); setPicked(new Set(a.projects.map((p) => p.folder))); setStates({}); },
  });

  const choose = async () => { const dir = await pickFolder(); if (dir) { setPath(dir); } };
  const toggle = (f: string) => setPicked((s) => { const n = new Set(s); if (n.has(f)) n.delete(f); else n.add(f); return n; });

  const run = async () => {
    if (!preview) return;
    setRunning(true);
    const queue = preview.projects.filter((p) => picked.has(p.folder)).map((p) => p.folder);
    setStates(Object.fromEntries(queue.map((f) => [f, { status: "waiting" as const }])));
    for (const folder of queue) {
      setStates((s) => ({ ...s, [folder]: { status: "importing" } }));
      try {
        const a = await api<Answer>("/projects/import-folder/", body({ dry_run: false, only: [folder] }));
        setStates((s) => ({ ...s, [folder]: { status: "done", result: a.projects[0] } }));
      } catch (e) {
        setStates((s) => ({ ...s, [folder]: { status: "failed", error: String((e as Error).message ?? e) } }));
      }
    }
    setRunning(false);
    void qc.invalidateQueries({ queryKey: ["projects"] });
  };

  const done = Object.values(states).filter((s) => s.status === "done").length;
  const finished = preview && !running && Object.keys(states).length > 0 && Object.values(states).every((s) => s.status === "done" || s.status === "failed");

  return (
    <div className="mx-auto max-w-3xl" data-testid="import-projects">
      <nav className="mb-6 text-sm text-stone-500 dark:text-stone-400">
        <Link to="/projects" className="hover:text-indigo-700 hover:underline dark:hover:text-indigo-300">Projects</Link>{" "}
        / <span className="text-stone-700 dark:text-stone-300">Import a folder</span>
      </nav>
      <h1 className="text-2xl font-semibold tracking-tight text-stone-900 dark:text-stone-100">Import a folder of projects</h1>
      <p className="mb-8 max-w-2xl text-sm text-stone-500 dark:text-stone-400">
        Point Atlas at the folder that holds your projects — one subfolder each. Every subfolder becomes a project: its README the description, Markdown files notes, PDFs papers in the library, everything else files in the same folder structure. Nothing is moved on disk, and running it again only adds what is missing.
      </p>

      <form className="space-y-6" onSubmit={(e) => { e.preventDefault(); if (path.trim()) look.mutate(); }}>
        <div>
          <label htmlFor="ip-path" className={labelClass}>Projects folder</label>
          <div className="flex gap-2">
            <input id="ip-path" value={path} onChange={(e) => setPath(e.target.value)} autoFocus placeholder={isDesktop() ? "Choose the folder that contains your projects…" : "/home/you/Projects"} className={inputClass} />
            {isDesktop() && <button type="button" onClick={() => void choose()} className="inline-flex shrink-0 items-center gap-1.5 rounded-lg border border-stone-300 px-3 py-1.5 text-sm text-stone-700 hover:border-stone-400 dark:border-stone-700 dark:text-stone-200"><FolderOpen className="h-4 w-4" aria-hidden="true" />Choose…</button>}
          </div>
          {!isDesktop() && <p className="mt-1 text-xs text-stone-400">A path on the machine that runs Atlas.</p>}
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <div>
            <label htmlFor="ip-pdfs" className={labelClass}>PDFs become</label>
            <select id="ip-pdfs" value={pdfs} onChange={(e) => setPdfs(e.target.value as typeof pdfs)} className={inputClass}>
              <option value="library">papers in the library (DOI read, metadata fetched)</option>
              <option value="documents">files in the project</option>
            </select>
          </div>
          <div>
            <label htmlFor="ip-md" className={labelClass}>Markdown becomes</label>
            <select id="ip-md" value={markdown} onChange={(e) => setMarkdown(e.target.value as typeof markdown)} className={inputClass}>
              <option value="notes">notes ([[links]] and #tags kept)</option>
              <option value="documents">files in the project</option>
            </select>
          </div>
        </div>
        <div className="flex items-center gap-3">
          <button type="submit" disabled={!path.trim() || look.isPending || running} className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50" data-testid="import-preview">
            {look.isPending ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : <Search className="h-4 w-4" aria-hidden="true" />}Preview
          </button>
          {look.error && <p className="text-sm text-rose-600 dark:text-rose-300">{String((look.error as Error).message ?? look.error)}</p>}
        </div>
      </form>

      {preview && (
        <section className={`${panel} mt-8 p-5`} data-testid="import-preview-table">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm text-stone-500">{preview.projects.length === 0 ? "No project folders here." : <>{plural(preview.projects.length, "folder")} in <code className="rounded bg-stone-100 px-1 text-xs dark:bg-stone-800">{preview.root}</code> · {picked.size} selected</>}</p>
            {preview.projects.length > 0 && !finished && (
              <button type="button" onClick={() => void run()} disabled={running || picked.size === 0} className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50" data-testid="import-run">
                {running ? <Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" /> : <FolderInput className="h-4 w-4" aria-hidden="true" />}{running ? `Importing… ${done}/${picked.size}` : `Import ${plural(picked.size, "project")}`}
              </button>
            )}
            {finished && <p className="inline-flex items-center gap-1.5 text-sm text-emerald-600 dark:text-emerald-300"><CheckCircle2 className="h-4 w-4" aria-hidden="true" />{plural(done, "project")} imported · <Link to="/projects" className="underline">open Projects</Link></p>}
          </div>
          {preview.projects.length === 0 ? (
            <p className="text-sm text-stone-500">Atlas looks one level down: every subfolder is a project. Pick the folder that contains them, not a project itself.</p>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead className="text-left text-[11px] font-semibold uppercase tracking-wider text-stone-400">
                  <tr><th className="w-8 py-1"></th><th className="py-1 pr-3">Folder</th><th className="py-1 pr-3">Becomes</th><th className="py-1 pr-3">Contents</th><th className="py-1">Result</th></tr>
                </thead>
                <tbody className="divide-y divide-stone-100 dark:divide-stone-800">
                  {preview.projects.map((p) => {
                    const st = states[p.folder];
                    const r = st?.result;
                    return (
                      <tr key={p.folder} data-testid="import-row" className="align-top">
                        <td className="py-2"><input type="checkbox" checked={picked.has(p.folder)} onChange={() => toggle(p.folder)} disabled={running || !!st} aria-label={`Import ${p.folder}`} /></td>
                        <td className="py-2 pr-3 font-medium text-stone-800 dark:text-stone-100">{p.folder}</td>
                        <td className="py-2 pr-3 text-stone-600 dark:text-stone-300">{p.name}{p.exists && <span className="ml-1.5 rounded-full bg-amber-500/10 px-1.5 py-0.5 text-[10px] font-semibold uppercase tracking-wide text-amber-700 dark:text-amber-300">already in Atlas · adds what is missing</span>}{!p.has_readme && !p.exists && <span className="ml-1.5 text-xs text-stone-400">no README</span>}</td>
                        <td className="py-2 pr-3 text-stone-500">
                          {[p.pdfs && `${p.pdfs} PDF${p.pdfs === 1 ? "" : "s"}`, p.notes && plural(p.notes, "note"), p.bibs && `${p.bibs} .bib`, p.files && plural(p.files, "file")].filter(Boolean).join(" · ") || "empty"}
                          {p.bytes > 0 && <span className="text-stone-400"> · {mb(p.bytes)}</span>}
                          {p.skipped.length > 0 && <details className="mt-0.5 text-xs text-stone-400"><summary className="cursor-pointer">{plural(p.skipped.length, "file")} skipped</summary><ul className="mt-1 space-y-0.5">{p.skipped.slice(0, 20).map((s) => <li key={s.path}><code>{s.path}</code> — {s.reason}</li>)}</ul></details>}
                        </td>
                        <td className="py-2 text-stone-500">
                          {!st && (picked.has(p.folder) ? "" : <span className="text-stone-400">skip</span>)}
                          {st?.status === "waiting" && <span className="text-stone-400">waiting…</span>}
                          {st?.status === "importing" && <span className="inline-flex items-center gap-1 text-indigo-600 dark:text-indigo-300"><Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden="true" />importing…</span>}
                          {st?.status === "failed" && <span className="text-rose-600 dark:text-rose-300">{st.error}</span>}
                          {st?.status === "done" && r && (
                            <span>
                              <Link to={`/projects/${r.slug}`} className="font-medium text-indigo-600 hover:underline dark:text-indigo-300">{r.created ? "created" : "updated"}</Link>
                              {" · "}{[plural(r.documents ?? 0, "file"), plural(r.notes ?? 0, "note"), plural(r.references ?? 0, "paper")].join(", ")}
                              {(r.needs_metadata ?? 0) > 0 && <span className="text-amber-600 dark:text-amber-300"> · {r.needs_metadata} without metadata</span>}
                              {(r.errors?.length ?? 0) > 0 && <details className="text-xs text-rose-600 dark:text-rose-300"><summary className="cursor-pointer">{plural(r.errors!.length, "error")}</summary><ul>{r.errors!.map((e) => <li key={e.path}><code>{e.path}</code> — {e.reason}</li>)}</ul></details>}
                            </span>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </section>
      )}
      <p className="mt-6 text-xs text-stone-400">Also: <code className="rounded bg-stone-100 px-1 dark:bg-stone-800">manage.py import_projects &lt;folder&gt; --apply</code>, the <code className="rounded bg-stone-100 px-1 dark:bg-stone-800">import_projects_folder</code> MCP tool, and the <code className="rounded bg-stone-100 px-1 dark:bg-stone-800">/atlas-import-projects</code> skill for Claude Code.</p>
    </div>
  );
}
