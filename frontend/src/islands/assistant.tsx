/**
 * Atlas Assistant panel ([REV] cycle 55).
 *
 * A calm slide-over summoned with Cmd/Ctrl-K (or the sidebar button): fuzzy
 * command bar over everything in Atlas, page-aware quick actions, an
 * "Ask Claude about this" MCP handoff, and recent activity for the context.
 * Local logic only — no LLM APIs.
 */
import { useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";

type Command = { title: string; type: string; url: string };
type Action = { label: string; url: string; method: string };
type Recent = { title: string; when: string; url: string; type: string };
type Context = {
  context: { page?: string; project?: { name: string; slug: string; url: string } };
  actions: Action[];
  commands: Command[];
  claude_prompt: string;
  recent: Recent[];
};
type Props = { contextUrl: string };

/** Subsequence fuzzy score: higher is better, null means no match. */
function fuzzy(needle: string, haystack: string): number | null {
  const n = needle.toLowerCase();
  const h = haystack.toLowerCase();
  if (!n) return 0;
  let score = 0;
  let hi = 0;
  let streak = 0;
  for (const ch of n) {
    const found = h.indexOf(ch, hi);
    if (found === -1) return null;
    streak = found === hi ? streak + 1 : 1;
    score += streak * 2 + (found === 0 || /\W/.test(h[found - 1] ?? "") ? 3 : 0);
    hi = found + 1;
  }
  return score - h.length * 0.01;
}

function Assistant({ contextUrl }: Props) {
  const [open, setOpen] = useState(false);
  const [data, setData] = useState<Context | null>(null);
  const [query, setQuery] = useState("");
  const [active, setActive] = useState(0);
  const [copied, setCopied] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((v) => !v);
      } else if (e.key === "Escape") {
        setOpen(false);
      }
    }
    document.addEventListener("keydown", onKey);
    const btn = document.getElementById("assistant-summon");
    const onClick = () => setOpen(true);
    btn?.addEventListener("click", onClick);
    return () => {
      document.removeEventListener("keydown", onKey);
      btn?.removeEventListener("click", onClick);
    };
  }, []);

  useEffect(() => {
    if (open && !data) {
      const url = `${contextUrl}?path=${encodeURIComponent(location.pathname)}`;
      fetch(url)
        .then((r) => r.json())
        .then(setData)
        .catch(() => setData(null));
    }
    if (open) setTimeout(() => inputRef.current?.focus(), 50);
    else {
      setQuery("");
      setActive(0);
      setCopied(false);
    }
  }, [open, data, contextUrl]);

  const matches = useMemo(() => {
    if (!data) return [];
    if (!query.trim()) return [];
    return data.commands
      .map((c) => ({ c, s: fuzzy(query, c.title) }))
      .filter((x): x is { c: Command; s: number } => x.s !== null)
      .sort((a, b) => b.s - a.s)
      .slice(0, 8)
      .map((x) => x.c);
  }, [data, query]);

  useEffect(() => setActive(0), [query]);

  function onInputKey(e: React.KeyboardEvent) {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActive((a) => Math.min(a + 1, matches.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActive((a) => Math.max(a - 1, 0));
    } else if (e.key === "Enter" && matches[active]) {
      location.href = matches[active].url;
    }
  }

  async function copyPrompt() {
    if (!data) return;
    try {
      await navigator.clipboard.writeText(data.claude_prompt);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* clipboard unavailable — the textarea below remains selectable */
    }
  }

  if (!open) return null;
  const project = data?.context.project;

  return (
    <div className="fixed inset-0 z-50">
      <div
        className="absolute inset-0 bg-stone-900/30"
        onClick={() => setOpen(false)}
        aria-hidden="true"
      />
      <aside
        role="dialog"
        aria-modal="true"
        aria-label="Atlas assistant"
        className="absolute right-0 top-0 flex h-full w-full max-w-md flex-col border-l border-stone-200 bg-white shadow-2xl"
      >
        <div className="flex items-center gap-2 border-b border-stone-100 px-5 py-4">
          <span className="text-lg" aria-hidden="true">✨</span>
          <div className="min-w-0 flex-1">
            <h2 className="text-sm font-semibold tracking-tight">Assistant</h2>
            <p className="truncate text-xs text-stone-400">
              {project ? project.name : "Everywhere"} · Cmd/Ctrl-K
            </p>
          </div>
          <button
            onClick={() => setOpen(false)}
            aria-label="Close"
            className="rounded px-2 py-1 text-stone-400 hover:bg-stone-100 hover:text-stone-600"
          >
            ✕
          </button>
        </div>

        <div className="border-b border-stone-100 px-5 py-3">
          <input
            ref={inputRef}
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={onInputKey}
            placeholder="Jump to anything…"
            aria-label="Search everything in Atlas"
            className="w-full rounded border border-stone-300 bg-stone-50 px-3 py-2 text-sm focus:border-indigo-600 focus:bg-white focus:outline-none"
          />
          {matches.length > 0 && (
            <ul role="listbox" className="mt-2 overflow-hidden rounded border border-stone-200">
              {matches.map((m, i) => (
                <li key={m.url + m.title}>
                  <a
                    href={m.url}
                    role="option"
                    aria-selected={i === active}
                    className={`flex items-center gap-2 px-3 py-1.5 text-sm hover:bg-stone-50 ${
                      i === active ? "bg-indigo-50" : ""
                    }`}
                  >
                    <span className="rounded bg-stone-100 px-1 py-0.5 text-[10px] uppercase tracking-wide text-stone-400">
                      {m.type}
                    </span>
                    <span className="truncate text-stone-700">{m.title}</span>
                  </a>
                </li>
              ))}
            </ul>
          )}
        </div>

        <div className="flex-1 overflow-y-auto px-5 py-4">
          {!data && <p className="text-sm text-stone-400">Loading context…</p>}

          {data && (
            <>
              <h3 className="mb-2 text-[10px] font-medium uppercase tracking-wide text-stone-400">
                Quick actions
              </h3>
              <div className="mb-5 flex flex-wrap gap-1.5">
                {data.actions.map((a) => (
                  <a
                    key={a.url + a.label}
                    href={a.url}
                    className="rounded-full border border-stone-200 px-2.5 py-1 text-xs text-stone-600 hover:border-indigo-400 hover:text-indigo-700"
                  >
                    {a.label}
                  </a>
                ))}
              </div>

              <h3 className="mb-2 text-[10px] font-medium uppercase tracking-wide text-stone-400">
                Ask Claude about this
              </h3>
              <div className="mb-5 rounded border border-stone-200 bg-stone-50 p-3">
                <p className="mb-2 text-xs text-stone-500">
                  Copies a context-rich prompt for your Claude session (Atlas is registered
                  there as an MCP server — Claude can act on it directly).
                </p>
                <textarea
                  readOnly
                  value={data.claude_prompt}
                  rows={4}
                  className="mb-2 w-full rounded border border-stone-200 bg-white p-2 font-mono text-[11px] text-stone-600"
                />
                <button
                  onClick={copyPrompt}
                  className="rounded bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-700"
                >
                  {copied ? "✓ Copied" : "⧉ Copy prompt"}
                </button>
              </div>

              {data.recent.length > 0 && (
                <>
                  <h3 className="mb-2 text-[10px] font-medium uppercase tracking-wide text-stone-400">
                    Recent here
                  </h3>
                  <ul className="space-y-1.5">
                    {data.recent.map((r) => (
                      <li key={r.url + r.when + r.title}>
                        <a href={r.url} className="group flex items-baseline gap-2 text-sm">
                          <span className="rounded bg-stone-100 px-1 py-0.5 text-[10px] uppercase tracking-wide text-stone-400">
                            {r.type}
                          </span>
                          <span className="min-w-0 flex-1 truncate text-stone-700 group-hover:text-indigo-700">
                            {r.title}
                          </span>
                          <span className="shrink-0 text-xs text-stone-400">{r.when}</span>
                        </a>
                      </li>
                    ))}
                  </ul>
                </>
              )}
            </>
          )}
        </div>
      </aside>
    </div>
  );
}

export default function mount(el: HTMLElement, props: Props) {
  createRoot(el).render(<Assistant {...props} />);
}
