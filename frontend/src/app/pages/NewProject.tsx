/** Create a project — in the SPA, where ⌘K sends you (owner feedback, cycle 69). */
import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";

type Template = { key: string; name: string; description: string; folders: string[] };

const inputClass =
  "w-full rounded border border-stone-300 bg-white px-3 py-2 text-sm text-stone-800 placeholder:text-stone-400 focus:border-indigo-600 focus:outline-none focus:ring-1 focus:ring-indigo-600 dark:border-stone-700 dark:bg-stone-800 dark:text-stone-100";

const labelClass = "mb-1.5 block text-xs font-medium uppercase tracking-wide text-stone-400";

const swatches = ["#4f46e5", "#0891b2", "#059669", "#d97706", "#dc2626", "#db2777", "#7c3aed", "#475569"];

export default function NewProject() {
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [color, setColor] = useState("#4f46e5");
  const [template, setTemplate] = useState("");
  const [error, setError] = useState("");

  const { data: templates } = useQuery({
    queryKey: ["project-templates"],
    queryFn: () => api<Template[]>("/projects/templates/"),
  });

  const create = useMutation({
    mutationFn: () =>
      api<{ slug: string }>("/projects/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, description, color, status: "active", template }),
      }),
    onSuccess: (p) => navigate(`/projects/${p.slug}`),
    onError: (e) => setError(String(e.message ?? e)),
  });

  return (
    <div className="mx-auto max-w-2xl">
      <nav className="mb-6 text-sm text-stone-500 dark:text-stone-400">
        <Link to="/projects" className="hover:text-indigo-700 hover:underline dark:hover:text-indigo-300">Projects</Link>{" "}
        / <span className="text-stone-700 dark:text-stone-300">New</span>
      </nav>

      <h1 className="text-2xl font-semibold tracking-tight text-stone-900 dark:text-stone-100">New project</h1>
      <p className="mb-8 text-sm text-stone-500 dark:text-stone-400">
        Give it a name and an optional starting scaffold. Everything else can be filled in later.
      </p>

      <form
        className="space-y-7"
        onSubmit={(e) => { e.preventDefault(); if (name.trim()) create.mutate(); }}
      >
        <div>
          <label htmlFor="np-name" className={labelClass}>Name</label>
          <input
            id="np-name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            autoFocus
            placeholder="e.g. Protein folding survey"
            className={inputClass}
          />
        </div>

        <div>
          <label htmlFor="np-desc" className={labelClass}>
            Description <span className="font-normal normal-case text-stone-300">— optional</span>
          </label>
          <textarea
            id="np-desc"
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            rows={4}
            placeholder="What is this research about? (markdown ok)"
            className={inputClass}
          />
        </div>

        <div>
          <label className={labelClass}>Accent color</label>
          <div className="flex items-center gap-2">
            {swatches.map((c) => (
              <button
                key={c}
                type="button"
                onClick={() => setColor(c)}
                aria-label={`Use accent color ${c}`}
                aria-pressed={color === c}
                style={{ backgroundColor: c }}
                className={
                  "h-7 w-7 rounded-full transition-transform hover:scale-110 focus:outline-none " +
                  (color === c
                    ? "ring-2 ring-stone-900 ring-offset-2 ring-offset-stone-50"
                    : "ring-1 ring-stone-200")
                }
              />
            ))}
            <label
              htmlFor="np-color"
              className="relative ml-1 inline-flex h-7 w-7 cursor-pointer items-center justify-center rounded-full border border-dashed border-stone-300 text-stone-400 hover:border-stone-400 hover:text-stone-500 dark:border-stone-700 dark:hover:border-stone-600"
              title="Custom color"
            >
              <span aria-hidden="true" className="text-base leading-none">+</span>
              <input
                id="np-color"
                type="color"
                value={color}
                onChange={(e) => setColor(e.target.value)}
                className="absolute inset-0 cursor-pointer opacity-0"
              />
            </label>
            <span className="ml-2 font-mono text-xs text-stone-400">{color}</span>
          </div>
        </div>

        <div>
          <label className={labelClass}>
            Scaffold <span className="font-normal normal-case text-stone-300">— optional</span>
          </label>
          <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            <button
              type="button"
              onClick={() => setTemplate("")}
              aria-pressed={template === ""}
              className={
                "rounded border p-3 text-left transition-colors " +
                (template === ""
                  ? "border-indigo-600 bg-indigo-50/40 ring-1 ring-indigo-600 dark:border-indigo-500 dark:bg-indigo-500/15 dark:ring-indigo-500"
                  : "border-stone-300 bg-white hover:border-stone-400 dark:border-stone-700 dark:bg-stone-800 dark:hover:border-stone-600")
              }
            >
              <span className="block text-sm font-medium text-stone-800 dark:text-stone-100">Empty project</span>
              <span className="mt-0.5 block text-xs text-stone-400">Start from a blank slate.</span>
            </button>
            {(templates ?? []).map((t) => {
              const selected = template === t.key;
              return (
                <button
                  key={t.key}
                  type="button"
                  onClick={() => setTemplate(t.key)}
                  aria-pressed={selected}
                  className={
                    "rounded border p-3 text-left transition-colors " +
                    (selected
                      ? "border-indigo-600 bg-indigo-50/40 ring-1 ring-indigo-600 dark:border-indigo-500 dark:bg-indigo-500/15 dark:ring-indigo-500"
                      : "border-stone-300 bg-white hover:border-stone-400 dark:border-stone-700 dark:bg-stone-800 dark:hover:border-stone-600")
                  }
                >
                  <span className="block text-sm font-medium text-stone-800 dark:text-stone-100">{t.name}</span>
                  <span className="mt-0.5 block text-xs leading-relaxed text-stone-400">{t.description}</span>
                  {t.folders.length > 0 && (
                    <span className="mt-2 flex flex-wrap gap-1">
                      {t.folders.map((f) => (
                        <span key={f} className="rounded bg-stone-100 px-1.5 py-0.5 text-[10px] text-stone-500 dark:bg-stone-700 dark:text-stone-300">
                          {f}
                        </span>
                      ))}
                    </span>
                  )}
                </button>
              );
            })}
          </div>
        </div>

        {error && <p className="text-sm text-red-600">{error}</p>}

        <div className="flex items-center gap-3 border-t border-stone-100 pt-6 dark:border-stone-800">
          <button
            type="submit"
            disabled={create.isPending || !name.trim()}
            className="rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white transition-colors hover:bg-indigo-700 disabled:opacity-50"
          >
            {create.isPending ? "Creating…" : "Create project"}
          </button>
          <Link to="/projects" className="text-sm text-stone-500 hover:text-stone-700 dark:text-stone-400 dark:hover:text-stone-300">Cancel</Link>
        </div>
      </form>
    </div>
  );
}
