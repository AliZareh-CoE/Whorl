/* Connect Claude Code (moved into the app, 2026-09-06): the one page that turns Atlas into a
 * Claude tool. Three steps — register, check, skills — with copy buttons, and on the desktop
 * a "run it here" button that opens the terminal dock with the command already typed. */
import { useState } from "react";
import { Link } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Check, Copy, Eye, EyeOff, ExternalLink, Plug, Sparkles, Stethoscope, TerminalSquare } from "lucide-react";
import { api } from "../api";
import { openTerminal } from "../TerminalDock";

type Skill = { name: string; description: string; folder: string; installed: boolean; up_to_date: boolean };
type Tool = { key: string; label: string; found: boolean; path: string | null; version: string; install: string };
type Conn = { tools: Tool[]; desktop: boolean; api_url: string; api_key: string; api_key_configured: boolean; command: string; args: string[]; env: Record<string, string>; claude_command: string; mcp_json: string; data_dir: string | null; skills: Skill[]; skills_dir: string };

const panel = "rise rounded-2xl border border-stone-200 bg-white/70 p-5 backdrop-blur dark:border-stone-800 dark:bg-stone-900/60";
const railH = "text-[11px] font-semibold uppercase tracking-wider text-stone-400";
const isDesktop = () => typeof window !== "undefined" && "__TAURI__" in window;

function CopyButton({ text, label = "Copy" }: { text: string; label?: string }) {
  const [done, setDone] = useState(false);
  return (
    <button type="button" onClick={async () => { try { await navigator.clipboard.writeText(text); setDone(true); window.setTimeout(() => setDone(false), 1800); } catch { /* clipboard blocked */ } }} className="inline-flex shrink-0 items-center gap-1 rounded-md border border-stone-300 px-2.5 py-1.5 text-xs text-stone-700 transition-colors hover:border-indigo-400 hover:text-indigo-700 dark:border-stone-700 dark:text-stone-300 dark:hover:text-indigo-300" aria-label={label}>
      {done ? <Check className="h-3.5 w-3.5 text-emerald-500" aria-hidden="true" /> : <Copy className="h-3.5 w-3.5" aria-hidden="true" />}{done ? "Copied" : label}
    </button>
  );
}

