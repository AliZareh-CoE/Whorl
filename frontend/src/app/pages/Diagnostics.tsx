/* Diagnostics (2026-09-06): the page to open when something on the desktop "didn't work".
 * Version, paths, the LaTeX engine, the update feed (probed on request), the last compile
 * failure and the server log tail — and one button that copies it all as text. */
import { useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router-dom";
import { AlertTriangle, Check, CheckCircle2, Copy, Download, Globe, Loader2, Stethoscope, XCircle } from "lucide-react";
import { api } from "../api";

type Feed = { url: string; status: number | string | null };
type Report = {
  version: string; desktop: boolean; platform: string; frozen: boolean; settings_module: string; data_dir: string | null; database: string;
  engine: string | null; jobs: string; api_key_configured: boolean; update_feed: Feed[];
  last_failed_compile: { manuscript: number; title: string; log: string; at: string } | null; server_log: string; text: string;
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
          <button type="button" onClick={() => void copy()} disabled={!r} className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50" data-testid="copy-report">{copied ? <Check className="h-4 w-4" aria-hidden="true" /> : <Copy className="h-4 w-4" aria-hidden="true" />}{copied ? "Copied" : "Copy report"}</button>
        </div>
      </div>
      {q.isLoading && <p className="flex items-center gap-2 text-sm text-stone-400"><Loader2 className="h-4 w-4 animate-spin" aria-hidden="true" />Collecting…</p>}
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
              <Row label="Background jobs" value={r.jobs} />
              <Row label="API key" value={r.api_key_configured ? "configured" : "missing — the API and Claude cannot connect"} ok={r.api_key_configured} />
              {r.update_feed.map((f) => <Row key={f.url} label="Update feed" value={<><code className="text-xs">{f.url.replace("https://github.com/", "")}</code>{f.status !== null && <span className="ml-2 text-xs text-stone-500">→ {f.status}{f.status === 404 ? " (private repository or missing feed)" : ""}</span>}</>} ok={f.status === null ? null : f.status === 200} />)}
            </dl>
          </section>
          {r.last_failed_compile && (
            <section className={`${panel} mt-5`} style={{ ["--i" as string]: 2 }} data-testid="diag-compile">
              <p className={`${railH} mb-2`}><AlertTriangle className="mr-1 inline h-3.5 w-3.5 text-amber-500" aria-hidden="true" />Last failed compile · <Link to={`/manuscripts/${r.last_failed_compile.manuscript}/editor`} className="normal-case tracking-normal text-indigo-600 hover:underline dark:text-indigo-300">{r.last_failed_compile.title}</Link></p>
              <pre className="max-h-64 overflow-auto rounded-lg bg-stone-950 p-3 font-mono text-[11px] leading-4 text-stone-200">{r.last_failed_compile.log || "(no log captured)"}</pre>
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
