/** Prompt gallery with {{variable}} fill-ins (SPA slice 8) — and, since the CRUD sweep of
 * 2026-09-06, the place to write, edit and delete prompts too. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { api } from "../api";
import { confirmDialog, errorDialog } from "../../components/Dialog";
import { Kebab, useMenu, type MenuItem } from "../../components/Menu";
import { queryGate } from "../../components/QueryBoundary";

type Prompt = { id: number; title: string; body: string; tags: string };
type Page<T> = { count: number; results: T[] };

// {{name}} or {{name|default}} (#393): the default fills in unless the user types a value;
// {{name:kind}} (#562): the fill-in is picked from Atlas — a paper in the library, a note, a
// project, a manuscript — and expands to that row at copy time (the server renders it)
const VAR_RE = /\{\{\s*([a-zA-Z0-9_ -]{1,40}?)\s*(?::\s*([a-zA-Z]{1,20})\s*)?(?:\|([^}]{0,200}?))?\s*\}\}/g;
const KINDS = ["reference", "note", "project", "manuscript"] as const;
type Kind = "text" | (typeof KINDS)[number];
type Variable = { name: string; kind: Kind; default: string };
// a typed value: the picked row's id + the label the chip shows; a text value: what was typed
type Value = { text?: string; id?: number; label?: string };
const STORE = "atlas-prompt-values:";
function loadValues(id: number): Record<string, Value> {
  try {
    const raw = JSON.parse(localStorage.getItem(STORE + id) || "{}") as Record<string, string | Value>;
    // #393 stored bare strings; they read back as text values
    return Object.fromEntries(Object.entries(raw).map(([k, v]) => [k, typeof v === "string" ? { text: v } : v]));
  } catch { return {}; }
}
function saveValues(id: number, values: Record<string, Value>) {
  try { localStorage.setItem(STORE + id, JSON.stringify(values)); } catch { /* private mode */ }
}

function variables(body: string): Variable[] {
  const seen: Variable[] = [];
  for (const match of body.matchAll(VAR_RE)) {
    const name = match[1].trim();
    const rawKind = (match[2] ?? "").trim().toLowerCase();
    const kind: Kind = (KINDS as readonly string[]).includes(rawKind) ? (rawKind as Kind) : "text";
    const def = (match[3] ?? "").trim();
    if (!name) continue;
    const existing = seen.find((v) => v.name === name);
    if (!existing) seen.push({ name, kind, default: def });
    else {
      if (def && !existing.default) existing.default = def;
      if (kind !== "text" && existing.kind === "text") existing.kind = kind;
    }
  }
  return seen;
}

const KIND_LABEL: Record<Kind, string> = { text: "", reference: "a paper", note: "a note", project: "a project", manuscript: "a manuscript" };
type Hit = { type: string; id: number; label: string; meta?: string; project_name?: string | null };

/** #562: a combobox over global search, narrowed to one kind — pick a paper / note / project /
 * manuscript for a typed fill-in; the chosen row becomes a chip with its title. */