export default function Connect() {
  const qc = useQueryClient();
  const q = useQuery({ queryKey: ["connect"], queryFn: () => api<Conn>("/connect/") });
  const install = useMutation({ mutationFn: () => api<{ installed: string[]; dir: string }>("/connect/skills/", { method: "POST" }), onSuccess: () => qc.invalidateQueries({ queryKey: ["connect"] }) });
  const [showKey, setShowKey] = useState(false);
  const c = q.data;
  if (q.isLoading) return <p className="text-sm text-stone-400">Loading…</p>;
  if (!c) return <p className="text-sm text-red-500">Could not load the connection details.</p>;
  const installed = c.skills.filter((s) => s.up_to_date).length;

  return (
    <div className="mx-auto max-w-4xl">
      <nav className="mb-4 flex items-center text-sm text-stone-400" aria-label="Breadcrumb">Connect Claude Code<Link to="/diagnostics" className="ml-auto inline-flex items-center gap-1 text-xs text-indigo-600 hover:underline dark:text-indigo-300"><Stethoscope className="h-3.5 w-3.5" aria-hidden="true" />Diagnostics</Link></nav>
      <h1 className="text-3xl font-semibold tracking-tight"><span className="text-gradient">Claude</span> works inside Atlas</h1>
      <p className="mt-2 max-w-2xl text-sm text-stone-500">Atlas ships an MCP server: register it once and Claude Code can list your projects, tick milestones, add papers by DOI, write notes, drive the manuscript studio and run bib checks — everything the API can do, 88 tools. Four skills teach it the workflows.</p>

      <div className={`${panel} mt-5 flex items-start gap-3 text-sm`} style={{ ["--i" as string]: 1 }}>
        <Plug className="mt-0.5 h-4 w-4 shrink-0 text-indigo-500" aria-hidden="true" />
        <p className="text-stone-600 dark:text-stone-300">{c.desktop ? <><strong>Desktop build detected.</strong> The MCP server ships with the app as <code className="rounded bg-stone-100 px-1 dark:bg-stone-800">atlas-mcp</code> and finds this Atlas by itself — the command below needs no key.</> : <><strong>Development / server install.</strong> The MCP server runs from this checkout's Python; the command passes the API URL and key explicitly.</>}</p>
      </div>
      <ul className="mt-3 flex flex-wrap gap-2 text-xs" data-testid="tools-on-machine" aria-label="Tools on this machine">
        {c.tools.map((t) => <li key={t.key} className={`inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 ${t.found ? "border-emerald-300/60 bg-emerald-500/10 text-emerald-700 dark:text-emerald-300" : "border-stone-200 text-stone-500 dark:border-stone-700"}`} title={t.found ? `${t.path}${t.version ? ` · ${t.version}` : ""}` : `Not found on PATH — ${t.install}`}>{t.found ? <Check className="h-3 w-3" aria-hidden="true" /> : <span aria-hidden="true">·</span>}{t.label}{t.found && t.version && <span className="opacity-70">{t.version.replace(/^[^0-9]*/, "").split(" ")[0]}</span>}{!t.found && <span className="opacity-70">not found</span>}</li>)}
      </ul>
      {c.tools.some((t) => t.key === "claude" && !t.found) && <p className="mt-2 text-xs text-stone-500">Claude Code is not on this machine's PATH yet — install it with <code className="rounded bg-stone-100 px-1 dark:bg-stone-800">npm i -g @anthropic-ai/claude-code</code>, then reopen this page.</p>}
      {!c.api_key_configured && <div className="mt-3 rounded-xl border border-amber-300 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:border-amber-700 dark:bg-amber-950/40 dark:text-amber-200">No API key is configured, so the API rejects every request. Set <code>ATLAS_API_KEY</code> in <code>.env</code> (or run <code>manage.py rotate_api_key</code>), restart, then come back.</div>}

      <section className={`${panel} mt-5`} style={{ ["--i" as string]: 2 }} data-testid="connect-step-1">
        <p className={`${railH} mb-2`}>1 · Register Atlas in Claude Code</p>
        <p className="mb-2 text-sm text-stone-500">Run this once on this machine (Claude Code installed: <code className="rounded bg-stone-100 px-1 text-xs dark:bg-stone-800">npm i -g @anthropic-ai/claude-code</code>).</p>
        <div className="flex items-start gap-2">
          <pre className="min-w-0 flex-1 overflow-x-auto rounded-lg bg-stone-950 px-4 py-3 text-xs leading-5 text-stone-100" data-testid="claude-command">{c.claude_command}</pre>
          <CopyButton text={c.claude_command} />
          {isDesktop() && <button type="button" onClick={() => openTerminal({ command: c.claude_command })} className="inline-flex shrink-0 items-center gap-1 rounded-md bg-indigo-600 px-2.5 py-1.5 text-xs font-medium text-white hover:bg-indigo-700" title="Open the terminal dock and run it"><TerminalSquare className="h-3.5 w-3.5" aria-hidden="true" />Run it here</button>}
        </div>
      </section>

      <section className={`${panel} mt-5`} style={{ ["--i" as string]: 3 }}>
        <p className={`${railH} mb-2`}>2 · Check it</p>
        <p className="text-sm text-stone-500"><code className="rounded bg-stone-100 px-1 text-xs dark:bg-stone-800">claude mcp list</code> should show <strong>atlas</strong> as connected while Atlas is running. Then, inside Claude Code, try <em>“List my Atlas projects.”</em>{isDesktop() && <> — or press the <strong>Claude</strong> button in the terminal dock (⌃`) to start a session right here.</>}</p>
      </section>

      <section className={`${panel} mt-5`} style={{ ["--i" as string]: 4 }} data-testid="connect-skills">
        <div className="mb-2 flex items-center justify-between"><p className={railH}>3 · Give Claude the Atlas playbooks <span className="normal-case tracking-normal text-stone-400">{installed}/{c.skills.length} installed</span></p><button type="button" onClick={() => install.mutate()} disabled={install.isPending} className="inline-flex items-center gap-1 rounded-md bg-indigo-600 px-2.5 py-1.5 text-xs font-medium text-white hover:bg-indigo-700 disabled:opacity-50"><Sparkles className="h-3.5 w-3.5" aria-hidden="true" />{install.isPending ? "Installing…" : installed === c.skills.length ? "Reinstall" : "Install / update the skills"}</button></div>
        <p className="mb-3 text-sm text-stone-500">Skills are short playbooks Claude Code loads on demand — a research day, a literature review, a manuscript, a plan — tool by tool, with the conventions that keep your data safe. They install into <code className="rounded bg-stone-100 px-1 text-xs dark:bg-stone-800">{c.skills_dir}</code>.</p>
        <ul className="divide-y divide-stone-100 dark:divide-stone-800">
          {c.skills.map((s) => (
            <li key={s.folder} className="flex items-start gap-3 py-2.5 text-sm">
              <code className="mt-0.5 shrink-0 rounded bg-indigo-500/10 px-1.5 py-0.5 text-xs text-indigo-700 dark:text-indigo-300">/{s.name}</code>
              <span className="min-w-0 flex-1 text-stone-600 dark:text-stone-300">{s.description}</span>
              <span className={`shrink-0 text-[11px] ${s.up_to_date ? "text-emerald-600 dark:text-emerald-400" : s.installed ? "text-amber-600 dark:text-amber-400" : "text-stone-400"}`}>{s.up_to_date ? "installed" : s.installed ? "older copy" : "not installed"}</span>
            </li>
          ))}
        </ul>
        {install.data && <p className="mt-2 text-xs text-emerald-600 dark:text-emerald-400">Installed {install.data.installed.length} skills into {install.data.dir}. In Claude Code: <em>“/atlas-daily — what should I work on?”</em></p>}
        {install.error && <p className="mt-2 text-xs text-red-500">Could not install the skills — is the home folder writable?</p>}
      </section>

      <section className={`${panel} mt-5`} style={{ ["--i" as string]: 5 }}>
        <p className={`${railH} mb-2`}>Connection details</p>
        <dl className="grid grid-cols-[max-content_1fr] gap-x-6 gap-y-2 text-sm">
          <dt className="text-stone-500">API URL</dt><dd><code className="rounded bg-stone-100 px-1 text-xs dark:bg-stone-800">{c.api_url}/api/v1/</code></dd>
          <dt className="text-stone-500">API key</dt>
          <dd className="min-w-0">{c.api_key_configured ? <span className="inline-flex flex-wrap items-center gap-2"><code className="break-all rounded bg-stone-100 px-1 text-xs dark:bg-stone-800">{showKey ? c.api_key : "•".repeat(Math.min(24, c.api_key.length))}</code><button type="button" onClick={() => setShowKey((v) => !v)} className="text-stone-400 hover:text-stone-700 dark:hover:text-stone-200" aria-label={showKey ? "Hide key" : "Show key"}>{showKey ? <EyeOff className="h-3.5 w-3.5" aria-hidden="true" /> : <Eye className="h-3.5 w-3.5" aria-hidden="true" />}</button><CopyButton text={c.api_key} label="copy" /><span className="block w-full text-xs text-stone-500">Header <code>X-API-Key</code>. Treat it like a password — it grants full access to this Atlas.</span></span> : <span className="text-stone-500">not configured</span>}</dd>
          <dt className="text-stone-500">MCP command</dt><dd><code className="break-all rounded bg-stone-100 px-1 text-xs dark:bg-stone-800">{[c.command, ...c.args].join(" ")}</code></dd>
          {c.data_dir && <><dt className="text-stone-500">Data folder</dt><dd><code className="break-all rounded bg-stone-100 px-1 text-xs dark:bg-stone-800">{c.data_dir}</code></dd></>}
          <dt className="text-stone-500">API docs</dt><dd><a href="/api/docs/" target="_blank" rel="noreferrer" className="inline-flex items-center gap-1 text-indigo-600 hover:underline dark:text-indigo-400">{c.api_url}/api/docs/<ExternalLink className="h-3 w-3" aria-hidden="true" /></a></dd>
        </dl>
      </section>

      <details className={`${panel} mt-5 text-sm`} style={{ ["--i" as string]: 6 }}>
        <summary className="cursor-pointer text-stone-600 hover:text-stone-900 dark:text-stone-300 dark:hover:text-stone-100">Other MCP clients (Claude Desktop, Cursor, a project <code>.mcp.json</code>)</summary>
        <p className="mt-2 text-stone-500">Add this server entry to the client's MCP configuration:</p>
        <div className="mt-2 flex items-start gap-2"><pre className="min-w-0 flex-1 overflow-x-auto rounded-lg bg-stone-950 px-4 py-3 text-xs leading-5 text-stone-100">{c.mcp_json}</pre><CopyButton text={c.mcp_json} /></div>
      </details>
    </div>
  );
}
