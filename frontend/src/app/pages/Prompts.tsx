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
    <article className="rounded border border-stone-200 bg-white">
      <div className="flex items-center gap-3 px-5 py-3">
        <h2 className="font-medium">{prompt.title}</h2>
        {prompt.tags.split(",").map((t) => t.trim()).filter(Boolean).map((t) => (
          <span key={t} className="rounded-full border border-stone-200 px-2 py-0.5 text-xs text-stone-500">{t}</span>
        ))}
        <span className="ml-auto" />
        <button onClick={copy}
                className="rounded border border-stone-300 bg-white px-2 py-1 text-xs text-stone-600 hover:border-stone-400">
          {copied ? "✓ Copied" : "⧉ Copy"}
        </button>
      </div>
      {vars.length > 0 && (
        <div className="border-t border-stone-100 px-5 py-2">
          <p className="mb-1 text-[10px] uppercase tracking-wide text-stone-400">Fill in before copying</p>
          <div className="flex flex-wrap gap-2">
            {vars.map((name) => (
              <label key={name} className="flex items-center gap-1 text-xs text-stone-500">
                {name}
                <input value={values[name] ?? ""} placeholder={name}
                       onChange={(e) => setValues({ ...values, [name]: e.target.value })}
                       className="rounded border border-stone-300 bg-white px-2 py-0.5 text-xs focus:border-indigo-600 focus:outline-none" />
              </label>
            ))}
          </div>
        </div>
      )}
      <details className="border-t border-stone-100 px-5 py-2">
        <summary className="cursor-pointer text-xs text-stone-400 hover:text-stone-600">Show prompt</summary>
        <pre className="mt-2 overflow-x-auto whitespace-pre-wrap rounded bg-stone-50 p-3 font-mono text-xs text-stone-700">{prompt.body}</pre>
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
  const rows = (data?.results ?? []).filter(
    (p) => !needle || p.title.toLowerCase().includes(needle) || p.tags.toLowerCase().includes(needle),
  );

  return (
    <div>
      <h1 className="mb-6 text-2xl font-semibold tracking-tight">Prompt gallery</h1>
      <input type="search" value={query} onChange={(e) => setQuery(e.target.value)}
             placeholder="Search prompts…"
             className="mb-4 w-64 rounded border border-stone-300 bg-white px-3 py-1.5 text-sm focus:border-indigo-600 focus:outline-none" />
      <div className="space-y-3">
        {rows.map((p) => <PromptCard key={p.id} prompt={p} />)}
        {rows.length === 0 && <p className="text-sm text-stone-400">No prompts match.</p>}
      </div>
    </div>
  );
}