function Picker({ variable, value, onPick }: { variable: Variable; value: Value | undefined; onPick: (v: Value | undefined) => void }) {
  const [q, setQ] = useState("");
  const [hits, setHits] = useState<Hit[]>([]);
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState(0);
  useEffect(() => {
    const needle = q.trim();
    if (needle.length < 2) { setHits([]); return; }
    const t = setTimeout(() => {
      api<{ results: Hit[] }>(`/search/?q=${encodeURIComponent(needle)}`)
        .then((r) => { setHits(r.results.filter((h) => h.type === variable.kind).slice(0, 8)); setActive(0); setOpen(true); })
        .catch(() => setHits([]));
    }, 180);
    return () => clearTimeout(t);
  }, [q, variable.kind]);
  if (value?.id != null) {
    return (
      <span className="inline-flex max-w-xs items-center gap-1 rounded-full border border-indigo-200 bg-indigo-50 py-0.5 pl-2 pr-1 text-xs text-indigo-700 dark:border-indigo-500/40 dark:bg-indigo-500/15 dark:text-indigo-300" data-testid="prompt-picked" title={value.label}>
        <span className="truncate">{value.label}</span>
        <button type="button" onClick={() => onPick(undefined)} aria-label={`Clear ${variable.name}`} className="rounded-full px-1 text-indigo-400 hover:text-red-600">×</button>
      </span>
    );
  }
  const pick = (h: Hit) => { onPick({ id: h.id, label: h.label.replace(/^[^:]+: /, "") }); setQ(""); setHits([]); setOpen(false); };
  return (
    <span className="relative">
      <input value={q} onChange={(e) => setQ(e.target.value)} onFocus={() => hits.length && setOpen(true)} onBlur={() => setTimeout(() => setOpen(false), 150)}
             onKeyDown={(e) => { if (!open || !hits.length) return; if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => (a + 1) % hits.length); } else if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => (a - 1 + hits.length) % hits.length); } else if (e.key === "Enter") { e.preventDefault(); pick(hits[active]); } else if (e.key === "Escape") setOpen(false); }}
             placeholder={`pick ${KIND_LABEL[variable.kind]}…`} title={`Type to search for ${KIND_LABEL[variable.kind]}`} data-testid="prompt-pick" role="combobox" aria-expanded={open} aria-autocomplete="list"
             className="w-44 rounded border border-stone-300 bg-white px-2 py-1 text-xs text-stone-700 placeholder:text-stone-400 focus:border-indigo-600 focus:outline-none focus:ring-1 focus:ring-indigo-600 dark:border-stone-700 dark:bg-stone-800 dark:text-stone-300" />
      {open && hits.length > 0 && (
        <ul role="listbox" className="absolute left-0 top-full z-20 mt-1 max-h-64 w-80 overflow-y-auto rounded-md border border-stone-200 bg-white py-1 shadow-lg dark:border-stone-700 dark:bg-stone-900" data-testid="prompt-hits">
          {hits.map((h, i) => (
            <li key={`${h.type}-${h.id}`} role="option" aria-selected={i === active} onMouseDown={(e) => { e.preventDefault(); pick(h); }} onMouseEnter={() => setActive(i)}
                className={`cursor-pointer px-3 py-1.5 text-xs ${i === active ? "bg-indigo-50 dark:bg-indigo-500/15" : ""}`}>
              <div className="truncate text-stone-800 dark:text-stone-100">{h.label.replace(/^[^:]+: /, "")}</div>
              {(h.meta || h.project_name) && <div className="truncate text-[11px] text-stone-400">{[h.meta, h.project_name].filter(Boolean).join(" · ")}</div>}
            </li>
          ))}
        </ul>
      )}
    </span>
  );
}

function PromptCard({ prompt, items, onContextMenu }: { prompt: Prompt; items: MenuItem[]; onContextMenu: (e: React.MouseEvent) => void }) {
  const vars = variables(prompt.body);
  const [values, setValues] = useState<Record<string, Value>>(() => loadValues(prompt.id)); // last-used values, per prompt (#393)
  const [copied, setCopied] = useState(false);

  async function copy() {
    // #562: the server renders — a picked row expands to its title / authors / abstract, a
    // typed value is used as typed, else the {{name|default}}, else the placeholder stays
    saveValues(prompt.id, values);
    const payload: Record<string, string | number> = {};
    for (const v of vars) {
      const val = values[v.name];
      if (val?.id != null) payload[v.name] = val.id;
      else if (val?.text?.trim()) payload[v.name] = val.text.trim();
    }
    let text: string;
    try {
      text = (await api<{ text: string }>(`/prompts/${prompt.id}/render/`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ values: payload }) })).text;
    } catch (e) { void errorDialog("Couldn't fill in the prompt", e); return; }
    try { await navigator.clipboard.writeText(text); } catch { void errorDialog("Couldn't copy", new Error("The clipboard is not available here.")); return; }
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  }

  return (
    <article className="group rounded border border-stone-200 bg-white transition-colors hover:border-stone-300 dark:border-stone-800 dark:bg-stone-900" onContextMenu={onContextMenu} data-testid="prompt-card">
      <div className="flex items-center gap-3 px-5 py-3.5">
        <h2 className="truncate text-sm font-medium text-stone-900 dark:text-stone-100">{prompt.title}</h2>
        {prompt.tags.split(",").map((t) => t.trim()).filter(Boolean).map((t) => (
          <span key={t} className="shrink-0 rounded-full border border-stone-200 px-2 py-0.5 text-xs text-stone-500 dark:border-stone-700 dark:text-stone-400">{t}</span>
        ))}
        <button onClick={copy}
                className={`ml-auto shrink-0 rounded border px-2.5 py-1 text-xs font-medium transition ${
                  copied
                    ? "border-indigo-200 bg-indigo-50 text-indigo-700 dark:border-indigo-500/30 dark:bg-indigo-500/10 dark:text-indigo-300"
                    : "border-stone-200 bg-white text-stone-400 hover:border-indigo-300 hover:text-indigo-700 group-hover:text-stone-600 dark:border-stone-700 dark:bg-stone-800 dark:hover:text-indigo-300 dark:group-hover:text-stone-300"
                }`}>
          {copied ? "✓ Copied" : "⧉ Copy"}
        </button>
        <Kebab items={items} label={`Actions for ${prompt.title}`} />
      </div>
      {vars.length > 0 && (
        <div className="border-t border-stone-100 px-5 py-3 dark:border-stone-800">
          <p className="mb-2 text-[10px] font-medium uppercase tracking-wide text-stone-400">Fill in before copying</p>
          <div className="flex flex-wrap gap-2.5">
            {vars.map((v) => (
              <label key={v.name} className="flex items-center gap-1.5 text-xs text-stone-500 dark:text-stone-400">
                {v.name}
                {v.kind === "text" ? (
                  <input value={values[v.name]?.text ?? ""} placeholder={v.default || v.name} title={v.default ? `Default: ${v.default}` : undefined} data-testid="prompt-var"
                         onChange={(e) => setValues({ ...values, [v.name]: { text: e.target.value } })}
                         className="w-28 rounded border border-stone-300 bg-white px-2 py-1 text-xs text-stone-700 placeholder:text-stone-400 focus:border-indigo-600 focus:outline-none focus:ring-1 focus:ring-indigo-600 dark:border-stone-700 dark:bg-stone-800 dark:text-stone-300" />
                ) : (
                  <Picker variable={v} value={values[v.name]} onPick={(val) => setValues((cur) => { const next = { ...cur }; if (val) next[v.name] = val; else delete next[v.name]; return next; })} />
                )}
              </label>
            ))}
          </div>
        </div>
      )}
      <details className="border-t border-stone-100 px-5 py-3 dark:border-stone-800">
        <summary className="cursor-pointer select-none text-xs text-stone-400 transition-colors hover:text-stone-600 dark:hover:text-stone-300">Show prompt</summary>
        <pre className="mt-2.5 overflow-x-auto whitespace-pre-wrap rounded border border-stone-100 bg-stone-50 p-3.5 font-mono text-xs leading-relaxed text-stone-700 dark:border-stone-800 dark:bg-stone-800 dark:text-stone-300">{prompt.body}</pre>
      </details>
    </article>
  );
}

