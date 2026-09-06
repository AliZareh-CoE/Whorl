/** Prompt gallery with {{variable}} fill-ins (SPA slice 8) — and, since the CRUD sweep of
 * 2026-09-06, the place to write, edit and delete prompts too. */
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Pencil, Plus, Trash2 } from "lucide-react";
import { api } from "../api";
import { confirmDialog, errorDialog } from "../../components/Dialog";
import { Kebab, useMenu, type MenuItem } from "../../components/Menu";

type Prompt = { id: number; title: string; body: string; tags: string };
type Page<T> = { count: number; results: T[] };

const VAR_RE = /\{\{\s*([a-zA-Z0-9_ -]{1,40}?)\s*\}\}/g;

function variableNames(body: string): string[] {
  const seen: string[] = [];
  for (const match of body.matchAll(VAR_RE)) {
    const name = match[1].trim();
    if (name && !seen.includes(name)) seen.push(name);
  }
  return seen;
}

function PromptCard({ prompt, items, onContextMenu }: { prompt: Prompt; items: MenuItem[]; onContextMenu: (e: React.MouseEvent) => void }) {
  const vars = variableNames(prompt.body);
  const [values, setValues] = useState<Record<string, string>>({});
  const [copied, setCopied] = useState(false);

  async function copy() {
    let text = prompt.body;
    for (const [name, value] of Object.entries(values)) {
      if (!value.trim()) continue;
      const esc = name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
      text = text.replace(new RegExp(`\\{\\{\\s*${esc}\\s*\\}\\}`, "g"), value.trim());
    }
    await navigator.clipboard.writeText(text);
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
            {vars.map((name) => (
              <label key={name} className="flex items-center gap-1.5 text-xs text-stone-500 dark:text-stone-400">
                {name}
                <input value={values[name] ?? ""} placeholder={name}
                       onChange={(e) => setValues({ ...values, [name]: e.target.value })}
                       className="w-28 rounded border border-stone-300 bg-white px-2 py-1 text-xs text-stone-700 placeholder:text-stone-400 focus:border-indigo-600 focus:outline-none focus:ring-1 focus:ring-indigo-600 dark:border-stone-700 dark:bg-stone-800 dark:text-stone-300" />
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
  const { data, isLoading } = useQuery({
    queryKey: ["prompts"],
    queryFn: () => api<Page<Prompt>>("/prompts/"),
  });
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

  if (isLoading) return <p className="text-sm text-stone-400">Loading prompts…</p>;
  const needle = query.trim().toLowerCase();
  const all = data?.results ?? [];
  const rows = all.filter(
    (p) => !needle || p.title.toLowerCase().includes(needle) || p.tags.toLowerCase().includes(needle),
  );

  return (
    <div>
      <h1 className="mb-1 text-2xl font-semibold tracking-tight">Prompt gallery</h1>
      <p className="mb-6 text-sm text-stone-500 dark:text-stone-300">
        {all.length} reusable {all.length === 1 ? "prompt" : "prompts"} with {"{{variable}}"} fill-ins.
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
          <textarea value={body} onChange={(e) => setBody(e.target.value)} rows={6} placeholder={"The prompt. Use {{variable}} for fill-ins."} aria-label="Prompt body" className={`${field} font-mono text-xs leading-relaxed`} />
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
