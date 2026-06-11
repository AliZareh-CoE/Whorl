/** Create a project — in the SPA, where ⌘K sends you (owner feedback, cycle 69). */
import { useMutation } from "@tanstack/react-query";
import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { api } from "../api";

export default function NewProject() {
  const navigate = useNavigate();
  const [name, setName] = useState("");
  const [description, setDescription] = useState("");
  const [color, setColor] = useState("#4f46e5");
  const [error, setError] = useState("");

  const create = useMutation({
    mutationFn: () =>
      api<{ slug: string }>("/projects/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name, description, color, status: "active" }),
      }),
    onSuccess: (p) => navigate(`/projects/${p.slug}`),
    onError: (e) => setError(String(e.message ?? e)),
  });

  return (
    <div className="max-w-xl">
      <nav className="mb-6 text-sm text-stone-500">
        <Link to="/projects" className="hover:underline">Projects</Link> / New
      </nav>
      <h1 className="mb-6 text-2xl font-semibold tracking-tight">New project</h1>
      <form className="space-y-4"
            onSubmit={(e) => { e.preventDefault(); if (name.trim()) create.mutate(); }}>
        <div>
          <label htmlFor="np-name" className="mb-1 block text-sm font-medium">Name</label>
          <input id="np-name" value={name} onChange={(e) => setName(e.target.value)} autoFocus
                 className="w-full rounded border border-stone-300 bg-white px-3 py-2 text-sm focus:border-indigo-600 focus:outline-none" />
        </div>
        <div>
          <label htmlFor="np-desc" className="mb-1 block text-sm font-medium">Description</label>
          <textarea id="np-desc" value={description} onChange={(e) => setDescription(e.target.value)} rows={4}
                    placeholder="What is this research about? (markdown ok)"
                    className="w-full rounded border border-stone-300 bg-white px-3 py-2 text-sm focus:border-indigo-600 focus:outline-none" />
        </div>
        <div>
          <label htmlFor="np-color" className="mb-1 block text-sm font-medium">Accent color</label>
          <input id="np-color" type="color" value={color} onChange={(e) => setColor(e.target.value)}
                 className="h-9 w-16 rounded border border-stone-300 bg-white" />
        </div>
        {error && <p className="text-sm text-red-600">{error}</p>}
        <button type="submit" disabled={create.isPending || !name.trim()}
                className="rounded bg-indigo-600 px-4 py-2 text-sm font-medium text-white hover:bg-indigo-700 disabled:opacity-50">
          {create.isPending ? "Creating…" : "Create project"}
        </button>
      </form>
    </div>
  );
}
