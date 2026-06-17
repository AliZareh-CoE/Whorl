/** Prompt gallery with {{variable}} fill-ins (SPA slice 8). */
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { api } from "../api";

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

function PromptCard({ prompt }: { prompt: Prompt }) {
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
    <article className="group rounded border border-stone-200 bg-white transition-colors hover:border-stone-300">
      <div className="flex items-center gap-3 px-5 py-3.5">
        <h2 className="truncate text-sm font-medium text-stone-900">{prompt.title}</h2>
        {prompt.tags.split(",").map((t) => t.trim()).filter(Boolean).map((t) => (
          <span key={t} className="shrink-0 rounded-full border border-stone-200 px-2 py-0.5 text-xs text-stone-500">{t}</span>
        ))}
        <button onClick={copy}
                className={`ml-auto shrink-0 rounded border px-2.5 py-1 text-xs font-medium transition ${
                  copied
                    ? "border-indigo-200 bg-indigo-50 text-indigo-700"
                    : "border-stone-200 bg-white text-stone-400 hover:border-indigo-300 hover:text-indigo-700 group-hover:text-stone-600"
                }`}>
          {copied ? "✓ Copied" : "⧉ Copy"}
        </button>
      </div>
      {vars.length > 0 && (
        <div className="border-t border-stone-100 px-5 py-3">
          <p className="mb-2 text-[10px] font-medium uppercase tracking-wide text-stone-400">Fill in before copying</p>
          <div className="flex flex-wrap gap-2.5">
            {vars.map((name) => (
              <label key={name} className="flex items-center gap-1.5 text-xs text-stone-500">
                {name}
                <input value={values[name] ?? ""} placeholder={name}
                       onChange={(e) => setValues({ ...values, [name]: e.target.value })}
                       className="w-28 rounded border border-stone-300 bg-white px-2 py-1 text-xs text-stone-700 placeholder:text-stone-400 focus:border-indigo-600 focus:outline-none focus:ring-1 focus:ring-indigo-600" />
              </label>
            ))}
          </div>
        </div>
      )}
      <details className="border-t border-stone-100 px-5 py-3">
        <summary className="cursor-pointer select-none text-xs text-stone-400 transition-colors hover:text-stone-600">Show prompt</summary>
        <pre className="mt-2.5 overflow-x-auto whitespace-pre-wrap rounded border border-stone-100 bg-stone-50 p-3.5 font-mono text-xs leading-relaxed text-stone-700">{prompt.body}</pre>
      </details>
    </article>
  );
}

export default function Prompts() {
  const [query, setQuery] = useState("");
  const { data, isLoading } = useQuery({
    queryKey: ["prompts"],
    queryFn: () => api<Page<Prompt>>("/prompts/"),
  });

  if (isLoading) return <p className="text-sm text-stone-400">Loading prompts…</p>;
  const needle = query.trim().toLowerCase();
  const all = data?.results ?? [];
  const rows = all.filter(
    (p) => !needle || p.title.toLowerCase().includes(needle) || p.tags.toLowerCase().includes(needle),
  );

  return (
    <div>
      <h1 className="mb-1 text-2xl font-semibold tracking-tight">Prompt gallery</h1>
      <p className="mb-6 text-sm text-stone-500">
        {all.length} reusable {all.length === 1 ? "prompt" : "prompts"} with {"{{variable}}"} fill-ins.
      </p>

      <div className="mb-4 flex items-center justify-between gap-3">
        <input type="search" value={query} onChange={(e) => setQuery(e.target.value)}
               placeholder="Search prompts…"
               className="w-72 rounded border border-stone-300 bg-white px-3 py-1.5 text-sm placeholder:text-stone-400 focus:border-indigo-600 focus:outline-none focus:ring-1 focus:ring-indigo-600" />
        <span className="text-xs uppercase tracking-wide text-stone-400">{rows.length} shown</span>
      </div>

      <div className="space-y-3">
        {rows.map((p) => <PromptCard key={p.id} prompt={p} />)}
        {rows.length === 0 && (
          <div className="rounded border border-dashed border-stone-300 bg-white px-4 py-12 text-center">
            <p className="text-sm font-medium text-stone-500">
              {query.trim() ? "No prompts match" : "No saved prompts yet"}
            </p>
            <p className="mx-auto mt-1 max-w-sm text-xs text-stone-400">
              {query.trim()
                ? "Try a different title or tag."
                : "Save a reusable prompt to build your gallery — use {{variable}} placeholders to fill in before copying."}
            </p>
          </div>
        )}
      </div>
    </div>
  );
}
