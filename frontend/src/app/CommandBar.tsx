/**
 * The Atlas command bar ([REV] cycle 65). Cmd/Ctrl-K anywhere in the SPA:
 * fuzzy jump-to-anything, real verbs (capture:, done:), page-aware quick
 * actions, and the "Ask Claude about this" MCP handoff. Local + instant.
 */
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { api, csrfToken, petReact } from "./api";
import { parseDue } from "./dueTime";
import { toggleCalm } from "./calm";
import { toSpaUrl } from "./links";
import { isDesktop, openDevtools } from "./external";
import { showShortcuts } from "./shortcuts";

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
// Recent jumps (backlog #284): the last places the palette navigated to, per browser
type Jump = { label: string; url: string; tag: string };
const JUMPS_KEY = "atlas-recent-jumps";
function readJumps(): Jump[] { try { return JSON.parse(localStorage.getItem(JUMPS_KEY) || "[]") as Jump[]; } catch { return []; } }
function pushJump(j: Jump) { try { const next = [j, ...readJumps().filter((x) => x.url !== j.url)].slice(0, 6); localStorage.setItem(JUMPS_KEY, JSON.stringify(next)); } catch { /* storage blocked */ } }
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

// Section headers so verbs read as actions, not destinations (#279).
const groupLabel: Record<Row["kind"], string> = {
  verb: "Commands",
  nav: "Go to",
  milestone: "Complete",
};

