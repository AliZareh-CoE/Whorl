/**
 * The Atlas command bar ([REV] cycle 65). Cmd/Ctrl-K anywhere in the SPA:
 * fuzzy jump-to-anything, real verbs (capture:, done:), page-aware quick
 * actions, and the "Ask Claude about this" MCP handoff. Local + instant.
 */
import { useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { api, csrfToken } from "./api";
import { toSpaUrl } from "./links";

type Command = { title: string; type: string; url: string };
type Action = { label: string; url: string };
type Recent = { title: string; when: string; url: string; type: string };
type AssistantContext = {
  context: { project?: { name: string; slug: string } };
  actions: Action[];
  commands: Command[];
  claude_prompt: string;
  recent: Recent[];
};
type Milestone = { id: number; title: string; completed_at: string | null };
type PlanData = { phases: { milestones: Milestone[] }[] };

/** Subsequence fuzzy score — higher is better, null = no match. */
function fuzzy(needle: string, haystack: string): number | null {
  const n = needle.toLowerCase();
  const h = haystack.toLowerCase();
  if (!n) return 0;
  let score = 0, hi = 0, streak = 0;
  for (const ch of n) {
    const found = h.indexOf(ch, hi);
    if (found === -1) return null;
    streak = found === hi ? streak + 1 : 1;
    score += streak * 2 + (found === 0 || /\W/.test(h[found - 1] ?? "") ? 3 : 0);
    hi = found + 1;
  }
  return score - h.length * 0.01;
}

type Row =
  | { kind: "nav"; label: string; tag: string; url: string }
  | { kind: "milestone"; label: string; tag: string; id: number }
  | { kind: "verb"; label: string; tag: string; run: () => Promise<string> };

export default function CommandBar() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const [flash, setFlash] = useState("");
  const [assistant, setAssistant] = useState<AssistantContext | null>(null);
  const [plan, setPlan] = useState<PlanData | null>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();

  const slug = location.pathname.match(/^\/projects\/([^/]+)/)?.[1] ?? null;

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((v) => !v);
      } else if (e.key === "Escape") setOpen(false);
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (!open) { setQuery(""); setActive(0); setFlash(""); return; }
    setTimeout(() => inputRef.current?.focus(), 30);
    fetch(`/assistant/context/?path=${encodeURIComponent("/projects/" + (slug ?? "") + "/")}`,
          { credentials: "same-origin" })
      .then((r) => r.json())
      .then(setAssistant)
      .catch(() => setAssistant(null));
    if (slug) {
      api<PlanData>(`/projects/${slug}/plan/`).then(setPlan).catch(() => setPlan(null));
    } else setPlan(null);
  }, [open, slug]);

  const doCapture = useCallback(async (text: string) => {
    await api("/quick-capture/", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
      body: JSON.stringify({ text }),
    });
    queryClient.invalidateQueries({ queryKey: ["inbox"] });
    return `Captured: ${text.slice(0, 60)}`;
  }, [queryClient]);

  const doComplete = useCallback(async (id: number, title: string) => {
    await api(`/milestones/${id}/`, {
      method: "PATCH",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
      body: JSON.stringify({ completed_at: new Date().toISOString() }),
    });
    queryClient.invalidateQueries({ queryKey: ["plan", slug] });
    queryClient.invalidateQueries({ queryKey: ["overview", slug] });
    return `✓ ${title}`;
  }, [queryClient, slug]);

  const rows: Row[] = useMemo(() => {
    const q = query.trim();
    if (q.toLowerCase().startsWith("capture:") || q.toLowerCase().startsWith("c:")) {
      const text = q.slice(q.indexOf(":") + 1).trim();
      return text
        ? [{ kind: "verb", label: `Capture “${text}”`, tag: "inbox", run: () => doCapture(text) }]
        : [];
    }
    if (q.toLowerCase().startsWith("done:")) {
      const needle = q.slice(5).trim();
      const open_ms = (plan?.phases ?? []).flatMap((p) => p.milestones).filter((m) => !m.completed_at);
      return open_ms
        .map((m) => ({ m, s: fuzzy(needle, m.title) }))
        .filter((x): x is { m: Milestone; s: number } => x.s !== null)
        .sort((a, b) => b.s - a.s)
        .slice(0, 6)
        .map(({ m }) => ({
          kind: "milestone" as const,
          label: m.title,
          tag: "done ✓",
          id: m.id,
        }));
    }
    if (!q) return [];
    return (assistant?.commands ?? [])
      .map((c) => ({ c, s: fuzzy(q, c.title) }))
      .filter((x): x is { c: Command; s: number } => x.s !== null)
      .sort((a, b) => b.s - a.s)
      .slice(0, 8)
      .map(({ c }) => ({ kind: "nav" as const, label: c.title, tag: c.type, url: c.url }));
  }, [query, assistant, plan, doCapture]);

  useEffect(() => setActive(0), [query]);

  async function runRow(row: Row) {
    if (row.kind === "nav") {
      const { to, spa } = toSpaUrl(row.url);
      setOpen(false);
      if (spa) navigate(to);
      else location_assign(row.url);
    } else if (row.kind === "milestone") {
      setFlash(await doComplete(row.id, row.label));
      setQuery("");
    } else {
      setFlash(await row.run());
      setQuery("");
    }
  }
  function location_assign(url: string) { window.location.assign(url); }

  async function copyClaudePrompt() {
    if (!assistant) return;
    await navigator.clipboard.writeText(assistant.claude_prompt);
    setFlash("Claude prompt copied — paste it into your Claude session");
  }

  if (!open) return null;
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center pt-[12vh]">
      <div className="absolute inset-0 bg-stone-900/30" onClick={() => setOpen(false)} aria-hidden="true" />
      <div role="dialog" aria-modal="true" aria-label="Command bar"
           className="relative w-full max-w-xl rounded-lg border border-stone-200 bg-white shadow-2xl">
        <input
          ref={inputRef}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(a + 1, rows.length - 1)); }
            else if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(a - 1, 0)); }
            else if (e.key === "Enter" && rows[active]) runRow(rows[active]);
          }}
          placeholder="Jump anywhere — or  capture: idea   done: milestone"
          aria-label="Command"
          className="w-full rounded-t-lg border-b border-stone-100 px-4 py-3 text-sm focus:outline-none"
        />
        {flash && <p className="border-b border-stone-100 bg-green-50 px-4 py-2 text-xs text-green-700">{flash}</p>}

        {rows.length > 0 && (
          <ul role="listbox" className="max-h-72 overflow-y-auto py-1">
            {rows.map((row, i) => (
              <li key={`${row.kind}-${row.label}-${i}`}>
                <button
                  type="button"
                  role="option"
                  aria-selected={i === active}
                  onClick={() => runRow(row)}
                  onMouseEnter={() => setActive(i)}
                  className={`flex w-full items-center gap-2 px-4 py-2 text-left text-sm ${i === active ? "bg-indigo-50" : ""}`}
                >
                  <span className="rounded bg-stone-100 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-stone-400">
                    {row.tag}
                  </span>
                  <span className="min-w-0 flex-1 truncate text-stone-700">{row.label}</span>
                </button>
              </li>
            ))}
          </ul>
        )}

        {!query && (
          <div className="px-4 py-3">
            {assistant && assistant.actions.length > 0 && (
              <div className="mb-3 flex flex-wrap gap-1.5">
                {assistant.actions.map((a) => {
                  const { to, spa } = toSpaUrl(a.url);
                  return (
                    <button key={a.url + a.label} type="button"
                            onClick={() => { setOpen(false); spa ? navigate(to) : window.location.assign(a.url); }}
                            className="rounded-full border border-stone-200 px-2.5 py-1 text-xs text-stone-600 hover:border-indigo-400 hover:text-indigo-700">
                      {a.label}
                    </button>
                  );
                })}
              </div>
            )}
            <button type="button" onClick={copyClaudePrompt}
                    className="mb-3 w-full rounded border border-stone-200 bg-stone-50 px-3 py-2 text-left text-xs text-stone-600 hover:border-indigo-300">
              ✨ Ask Claude about this — copy a context-rich MCP prompt
            </button>
            {assistant && assistant.recent.length > 0 && (
              <ul className="space-y-1">
                {assistant.recent.slice(0, 5).map((r) => {
                  const { to, spa } = toSpaUrl(r.url);
                  return (
                    <li key={r.url + r.title}>
                      <button type="button"
                              onClick={() => { setOpen(false); spa ? navigate(to) : window.location.assign(r.url); }}
                              className="flex w-full items-baseline gap-2 text-left text-sm hover:text-indigo-700">
                        <span className="rounded bg-stone-100 px-1 py-0.5 text-[10px] uppercase tracking-wide text-stone-400">{r.type}</span>
                        <span className="min-w-0 flex-1 truncate text-stone-600">{r.title}</span>
                        <span className="shrink-0 text-xs text-stone-400">{r.when}</span>
                      </button>
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        )}
        <p className="rounded-b-lg border-t border-stone-100 px-4 py-1.5 text-[10px] text-stone-400">
          ↑↓ navigate · Enter run · Esc close ·  capture: <i>text</i>  ·  done: <i>milestone</i>
        </p>
      </div>
    </div>
  );
}