const field = "w-full rounded border border-stone-300 bg-white px-3 py-1.5 text-sm text-stone-800 placeholder:text-stone-400 focus:border-indigo-600 focus:outline-none focus:ring-1 focus:ring-indigo-600 dark:border-stone-700 dark:bg-stone-800 dark:text-stone-100";

export default function Prompts() {
  const [query, setQuery] = useState("");
  const promptsQuery = useQuery({
    queryKey: ["prompts"],
    queryFn: () => api<Page<Prompt>>("/prompts/"),
  });
  const data = promptsQuery.data;
  const queryClient = useQueryClient();
  const menu = useMenu();
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<Prompt | null>(null);
  const [title, setTitle] = useState(""); const [tags, setTags] = useState(""); const [body, setBody] = useState("");
  const reset = () => { setFormOpen(false); setEditing(null); setTitle(""); setTags(""); setBody(""); };
  const startEdit = (p: Prompt) => { setEditing(p); setTitle(p.title); setTags(p.tags); setBody(p.body); setFormOpen(true); window.scrollTo({ top: 0, behavior: "smooth" }); };
  const refresh = () => queryClient.invalidateQueries({ queryKey: ["prompts"] });
  const save = useMutation({
    mutationFn: () => api(editing ? `/prompts/${editing.id}/` : "/prompts/", { method: editing ? "PATCH" : "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ title: title.trim(), tags: tags.trim(), body }) }),
    onSuccess: () => { reset(); refresh(); },
    onError: (e) => void errorDialog("Couldn't save the prompt", e),
  });
  const remove = useMutation({ mutationFn: (id: number) => api(`/prompts/${id}/`, { method: "DELETE" }), onSuccess: () => { if (editing) reset(); refresh(); }, onError: (e) => void errorDialog("Couldn't delete the prompt", e) });
  const itemsFor = (p: Prompt): MenuItem[] => [
    { label: "Edit…", icon: <Pencil className="h-3.5 w-3.5" />, onSelect: () => startEdit(p) },
    { label: "Delete…", icon: <Trash2 className="h-3.5 w-3.5" />, danger: true, onSelect: async () => { if (await confirmDialog({ title: `Delete “${p.title}”?`, danger: true, confirmLabel: "Delete prompt" })) remove.mutate(p.id); } },
  ];

  const gate = queryGate(promptsQuery, { message: "Couldn't load the prompts.", skeleton: <p className="text-sm text-stone-400">Loading prompts…</p> });
  if (gate) return gate;
  const needle = query.trim().toLowerCase();
  const all = data?.results ?? [];
  const rows = all.filter(
    (p) => !needle || p.title.toLowerCase().includes(needle) || p.tags.toLowerCase().includes(needle),
  );

  return (
    <div>
      <h1 className="mb-1 text-2xl font-semibold tracking-tight">Prompt gallery</h1>
      <p className="mb-6 text-sm text-stone-500 dark:text-stone-300">
        {all.length} reusable {all.length === 1 ? "prompt" : "prompts"} with {"{{variable}}"} fill-ins — a {"{{paper:reference}}"} is picked from your library and copied with its title and abstract.
      </p>

      <div className="mb-4 flex items-center justify-between gap-3">
        <input type="search" value={query} onChange={(e) => setQuery(e.target.value)}
               placeholder="Search prompts…"
               className="w-72 rounded border border-stone-300 bg-white px-3 py-1.5 text-sm placeholder:text-stone-400 focus:border-indigo-600 focus:outline-none focus:ring-1 focus:ring-indigo-600 dark:border-stone-700 dark:bg-stone-800 dark:text-stone-100" />
        <span className="flex items-center gap-3 text-xs uppercase tracking-wide text-stone-400">{rows.length} shown
          <button type="button" onClick={() => (formOpen ? reset() : setFormOpen(true))} className="inline-flex items-center gap-1 rounded bg-indigo-600 px-3 py-1.5 text-sm font-medium normal-case tracking-normal text-white hover:bg-indigo-700" data-testid="new-prompt">{formOpen ? "Cancel" : <><Plus className="h-4 w-4" aria-hidden="true" />New prompt</>}</button>
        </span>
      </div>
      {formOpen && (
        <form onSubmit={(e) => { e.preventDefault(); if (title.trim() && body.trim()) save.mutate(); }} className="mb-5 space-y-3 rounded border border-stone-200 bg-white p-5 dark:border-stone-800 dark:bg-stone-900" data-testid="prompt-form">
          <div className="grid gap-3 sm:grid-cols-[minmax(0,1fr)_16rem]">
            <input value={title} onChange={(e) => setTitle(e.target.value)} placeholder="Title" aria-label="Prompt title" className={field} autoFocus />
            <input value={tags} onChange={(e) => setTags(e.target.value)} placeholder="tags, comma separated" aria-label="Prompt tags" className={field} />
          </div>
          <textarea value={body} onChange={(e) => setBody(e.target.value)} rows={6} placeholder={"The prompt. Use {{variable}} for fill-ins, {{venue|NeurIPS}} for a default, {{paper:reference}} / {{note:note}} / {{project:project}} / {{draft:manuscript}} to pick from Atlas."} aria-label="Prompt body" className={`${field} font-mono text-xs leading-relaxed`} />
          <div className="flex items-center gap-3">
            <button type="submit" disabled={save.isPending || !title.trim() || !body.trim()} className="rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50">{save.isPending ? "Saving…" : editing ? "Save changes" : "Save prompt"}</button>
            {editing && <span className="text-xs text-stone-400">editing “{editing.title}”</span>}
          </div>
        </form>
      )}

      <div className="space-y-3">
        {rows.map((p) => <PromptCard key={p.id} prompt={p} items={itemsFor(p)} onContextMenu={(e) => menu.open(e, itemsFor(p))} />)}
        {rows.length === 0 && (
          <div className="rounded border border-dashed border-stone-300 bg-white px-4 py-12 text-center dark:border-stone-700 dark:bg-stone-900">
            <p className="text-sm font-medium text-stone-500 dark:text-stone-300">
              {query.trim() ? "No prompts match" : "No saved prompts yet"}
            </p>
            <p className="mx-auto mt-1 max-w-sm text-xs text-stone-400">
              {query.trim()
                ? "Try a different title or tag."
                : "Save a reusable prompt to build your gallery — use {{variable}} placeholders to fill in before copying."}
            </p>
            {!query.trim() && !formOpen && <button type="button" onClick={() => setFormOpen(true)} className="mt-4 rounded bg-indigo-600 px-3 py-1.5 text-sm font-medium text-white hover:bg-indigo-700">Write the first prompt</button>}
          </div>
        )}
      </div>
      {menu.element}
    </div>
  );
}
