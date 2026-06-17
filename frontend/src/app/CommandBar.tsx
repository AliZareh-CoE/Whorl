/**
 * The Atlas command bar ([REV] cycle 65). Cmd/Ctrl-K anywhere in the SPA:
 * fuzzy jump-to-anything, real verbs (capture:, done:), page-aware quick
 * actions, and the "Ask Claude about this" MCP handoff. Local + instant.
 */
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { api, csrfToken, petReact } from "./api";
import { toggleCalm } from "./calm";
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
  const inputRef = useRef<HTMLInputElement>(null);
  const navigate = useNavigate();
  const location = useLocation();
  const queryClient = useQueryClient();

  const slug = location.pathname.match(/^\/projects\/([^/]+)/)?.[1] ?? null;

  // #73: the assistant index is cached per path (stale-while-revalidate) and kept warm, so
  // ⌘K is instant on every open — the first open prefetches, repeats read from cache.
  const { data: assistant = null } = useQuery({
    queryKey: ["assistant-context", slug],
    queryFn: () =>
      fetch(`/assistant/context/?path=${encodeURIComponent("/projects/" + (slug ?? "") + "/")}`,
            { credentials: "same-origin" }).then((r) => r.json() as Promise<AssistantContext>),
    staleTime: 60_000,
  });
  const { data: plan = null } = useQuery({
    queryKey: ["plan", slug],
    queryFn: () => api<PlanData>(`/projects/${slug}/plan/`),
    enabled: !!slug,
    staleTime: 30_000,
  });

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
  }, [open]);

  const doCapture = useCallback(async (text: string) => {
    await api("/quick-capture/", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
      body: JSON.stringify({ text }),
    });
    queryClient.invalidateQueries({ queryKey: ["inbox"] });
    petReact("capture");
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
    petReact("milestone");
    return `✓ ${title}`;
  }, [queryClient, slug]);

  const doToggleTheme = useCallback(async () => {
    (window as unknown as { __toggleTheme?: () => void }).__toggleTheme?.();
    return document.documentElement.classList.contains("dark") ? "Dark mode on" : "Light mode on";
  }, []);

  const doToggleCalm = useCallback(async () => {
    return toggleCalm() ? "Calm mode on — stats hidden" : "Calm mode off";
  }, []);

  // Static verbs the palette can run directly (not navigation). Discoverable by typing
  // "dark"/"theme"/"calm" etc. — surfacing the #273 theme + #274 calm toggles in ⌘K.
  const verbs = useMemo(
    () => [
      { label: "Toggle dark mode", keys: "toggle dark light mode theme appearance color scheme", run: doToggleTheme },
      { label: "Toggle calm mode", keys: "toggle calm mode focus quiet hide stats dashboard", run: doToggleCalm },
    ],
    [doToggleTheme, doToggleCalm],
  );

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
    const verbRows: Row[] = verbs
      .map((v) => ({ v, s: fuzzy(q, v.keys) }))
      .filter((x): x is { v: (typeof verbs)[number]; s: number } => x.s !== null)
      .sort((a, b) => b.s - a.s)
      .map(({ v }) => ({ kind: "verb" as const, label: v.label, tag: "view", run: v.run }));
    const navRows: Row[] = (assistant?.commands ?? [])
      .map((c) => ({ c, s: fuzzy(q, c.title) }))
      .filter((x): x is { c: Command; s: number } => x.s !== null)
      .sort((a, b) => b.s - a.s)
      .slice(0, 8)
      .map(({ c }) => ({ kind: "nav" as const, label: c.title, tag: c.type, url: c.url }));
    return [...verbRows, ...navRows];
  }, [query, assistant, plan, doCapture, verbs]);

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
    <div className="fixed inset-0 z-50 flex items-start justify-center px-4 pt-[12vh]">
      <div className="absolute inset-0 bg-stone-900/40 dark:bg-black/60 backdrop-blur-[2px]" onClick={() => setOpen(false)} aria-hidden="true" />
      <div role="dialog" aria-modal="true" aria-label="Command bar"
           className="relative w-full max-w-xl overflow-hidden rounded-lg border border-stone-200 dark:border-stone-800 bg-white dark:bg-stone-900 shadow-xl ring-1 ring-black/5">
        <div className="flex items-center gap-3 border-b border-stone-100 dark:border-stone-800 px-4">
          <svg viewBox="0 0 24 24" fill="none" aria-hidden="true"
               className="h-4 w-4 shrink-0 text-stone-400 dark:text-stone-500">
            <circle cx="11" cy="11" r="7" stroke="currentColor" strokeWidth="2" />
            <path d="m20 20-3-3" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
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
            className="w-full bg-transparent py-3.5 text-sm text-stone-800 dark:text-stone-100 placeholder:text-stone-400 focus:outline-none"
          />
        </div>
        {flash && (
          <p className="border-b border-stone-100 dark:border-stone-800 bg-green-50 dark:bg-green-500/15 px-4 py-2 text-xs text-green-700 dark:text-green-300">{flash}</p>
        )}

        {rows.length > 0 && (
          <ul role="listbox" className="max-h-72 overflow-y-auto p-1.5">
            {rows.map((row, i) => (
              <li key={`${row.kind}-${row.label}-${i}`}>
                <button
                  type="button"
                  role="option"
                  aria-selected={i === active}
                  onClick={() => runRow(row)}
                  onMouseEnter={() => setActive(i)}
                  className={`flex w-full items-center gap-2.5 rounded-md px-2.5 py-2 text-left text-sm transition-colors ${i === active ? "bg-indigo-50 dark:bg-indigo-500/15" : "dark:hover:bg-stone-800"}`}
                >
                  <span aria-hidden="true" className={`h-1.5 w-1.5 shrink-0 rounded-full ${i === active ? "bg-indigo-500" : "bg-transparent"}`} />
                  <span className={`min-w-0 flex-1 truncate ${i === active ? "text-stone-900 dark:text-stone-100" : "text-stone-700 dark:text-stone-300"}`}>{row.label}</span>
                  <span className={`shrink-0 rounded px-1.5 py-0.5 text-[10px] uppercase tracking-wide ${i === active ? "bg-white dark:bg-stone-900 text-indigo-500 dark:text-indigo-400" : "bg-stone-100 dark:bg-stone-800 text-stone-400 dark:text-stone-300"}`}>
                    {row.tag}
                  </span>
                </button>
              </li>
            ))}
          </ul>
        )}

        {!query && (
          <div className="px-4 py-4">
            {assistant && assistant.actions.length > 0 && (
              <div className="mb-4">
                <p className="mb-2 text-xs uppercase tracking-wide text-stone-400 dark:text-stone-500">Actions</p>
                <div className="flex flex-wrap gap-1.5">
                  {assistant.actions.map((a) => {
                    const { to, spa } = toSpaUrl(a.url);
                    return (
                      <button key={a.url + a.label} type="button"
                              onClick={() => { setOpen(false); spa ? navigate(to) : window.location.assign(a.url); }}
                              className="rounded-full border border-stone-200 dark:border-stone-800 px-2.5 py-1 text-xs text-stone-600 dark:text-stone-300 transition-colors hover:border-indigo-400 hover:text-indigo-700 dark:hover:text-indigo-400">
                        {a.label}
                      </button>
                    );
                  })}
                </div>
              </div>
            )}
            <button type="button" onClick={copyClaudePrompt}
                    className="mb-4 flex w-full items-center gap-2 rounded-md border border-stone-200 dark:border-stone-800 bg-stone-50 dark:bg-stone-900 px-3 py-2.5 text-left text-xs text-stone-600 dark:text-stone-300 transition-colors hover:border-indigo-300 hover:bg-indigo-50/40 dark:hover:bg-indigo-500/10">
              <span aria-hidden="true">✨</span>
              <span>Ask Claude about this — copy a context-rich MCP prompt</span>
            </button>
            {assistant && assistant.recent.length > 0 && (
              <div>
                <p className="mb-1.5 text-xs uppercase tracking-wide text-stone-400 dark:text-stone-500">Recent</p>
                <ul className="-mx-1.5">
                  {assistant.recent.slice(0, 5).map((r) => {
                    const { to, spa } = toSpaUrl(r.url);
                    return (
                      <li key={r.url + r.title}>
                        <button type="button"
                                onClick={() => { setOpen(false); spa ? navigate(to) : window.location.assign(r.url); }}
                                className="flex w-full items-center gap-2.5 rounded-md px-1.5 py-1.5 text-left text-sm transition-colors hover:bg-stone-50 dark:hover:bg-stone-800">
                          <span className="min-w-0 flex-1 truncate text-stone-600 dark:text-stone-300">{r.title}</span>
                          <span className="shrink-0 text-xs text-stone-400 dark:text-stone-400">{r.when}</span>
                          <span className="shrink-0 rounded bg-stone-100 dark:bg-stone-800 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-stone-400 dark:text-stone-300">{r.type}</span>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              </div>
            )}
          </div>
        )}
        <div className="flex items-center gap-3 border-t border-stone-100 dark:border-stone-800 bg-stone-50/60 dark:bg-stone-900 px-4 py-2 text-[10px] text-stone-400 dark:text-stone-500">
          <span className="flex items-center gap-1">
            <kbd className="rounded border border-stone-200 dark:border-stone-800 bg-white dark:bg-stone-900 px-1 font-sans text-stone-500 dark:text-stone-400">↑</kbd>
            <kbd className="rounded border border-stone-200 dark:border-stone-800 bg-white dark:bg-stone-900 px-1 font-sans text-stone-500 dark:text-stone-400">↓</kbd>
            navigate
          </span>
          <span className="flex items-center gap-1">
            <kbd className="rounded border border-stone-200 dark:border-stone-800 bg-white dark:bg-stone-900 px-1 font-sans text-stone-500 dark:text-stone-400">↵</kbd>
            open
          </span>
          <span className="flex items-center gap-1">
            <kbd className="rounded border border-stone-200 dark:border-stone-800 bg-white dark:bg-stone-900 px-1 font-sans text-stone-500 dark:text-stone-400">esc</kbd>
            close
          </span>
          <span className="ml-auto">capture: <i>text</i> · done: <i>milestone</i></span>
        </div>
      </div>
    </div>
  );
}
