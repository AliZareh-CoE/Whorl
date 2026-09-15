/* Diagnostics (2026-09-06): the page to open when something on the desktop "didn't work".
 * Version, paths, the LaTeX engine, the update feed (probed on request), the last compile
 * failure and the server log tail — and one button that copies it all as text. */
import { useEffect, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { AlertTriangle, Camera, Check, CheckCircle2, Copy, Download, FolderOpen, Globe, Loader2, RotateCcw, Stethoscope, Upload, XCircle } from "lucide-react";
import { api } from "../api";
import { confirmDialog, errorDialog } from "../../components/Dialog";
import { isDesktop, openDevtools, revealPath } from "../external";
import { ErrorState } from "../../components/ErrorState";

type Feed = { url: string; status: number | string | null; version: string | null; platforms: string[]; key_match: boolean | null };
type Verdict = { state: "unchecked" | "offline" | "unreachable" | "unsigned" | "wrong_key" | "current" | "available" | "unknown_version"; text: string };
type RestoreState = { pending: { created_at?: string; staged_at: string | null; media_files: number; has_sqlite: boolean; has_json: boolean; size_bytes: number } | null; last_result: { ok: boolean; detail: string; applied_at: string; kept_previous_in: string } | null; data_dir: string };
type Latex = { state: "idle" | "running" | "ok" | "failed" | "unknown"; log: string; seconds: number | null; dir: string; warm: boolean; size_mb: number };
type Report = {
  version: string; desktop: boolean; platform: string; frozen: boolean; settings_module: string; data_dir: string | null; database: string;
  engine: string | null; latex: Latex; jobs: string; api_key_configured: boolean; update_feed: Feed[]; update_verdict?: Verdict;
  last_failed_compile: { manuscript: number; title: string; log: string; at: string } | null; server_log: string; text: string;
  backups?: { last: { at: string; days_ago: number; size_bytes: number } | null; stale: boolean; has_data: boolean; stale_after_days: number };
  // #462: the zips Atlas keeps on its own in <data dir>/backups
  snapshots?: { dir: string; keep: number; every_hours: number; count: number; total_bytes: number; last: { name: string; path: string; size_bytes: number; at: string; hours_ago: number } | null; scheduler: boolean; last_error: { at: string; detail: string } | null } | null;
  client_errors?: { at: string; where: string; url: string; version: string; errors: string[] }[];
  access?: { summary: { days: number; counts: Record<string, number>; last_problem: { kind: string; at: string; address: string } | null } | null; events: { id: number; kind: string; label: string; address: string; user_agent: string; detail: string; at: string }[] };
};

const panel = "rise rounded-2xl border border-stone-200 bg-white/70 p-5 backdrop-blur dark:border-stone-800 dark:bg-stone-900/60";
const railH = "text-[11px] font-semibold uppercase tracking-wider text-stone-400";

function Row({ label, value, ok }: { label: string; value: React.ReactNode; ok?: boolean | null }) {
  return (
    <div className="flex items-start gap-3 py-1.5 text-sm">
      <dt className="w-36 shrink-0 text-stone-500">{label}</dt>
      <dd className="min-w-0 flex-1 break-all">{ok === true && <CheckCircle2 className="mr-1 inline h-3.5 w-3.5 text-emerald-500" aria-hidden="true" />}{ok === false && <XCircle className="mr-1 inline h-3.5 w-3.5 text-red-500" aria-hidden="true" />}{value}</dd>
    </div>
  );
}

export default function Diagnostics() {
  const [network, setNetwork] = useState(false);
  const [copied, setCopied] = useState(false);
  const q = useQuery({ queryKey: ["diagnostics", network], queryFn: () => api<Report>(`/diagnostics/${network ? "?network=1" : ""}`) });
  const r = q.data;
  // LaTeX warm-up (2026-09-06): the first compile downloads the TeX bundle; do it here, on purpose
  const qc = useQueryClient();
  const warm = useMutation({ mutationFn: () => api<Latex>("/diagnostics/warm-latex/", { method: "POST" }), onSuccess: () => qc.invalidateQueries({ queryKey: ["diagnostics"] }) });
  const running = r?.latex.state === "running";
  // Restore from a backup (#376): staged now, applied at the next launch before the database opens
  const restore = useQuery({ queryKey: ["restore"], queryFn: () => api<RestoreState>("/restore/") });
  const stage = useMutation({
    mutationFn: async (file: File) => { const fd = new FormData(); fd.append("file", file); return api<{ staged: unknown }>("/restore/", { method: "POST", body: fd }); },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["restore"] }),
    onError: (e) => void errorDialog("That backup can't be restored", e),
  });
  const cancelRestore = useMutation({ mutationFn: () => api("/restore/", { method: "DELETE" }), onSuccess: () => qc.invalidateQueries({ queryKey: ["restore"] }) });
  const pickBackup = async (file: File | undefined) => {
    if (!file) return;
    if (await confirmDialog({ title: "Restore this backup?", danger: true, confirmLabel: "Stage the restore", body: <>“{file.name}” replaces <b>everything</b> — the database and every file — at the next launch of Atlas. The current data is kept next to it in the data folder, so this can be undone by hand. Nothing changes until you restart.</> })) stage.mutate(file);
  };
  // #462: a snapshot on demand — the same zip the daily scheduler writes
  const snapshot = useMutation({
    mutationFn: () => api<{ path: string; size_bytes: number; removed: string[] }>("/snapshots/", { method: "POST" }),
    onSuccess: () => { void qc.invalidateQueries({ queryKey: ["diagnostics"] }); void qc.invalidateQueries({ queryKey: ["snapshots"] }); },
    onError: (e) => void errorDialog("Couldn't write the snapshot", e),
  });
  // #463: the snapshots on disk, each restorable with one click (staged like an upload)
  const snapFiles = useQuery({ queryKey: ["snapshots"], queryFn: () => api<{ files: { name: string; size_bytes: number; created_at: string }[] }>("/snapshots/"), enabled: Boolean(r?.snapshots) });
  const restoreSnapshot = useMutation({
    mutationFn: (name: string) => api("/restore/", { method: "POST", body: JSON.stringify({ snapshot: name }), headers: { "Content-Type": "application/json" } }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["restore"] }),
    onError: (e) => void errorDialog("That snapshot can't be restored", e),
  });
  const pickSnapshot = async (name: string, at: string) => {
    if (await confirmDialog({ title: "Restore this snapshot?", danger: true, confirmLabel: "Stage the restore", body: <>The snapshot from <b>{new Date(at).toLocaleString()}</b> replaces <b>everything</b> — the database and every file — at the next launch of Atlas. The current data is kept next to it in the data folder. Nothing changes until you restart.</> })) restoreSnapshot.mutate(name);
  };
  const restartApp = async () => { try { const t = (await import("@tauri-apps/api")) as unknown as { core: { invoke: (c: string) => Promise<unknown> } }; await t.core.invoke("restart_app"); } catch (e) { void errorDialog("Couldn't restart", e); } };
  useEffect(() => { if (!running) return; const t = window.setInterval(() => qc.invalidateQueries({ queryKey: ["diagnostics"] }), 3000); return () => window.clearInterval(t); }, [running, qc]);
  const copy = async () => { if (!r) return; try { await navigator.clipboard.writeText(r.text); setCopied(true); window.setTimeout(() => setCopied(false), 2000); } catch { /* blocked */ } };

  return (
    <div className="mx-auto max-w-4xl">
      <nav className="mb-4 text-sm text-stone-400" aria-label="Breadcrumb"><Link to="/connect" className="hover:underline">Connect Claude Code</Link> / Diagnostics</nav>
      <div className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="flex items-center gap-2 text-3xl font-semibold tracking-tight"><Stethoscope className="h-7 w-7 text-indigo-500" aria-hidden="true" />Diagnostics</h1>
          <p className="mt-1 text-sm text-stone-500">Everything needed to explain a failure. Copy the report and paste it where you ask for help.</p>
        </div>
        <div className="flex items-center gap-2">
          <label className="inline-flex cursor-pointer items-center gap-2 rounded-lg border border-stone-200 bg-white px-3 py-1.5 text-sm dark:border-stone-700 dark:bg-stone-900"><input type="checkbox" checked={network} onChange={(e) => setNetwork(e.target.checked)} className="accent-indigo-600" /><Globe className="h-4 w-4 text-stone-400" aria-hidden="true" />Probe the update feed</label>
          <a href="/api/v1/backup.zip" className="inline-flex items-center gap-1.5 rounded-lg border border-stone-300 px-3 py-1.5 text-sm text-stone-700 hover:border-indigo-400 dark:border-stone-700 dark:text-stone-200" title="Download everything — database and files — as one zip. Restore notes are inside." data-testid="backup-link"><Download className="h-4 w-4" aria-hidden="true" />Download a backup</a>
          {/* #424: when the last backup was — amber once it is older than the threshold */}
          {r?.backups && (
            <span className={`text-xs ${r.backups.stale ? "text-amber-600 dark:text-amber-300" : "text-stone-400"}`} data-testid="last-backup" data-stale={r.backups.stale ? "1" : undefined}>
              {r.backups.last ? `last backup ${r.backups.last.days_ago === 0 ? "today" : `${r.backups.last.days_ago} d ago`}` : "no backup yet"}
            </span>
          )}
          <button type="button" onClick={() => void copy()} disabled={!r} className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50" data-testid="copy-report">{copied ? <Check className="h-4 w-4" aria-hidden="true" /> : <Copy className="h-4 w-4" aria-hidden="true" />}{copied ? "Copied" : "Copy report"}</button>
          {isDesktop() && <button type="button" onClick={() => void openDevtools()} className="inline-flex items-center gap-1.5 rounded-lg border border-stone-300 px-3 py-1.5 text-sm text-stone-700 hover:border-indigo-400 dark:border-stone-700 dark:text-stone-200" title="Open the web inspector (also F12 or Ctrl+Shift+I) — the console shows what a page threw" data-testid="open-inspector"><Stethoscope className="h-4 w-4" aria-hidden="true" />Web inspector</button>}
        </div>
      </div>
      {q.isLoading && <p className="flex items-center gap-2 text-sm text-stone-400"><Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />Collecting…</p>}
      {q.isError && <ErrorState message="Couldn't collect the diagnostics." onRetry={() => void q.refetch()} />}
      {r && (
        <>
          <section className={panel} style={{ ["--i" as string]: 1 }} data-testid="diag-summary">
            <p className={`${railH} mb-2`}>This install</p>
            <dl className="divide-y divide-stone-100 dark:divide-stone-800">
              <Row label="Version" value={<>{r.version} · {r.desktop ? "desktop" : "server"}{r.frozen ? " · bundled" : ""}</>} />
              <Row label="System" value={r.platform} />
              <Row label="Data folder" value={<code className="text-xs">{r.data_dir ?? "—"}</code>} />
              <Row label="Database" value={<code className="text-xs">{r.database}</code>} />
              <Row label="LaTeX engine" value={r.engine ? <code className="text-xs">{r.engine}</code> : "not found — compiles will fail"} ok={Boolean(r.engine)} />
              {r.engine && (
                <Row label="TeX bundle" ok={r.latex.warm ? true : r.latex.state === "failed" ? false : null} value={
                  <span className="flex flex-wrap items-center gap-2" data-testid="latex-warmup">
                    <span>{r.latex.warm ? `warm · ${r.latex.size_mb} MB cached` : "cold — the first compile downloads a few hundred MB and can take minutes"}</span>
                    {r.latex.state === "running" ? <span className="inline-flex items-center gap-1 text-xs text-indigo-500"><Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" />warming up…</span>
                      : <button type="button" onClick={() => warm.mutate()} disabled={warm.isPending} className="rounded-md border border-stone-300 px-2 py-0.5 text-xs text-stone-700 hover:border-indigo-400 dark:border-stone-700 dark:text-stone-200" data-testid="warm-latex">{r.latex.warm ? "Warm up again" : "Warm up now"}</button>}
                    {r.latex.state === "ok" && r.latex.seconds != null && <span className="text-xs text-emerald-600 dark:text-emerald-400">ready · last warm-up {r.latex.seconds}s</span>}
                    {r.latex.state === "failed" && <span className="text-xs text-red-600 dark:text-red-300" title={r.latex.log}>warm-up failed — {r.latex.log.split("\n").slice(-1)[0]?.slice(0, 120)}</span>}
                  </span>
                } />
              )}
              <Row label="Background jobs" value={r.jobs} />
              <Row label="API key" value={r.api_key_configured ? "configured" : "missing — the API and Claude cannot connect"} ok={r.api_key_configured} />
              {r.update_verdict && <Row label="Update check" value={<span data-testid="update-verdict" data-state={r.update_verdict.state}>{r.update_verdict.text}</span>} ok={r.update_verdict.state === "unchecked" || r.update_verdict.state === "unknown_version" ? null : r.update_verdict.state === "current" || r.update_verdict.state === "available"} />}
              {r.update_feed.map((f) => <Row key={f.url} label="Update feed" value={<><code className="text-xs">{f.url.replace("https://github.com/", "")}</code>{f.status !== null && <span className="ml-2 text-xs text-stone-500">→ {f.status}{f.status === 404 ? " (no feed at this address)" : ""}{f.version ? ` · offers ${f.version}` : ""}{f.key_match === false ? " · signed with a different key" : f.key_match ? " · signed for this app" : ""}</span>}</>} ok={f.status === null ? null : f.status === 200 && f.key_match !== false} />)}
            </dl>
          </section>
          {r.access?.summary && (
            <section className={`${panel} mt-5`} data-testid="access-log">
              <p className={`${railH} mb-2`}>Access · last {r.access.summary.days} days</p>
              <p className="mb-2 text-sm text-stone-600 dark:text-stone-300">
                {r.access.summary.counts.login_ok ?? 0} logins · {r.access.summary.counts.login_failed ?? 0} failed · {r.access.summary.counts.login_locked ?? 0} lockouts · {r.access.summary.counts.api_key_rejected ?? 0} rejected API keys
                {r.access.summary.last_problem && <span className="ml-2 text-amber-600 dark:text-amber-300">· last problem {r.access.summary.last_problem.at.replace("T", " ").slice(0, 16)} from {r.access.summary.last_problem.address || "?"}</span>}
              </p>
              {r.access.events.length > 0 ? (
                <ul className="divide-y divide-stone-100 text-xs dark:divide-stone-800">
                  {r.access.events.map((e) => (
                    <li key={e.id} className="flex flex-wrap items-center gap-2 py-1.5">
                      <span className={`rounded-full px-1.5 py-0.5 text-[10px] font-medium ${e.kind === "login_ok" ? "bg-emerald-500/10 text-emerald-700 dark:text-emerald-300" : "bg-amber-500/10 text-amber-700 dark:text-amber-300"}`}>{e.label}</span>
                      <span className="font-mono text-stone-500">{e.at.replace("T", " ").slice(0, 16)}</span>
                      <span className="text-stone-500">{e.address || "?"}</span>
                      {e.detail && <span className="text-stone-400">{e.detail}</span>}
                      <span className="ml-auto max-w-[24rem] truncate text-stone-400" title={e.user_agent}>{e.user_agent}</span>
                    </li>
                  ))}
                </ul>
              ) : <p className="text-xs text-stone-400">No events yet — logins and rejected keys appear here.</p>}
            </section>
          )}
          {r.client_errors && r.client_errors.length > 0 && (
            <section className={`${panel} mt-5`} data-testid="client-errors">
              <p className={`${railH} mb-2`}><AlertTriangle className="mr-1 inline h-3.5 w-3.5 text-amber-500" aria-hidden="true" />Front-end errors · most recent first</p>
              <ul className="space-y-2">
                {r.client_errors.map((e, i) => (
                  <li key={i} className="rounded-lg bg-stone-950 p-3 font-mono text-[11px] leading-4 text-stone-200">
                    <p className="mb-1 text-stone-400">{e.at} · {e.where} · {e.url} · {e.version || "dev"}</p>
                    <pre className="whitespace-pre-wrap break-words">{e.errors.join("\n") || "(no message captured)"}</pre>
                  </li>
                ))}
              </ul>
            </section>
          )}
          {r.last_failed_compile && (
            <section className={`${panel} mt-5`} style={{ ["--i" as string]: 2 }} data-testid="diag-compile">
              <p className={`${railH} mb-2`}><AlertTriangle className="mr-1 inline h-3.5 w-3.5 text-amber-500" aria-hidden="true" />Last failed compile · <Link to={`/manuscripts/${r.last_failed_compile.manuscript}/editor`} className="normal-case tracking-normal text-indigo-600 hover:underline dark:text-indigo-300">{r.last_failed_compile.title}</Link></p>
              <pre className="max-h-64 overflow-auto rounded-lg bg-stone-950 p-3 font-mono text-[11px] leading-4 text-stone-200">{r.last_failed_compile.log || "(no log captured)"}</pre>
            </section>
          )}
          <section className={`${panel} mt-5`} style={{ ["--i" as string]: 2.5 }} data-testid="restore">
            <p className={`${railH} mb-2`}><RotateCcw className="mr-1 inline h-3.5 w-3.5" aria-hidden="true" />Restore from a backup</p>
            {restore.data?.pending ? (
              <div className="rounded-xl border border-amber-300/60 bg-amber-50/60 p-3 text-sm dark:border-amber-500/40 dark:bg-amber-500/10" data-testid="restore-pending">
                <p className="font-medium text-amber-900 dark:text-amber-100">A restore is staged{restore.data.pending.created_at ? ` — backup from ${new Date(restore.data.pending.created_at).toLocaleString()}` : ""}.</p>
                <p className="mt-1 text-xs text-amber-800/80 dark:text-amber-200/80">{restore.data.pending.has_sqlite ? "Database file" : "JSON dump"} · {restore.data.pending.media_files} media file{restore.data.pending.media_files === 1 ? "" : "s"} · {(restore.data.pending.size_bytes / 1048576).toFixed(1)} MB. It is applied the next time Atlas starts, before the database opens; the current data is kept in the data folder.</p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {isDesktop() ? <button type="button" onClick={() => void restartApp()} className="rounded-md bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-700" data-testid="restore-restart">Restart Atlas and restore now</button> : <span className="text-xs text-stone-500">Restart the server to apply it (a Docker/server install: <code>manage.py restore_backup</code> while stopped).</span>}
                  <button type="button" onClick={() => cancelRestore.mutate()} className="rounded-md border border-stone-300 px-3 py-1.5 text-xs text-stone-700 hover:border-red-400 dark:border-stone-700 dark:text-stone-200" data-testid="restore-cancel">Cancel</button>
                </div>
              </div>
            ) : (
              <label className="flex cursor-pointer flex-wrap items-center gap-3 rounded-xl border border-dashed border-stone-300 p-3 text-sm text-stone-600 hover:border-indigo-400 dark:border-stone-700 dark:text-stone-300">
                <Upload className="h-4 w-4 text-stone-400" aria-hidden="true" />
                <span className="min-w-0 flex-1">Choose an Atlas backup zip (from <b>Download a backup</b>) to put everything back the way it was. {stage.isPending && <span className="text-indigo-500">Uploading…</span>}</span>
                <input type="file" accept=".zip,application/zip" className="hidden" onChange={(e) => { void pickBackup(e.target.files?.[0]); e.target.value = ""; }} data-testid="restore-file" />
              </label>
            )}
            {restore.data?.last_result && <p className={`mt-2 text-xs ${restore.data.last_result.ok ? "text-emerald-600 dark:text-emerald-400" : "text-red-600 dark:text-red-300"}`} data-testid="restore-result">Last restore ({new Date(restore.data.last_result.applied_at).toLocaleString()}): {restore.data.last_result.detail}{restore.data.last_result.ok ? ` Previous data kept in ${restore.data.last_result.kept_previous_in}.` : ""}</p>}
          </section>
          {r.snapshots && (
            <section className={`${panel} mt-5`} style={{ ["--i" as string]: 2.7 }} data-testid="snapshots" data-count={r.snapshots.count}>
              <p className={`${railH} mb-2`}><Camera className="mr-1 inline h-3.5 w-3.5" aria-hidden="true" />Automatic snapshots</p>
              <p className="text-sm text-stone-600 dark:text-stone-300">
                {r.desktop || r.snapshots.scheduler
                  ? <>Atlas writes a backup zip into its data folder once every {r.snapshots.every_hours} hours while it runs and keeps the last {r.snapshots.keep}.</>
                  : <>A server install writes these from cron: <code className="text-xs">manage.py snapshot --if-due</code> keeps the last {r.snapshots.keep}, one a day.</>}
                {" "}Nothing to remember — the newest one is always there.
              </p>
              <dl className="mt-2 divide-y divide-stone-100 dark:divide-stone-800">
                <Row label="Folder" value={<span className="flex flex-wrap items-center gap-2"><code className="text-xs">{r.snapshots.dir}</code>{isDesktop() && r.snapshots.count > 0 && <button type="button" onClick={() => { revealPath(r.snapshots!.last!.path).catch((e) => void errorDialog("Couldn't show the folder", e)); }} className="inline-flex items-center gap-1 rounded-md border border-stone-300 px-2 py-0.5 text-xs text-stone-700 hover:border-indigo-400 dark:border-stone-700 dark:text-stone-200" data-testid="snapshot-reveal"><FolderOpen className="h-3 w-3" aria-hidden="true" />Show in folder</button>}</span>} />
                <Row label="Newest" ok={r.snapshots.last_error ? false : r.snapshots.last ? true : null} value={
                  <span className="flex flex-wrap items-center gap-2" data-testid="snapshot-last">
                    <span>{r.snapshots.last ? `${r.snapshots.last.name} · ${(r.snapshots.last.size_bytes / 1048576).toFixed(1)} MB · ${r.snapshots.last.hours_ago === 0 ? "less than an hour ago" : `${r.snapshots.last.hours_ago} h ago`}` : r.snapshots.scheduler ? "none yet — the first one is written a minute or two after launch" : "none yet"}</span>
                    <button type="button" onClick={() => snapshot.mutate()} disabled={snapshot.isPending} className="inline-flex items-center gap-1 rounded-md border border-stone-300 px-2 py-0.5 text-xs text-stone-700 hover:border-indigo-400 disabled:opacity-50 dark:border-stone-700 dark:text-stone-200" data-testid="snapshot-now">{snapshot.isPending ? <Loader2 className="h-3 w-3 animate-spin" aria-hidden="true" /> : <Camera className="h-3 w-3" aria-hidden="true" />}Snapshot now</button>
                    {snapshot.data && <span className="text-xs text-emerald-600 dark:text-emerald-400" data-testid="snapshot-written">written{snapshot.data.removed.length ? ` · ${snapshot.data.removed.length} old removed` : ""}</span>}
                  </span>
                } />
                <Row label="Kept" value={`${r.snapshots.count} of ${r.snapshots.keep} · ${(r.snapshots.total_bytes / 1048576).toFixed(1)} MB in total`} />
                {r.snapshots.last_error && <Row label="Last failure" ok={false} value={<span className="text-red-600 dark:text-red-300" data-testid="snapshot-error">{r.snapshots.last_error.detail} ({new Date(r.snapshots.last_error.at).toLocaleString()})</span>} />}
              </dl>
              {snapFiles.data && snapFiles.data.files.length > 0 && (
                <ul className="mt-3 divide-y divide-stone-100 rounded-xl border border-stone-200 text-sm dark:divide-stone-800 dark:border-stone-800" data-testid="snapshot-files">
                  {snapFiles.data.files.map((f) => (
                    <li key={f.name} className="flex flex-wrap items-center gap-3 px-3 py-1.5">
                      <code className="text-xs">{f.name}</code>
                      <span className="text-xs text-stone-400">{(f.size_bytes / 1048576).toFixed(1)} MB · {new Date(f.created_at).toLocaleString()}</span>
                      <button type="button" onClick={() => void pickSnapshot(f.name, f.created_at)} disabled={restoreSnapshot.isPending || Boolean(restore.data?.pending)} className="ml-auto inline-flex items-center gap-1 rounded-md border border-stone-300 px-2 py-0.5 text-xs text-stone-700 hover:border-amber-400 disabled:opacity-50 dark:border-stone-700 dark:text-stone-200" title="Stage this snapshot as the restore applied at the next launch" data-testid="snapshot-restore"><RotateCcw className="h-3 w-3" aria-hidden="true" />Restore…</button>
                    </li>
                  ))}
                </ul>
              )}
            </section>
          )}
          <section className={`${panel} mt-5`} style={{ ["--i" as string]: 3 }}>
            <p className={`${railH} mb-2`}>Server log · last lines</p>
            {r.server_log ? <pre className="max-h-80 overflow-auto rounded-lg bg-stone-950 p-3 font-mono text-[11px] leading-4 text-stone-200">{r.server_log}</pre> : <p className="text-sm text-stone-500">No server log here — the desktop app writes one to its data folder; a development server logs to the terminal.</p>}
          </section>
        </>
      )}
    </div>
  );
}