export default function CommandBar() {
  const [open, setOpen] = useState(false);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const [flash, setFlash] = useState("");
  const [jumps, setJumps] = useState<Jump[]>([]);
  useEffect(() => { if (open) setJumps(readJumps()); }, [open]);
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
    enabled: !!slug && slug !== "new",
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

  // backlog #300: "todo: buy the cheaper eye-tracker" → the Today list, scoped to the project you are in
  const doTodo = useCallback(async (raw: string) => {
    const { text, due_at } = parseDue(raw); // #431: "todo: call Sam at 3pm" carries the time
    await api("/todos/", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
      body: JSON.stringify({ text, due_at, project: slug ?? null }),
    });
    queryClient.invalidateQueries({ queryKey: ["todos"] });
    queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    return `On your list: ${text.slice(0, 60)}`;
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
  // backlog #279 (2026-09-07, #391): the safe, repeatable actions — nothing here destroys anything.
  const copyBib = useCallback(async (scope: "project" | "library") => {
    const url = scope === "project" && slug ? `/api/v1/references/export/?project=${slug}` : "/api/v1/references/export/";
    const response = await fetch(url, { credentials: "same-origin" });
    if (!response.ok) throw new Error(`${response.status} exporting the bibliography`);
    const text = await response.text();
    const entries = (text.match(/^@\w+\{/gm) ?? []).length;
    try { await navigator.clipboard.writeText(text); } catch { throw new Error("The clipboard refused the text — export from the Library instead."); }
    return `Copied ${entries} BibTeX entr${entries === 1 ? "y" : "ies"}${scope === "project" && slug ? ` for ${slug}` : ""}`;
  }, [slug]);
  // #432: creation verbs — "paper: <doi|arxiv>" adds to the library (and to the project you are
  // in); a bare DOI or arXiv id typed into the bar does the same without the prefix.
  const doPaper = useCallback(async (id: string) => {
    const r = await api<{ id: number; title: string }>("/references/by-doi/", {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
      body: JSON.stringify(slug ? { doi: id, project: slug } : { doi: id }),
    });
    queryClient.invalidateQueries({ queryKey: ["references"] });
    queryClient.invalidateQueries({ queryKey: ["library"] });
    queryClient.invalidateQueries({ queryKey: ["dashboard"] });
    return `Added: ${r.title.slice(0, 70)}${slug ? ` · ${slug}` : ""}`;
  }, [queryClient, slug]);
  const verbs = useMemo(
    () => [
      { label: "Add a paper by DOI or arXiv id", keys: "add paper reference doi arxiv import new library pdf", run: async () => { navigate("/library?add=1"); return "Library — paste the DOI or arXiv id"; } },
      { label: slug ? "New note in this project" : "New note", keys: "new note write jot thought", run: async () => { navigate(slug ? `/projects/${slug}/notes/new` : "/projects"); return slug ? "A fresh note" : "Pick the project first"; } },
      { label: "New manuscript", keys: "new manuscript draft paper write start writing", run: async () => { navigate("/writing?new=1"); return "Writing — give it a working title"; } },
      { label: "New project", keys: "new project create start", run: async () => { navigate("/projects/new"); return "A new project"; } },
      { label: "Import a folder of projects", keys: "import folder projects bulk migrate old", run: async () => { navigate("/projects/import"); return "Import projects from a folder"; } },
      { label: "Toggle dark mode", keys: "toggle dark light mode theme appearance color scheme", run: doToggleTheme },
      { label: "Toggle calm mode", keys: "toggle calm mode focus quiet hide stats dashboard", run: doToggleCalm },
      ...(slug ? [{ label: "Copy this project's .bib", keys: "copy bib bibtex bibliography project export cite", run: () => copyBib("project") }] : []),
      ...(slug ? [{ label: "Export this project as a Markdown vault", keys: "export project markdown vault zip obsidian notes decisions plan bib", run: async () => { window.location.assign(`/api/v1/projects/${slug}/vault/`); return "Vault download started"; } }] : []),
      { label: slug ? "Copy the whole library as .bib" : "Copy the library as .bib", keys: "copy library bib bibtex bibliography export all", run: () => copyBib("library") },
      { label: "Go to this week's review", keys: "go to weekly review week reflect", run: async () => { navigate("/review"); return "This week's review"; } },
      { label: "New quick capture", keys: "new quick capture inbox note idea jot", run: async () => { navigate("/inbox"); return "Inbox — type the thought"; } },
      { label: "Warm up the LaTeX engine", keys: "warm up latex tex engine bundle prefetch tectonic", run: async () => { await api("/diagnostics/warm-latex/", { method: "POST" }); return "Warming up the TeX bundle in the background"; } },
      { label: "Keyboard shortcuts", keys: "keyboard shortcuts keys help cheat sheet hotkeys", run: async () => { void showShortcuts(); return "Shortcuts"; } },
      { label: "Download a backup", keys: "download backup zip export everything", run: async () => { window.location.assign("/api/v1/backup.zip"); return "Backup download started"; } },
      ...(isDesktop() ? [{ label: "Open the web inspector", keys: "open web inspector devtools console debug f12", run: async () => { await openDevtools(); return "Inspector opened"; } }] : []),
    ],
    [doToggleTheme, doToggleCalm, copyBib, slug, navigate],
  );

  const rows: Row[] = useMemo(() => {
    const q = query.trim();
    if (q.toLowerCase().startsWith("capture:") || q.toLowerCase().startsWith("c:")) {
      const text = q.slice(q.indexOf(":") + 1).trim();
      return text
        ? [{ kind: "verb", label: `Capture “${text}”`, tag: "inbox", run: () => doCapture(text) }]
        : [];
    }
    const paperId = (() => {
      const low = q.toLowerCase();
      const body = low.startsWith("paper:") || low.startsWith("doi:") || low.startsWith("p:") ? q.slice(q.indexOf(":") + 1).trim() : q;
      return /^(?:https?:\/\/(?:dx\.)?doi\.org\/)?(10\.\d{4,9}\/\S+)$/i.exec(body)?.[1] ?? /^(?:arxiv:)?(\d{4}\.\d{4,5}(?:v\d+)?)$/i.exec(body)?.[1] ?? (low.startsWith("paper:") || low.startsWith("doi:") ? body : null);
    })();
    if (paperId !== null) {
      return paperId
        ? [{ kind: "verb", label: `Add paper ${paperId} to the library${slug ? ` · ${slug}` : ""}`, tag: "paper", run: () => doPaper(paperId) }]
        : [];
    }
    if (q.toLowerCase().startsWith("todo:") || q.toLowerCase().startsWith("t:")) {
      const text = q.slice(q.indexOf(":") + 1).trim();
      return text
        ? [{ kind: "verb", label: `Add “${text}” to Today${slug ? ` · ${slug}` : ""}`, tag: "today", run: () => doTodo(text) }]
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
  }, [query, assistant, plan, doCapture, doTodo, doPaper, verbs, slug]);

  useEffect(() => setActive(0), [query]);

  async function runRow(row: Row) {
    if (row.kind === "nav") {
      const { to, spa } = toSpaUrl(row.url);
      pushJump({ label: row.label, url: row.url, tag: row.tag });
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
      <div className="absolute inset-0 bg-stone-900/40 backdrop-blur-[3px] dark:bg-[#05070f]/70" onClick={() => setOpen(false)} aria-hidden="true" />
      <div role="dialog" aria-modal="true" aria-label="Command bar"
           className="hairline-gradient glow-accent rise relative w-full max-w-2xl overflow-hidden rounded-2xl border border-stone-200 bg-white shadow-2xl dark:border-transparent dark:bg-stone-900">
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
            placeholder="Jump anywhere — or  capture: idea   todo: task   paper: DOI   done: milestone"
            aria-label="Command"
            className="w-full bg-transparent py-4 text-base text-stone-800 placeholder:text-stone-400 focus:outline-none dark:text-stone-100"
          />
        </div>
        {flash && (
          <p className="border-b border-stone-100 dark:border-stone-800 bg-green-50 dark:bg-green-500/15 px-4 py-2 text-xs text-green-700 dark:text-green-300">{flash}</p>
        )}

        {rows.length === 0 && query.trim() && !flash && (
          <p className="px-4 py-3 text-xs text-stone-400 dark:text-stone-500" data-testid="palette-empty">
            Nothing matches. Try a page name, or <i>capture:</i> a thought, <i>todo:</i> a task, <i>paper:</i> a DOI, <i>done:</i> a milestone.
          </p>
        )}
        {rows.length > 0 && (
          <ul role="listbox" className="max-h-72 overflow-y-auto p-1.5">
            {rows.map((row, i) => (
              <li key={`${row.kind}-${row.label}-${i}`}>
                {(i === 0 || rows[i - 1].kind !== row.kind) && groupLabel[row.kind] && (
                  <p role="presentation" className="px-2.5 pb-1 pt-2 text-[10px] font-medium uppercase tracking-wide text-stone-400 dark:text-stone-500">
                    {groupLabel[row.kind]}
                  </p>
                )}
                <button
                  type="button"
                  role="option"
                  aria-selected={i === active}
                  onClick={() => runRow(row)}
                  onMouseEnter={() => setActive(i)}
                  className={`flex w-full items-center gap-2.5 rounded-lg px-2.5 py-2 text-left text-sm transition-colors ${i === active ? "bg-indigo-50 dark:bg-indigo-500/20 dark:shadow-[inset_0_0_0_1px_rgba(139,124,255,0.35)]" : "dark:hover:bg-stone-800"}`}
                >
                  <span aria-hidden="true" className={`h-1.5 w-1.5 shrink-0 rounded-full ${i === active ? "bg-indigo-500 shadow-[0_0_8px_rgba(139,124,255,0.9)]" : "bg-transparent"}`} />
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
            {jumps.length > 0 && (
              <div className="mb-4" data-testid="recent-jumps">
                <p className="mb-1.5 text-xs uppercase tracking-wide text-stone-400 dark:text-stone-500">Recent jumps</p>
                <ul className="-mx-1.5">
                  {jumps.map((j) => {
                    const { to, spa } = toSpaUrl(j.url);
                    return (
                      <li key={j.url}>
                        <button type="button" onClick={() => { pushJump(j); setOpen(false); spa ? navigate(to) : window.location.assign(j.url); }}
                                className="flex w-full items-center gap-2.5 rounded-md px-1.5 py-1.5 text-left text-sm transition-colors hover:bg-stone-50 dark:hover:bg-stone-800">
                          <span className="min-w-0 flex-1 truncate text-stone-600 dark:text-stone-300">{j.label}</span>
                          <span className="shrink-0 rounded bg-stone-100 dark:bg-stone-800 px-1.5 py-0.5 text-[10px] uppercase tracking-wide text-stone-400 dark:text-stone-300">{j.tag}</span>
                        </button>
                      </li>
                    );
                  })}
                </ul>
              </div>
            )}
            {assistant && assistant.recent.length > 0 && (
              <div>
                <p className="mb-1.5 text-xs uppercase tracking-wide text-stone-400 dark:text-stone-500">Recently edited</p>
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
          <span className="ml-auto">capture: <i>text</i> · todo: <i>task</i> · paper: <i>DOI</i> · done: <i>milestone</i></span>
        </div>
      </div>
    </div>
  );
}
