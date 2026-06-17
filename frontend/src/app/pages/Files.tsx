import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { File, FileCode, FileImage, FileText, Folder, FolderOpen, Table } from "lucide-react";
import Papa from "papaparse";
import { lazy, Suspense, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";

const TerminalPanel = lazy(() => import("./TerminalPanel"));

type FileNode = {
  id: number;
  name: string;
  rel_path: string;
  kind: string;
  role: string;
  folder_id: number | null;
  size: number;
  is_text: boolean;
};
type FolderNode = { id: number; name: string; parent_id: number | null };
type Tree = { folders: FolderNode[]; files: FileNode[] };

function humanSize(n: number): string {
  if (!n) return "";
  const u = ["B", "KB", "MB", "GB"];
  let i = 0;
  let v = n;
  while (v >= 1024 && i < u.length - 1) {
    v /= 1024;
    i++;
  }
  return `${v.toFixed(v < 10 && i ? 1 : 0)} ${u[i]}`;
}

// lucide file-kind icons (#146) — one consistent open-source set
function Icon({ kind, open, name }: { kind: string; open?: boolean; name?: string }) {
  const cls = "shrink-0";
  if (kind === "folder")
    return open
      ? <FolderOpen size={15} className={`${cls} text-stone-400`} />
      : <Folder size={15} className={`${cls} text-stone-400`} />;
  const ext = (name ?? "").toLowerCase();
  if (kind === "tex" || kind === "bib")
    return <FileText size={15} className={`${cls} text-indigo-400`} />;
  if (kind === "pdf" || /\.pdf$/.test(ext))
    return <FileText size={15} className={`${cls} text-red-400`} />;
  if (/\.(png|jpe?g|gif|webp|svg)$/.test(ext))
    return <FileImage size={15} className={`${cls} text-amber-400`} />;
  if (/\.(csv|tsv)$/.test(ext))
    return <Table size={15} className={`${cls} text-emerald-500`} />;
  if (/\.(py|js|ts|json|yaml|yml|sh|r|toml|css|html|xml)$/.test(ext))
    return <FileCode size={15} className={`${cls} text-sky-500`} />;
  if (kind === "asset") return <File size={15} className={`${cls} text-stone-400`} />;
  return <FileText size={15} className={`${cls} text-stone-400`} />;
}

// subsequence fuzzy match: every char of the query appears in order in the text
function fuzzy(query: string, text: string): boolean {
  const q = query.toLowerCase();
  const t = text.toLowerCase();
  let qi = 0;
  for (let i = 0; i < t.length && qi < q.length; i++) if (t[i] === q[qi]) qi++;
  return qi === q.length;
}

// Ctrl/Cmd-P quick-open (#30 slice 9): fuzzy-jump to any file in the tree.
function QuickOpen({ files, onPick, onClose }: { files: FileNode[]; onPick: (f: FileNode) => void; onClose: () => void }) {
  const [q, setQ] = useState("");
  const matches = (q ? files.filter((f) => fuzzy(q, f.rel_path)) : files).slice(0, 40);
  return (
    <div className="fixed inset-0 z-50 flex items-start justify-center bg-stone-900/30 pt-24" onClick={onClose}>
      <div className="w-full max-w-lg rounded-lg border border-stone-200 bg-white shadow-xl dark:border-stone-800 dark:bg-stone-900" onClick={(e) => e.stopPropagation()}>
        <input
          autoFocus
          value={q}
          onChange={(e) => setQ(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === "Escape") onClose();
            if (e.key === "Enter" && matches[0]) { onPick(matches[0]); onClose(); }
          }}
          placeholder="Go to file…"
          className="w-full rounded-t-lg border-b border-stone-100 px-4 py-3 text-sm focus:outline-none dark:border-stone-800 dark:bg-stone-900 dark:text-stone-100"
        />
        <ul className="max-h-80 overflow-y-auto py-1 text-sm">
          {matches.map((f) => (
            <li key={f.id}>
              <button
                onClick={() => { onPick(f); onClose(); }}
                className="flex w-full items-center gap-2 px-4 py-1.5 text-left hover:bg-stone-50 dark:hover:bg-stone-800"
              >
                <span className="truncate">{f.name}</span>
                <span className="ml-auto truncate font-mono text-xs text-stone-400">{f.rel_path}</span>
              </button>
            </li>
          ))}
          {matches.length === 0 && <li className="px-4 py-2 text-stone-400">No match.</li>}
        </ul>
      </div>
    </div>
  );
}

const isPdf = (f: FileNode) => /\.pdf$/i.test(f.rel_path);
const isImage = (f: FileNode) => /\.(png|jpe?g|gif|webp)$/i.test(f.rel_path);
const isCsv = (f: FileNode) => /\.(csv|tsv)$/i.test(f.rel_path);

// Open-anything preview (#30 slice 2c): route by file type, reusing the local raw/content
// endpoints. PDFs use the browser's native viewer over the vendored, nosniff'd raw bytes.
function FilePreview({ file }: { file: FileNode }) {
  const rawUrl = `/api/v1/documents/${file.id}/raw/`;
  const { data, isLoading, error } = useQuery({
    queryKey: ["file-content", file.id],
    enabled: file.is_text,
    queryFn: () => api<{ content: string; truncated: boolean }>(`/documents/${file.id}/content/`),
  });

  if (isImage(file))
    return <img src={rawUrl} alt={file.name} className="max-h-[62vh] max-w-full rounded border border-stone-200 dark:border-stone-800" />;
  if (isPdf(file))
    return <iframe src={rawUrl} title={file.name} className="h-[62vh] w-full rounded border border-stone-200 dark:border-stone-800" />;

  if (!file.is_text)
    return (
      <div className="rounded border border-dashed border-stone-200 p-6 text-center text-sm text-stone-500 dark:border-stone-700 dark:text-stone-400">
        <p className="mb-2">No in-app preview for this file type.</p>
        <a href={`/api/v1/documents/${file.id}/raw/`} className="text-indigo-600 hover:underline dark:text-indigo-400" download>
          Download {file.name}
        </a>
      </div>
    );

  if (isLoading) return <p className="text-sm text-stone-400">Loading…</p>;
  if (error || !data) return <p className="text-sm text-red-600">Couldn't load this file.</p>;

  if (isCsv(file)) {
    const parsed = Papa.parse<string[]>(data.content.trim(), { skipEmptyLines: true });
    const rows = (parsed.data as string[][]).slice(0, 200);
    return (
      <div className="max-h-[62vh] overflow-auto">
        <table className="w-full border-collapse text-xs">
          <tbody>
            {rows.map((row, i) => (
              <tr key={i} className={i === 0 ? "bg-stone-50 font-medium dark:bg-stone-800" : ""}>
                {row.map((cell, j) => (
                  <td key={j} className="border border-stone-100 px-2 py-1 dark:border-stone-800">{cell}</td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
        {data.truncated && <p className="mt-1 text-xs text-stone-400">Showing the first part of a large file.</p>}
      </div>
    );
  }

  return <TextView file={file} content={data.content} truncated={data.truncated} />;
}

const slugFromPath = () => location.pathname.split("/")[2];

// In-place text editing (#30 slice 2d): general nodes are editable + saved back to the
// content endpoint; manuscript sources are read-only here (they sync from the LaTeX editor).
function TextView({ file, content, truncated }: { file: FileNode; content: string; truncated: boolean }) {
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState(false);
  const [draft, setDraft] = useState(content);
  useEffect(() => {
    setDraft(content);
    setEditing(false);
  }, [content, file.id]);

  const save = useMutation({
    mutationFn: () =>
      api(`/documents/${file.id}/content/`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content: draft }),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["file-content", file.id] });
      queryClient.invalidateQueries({ queryKey: ["tree", slugFromPath()] });
      setEditing(false);
    },
  });

  const manuscript = file.role === "manuscript_source";
  return (
    <div>
      <div className="mb-1 flex items-center justify-end gap-2 text-xs">
        {manuscript ? (
          <span className="text-stone-400">read-only — edit in the LaTeX editor</span>
        ) : editing ? (
          <>
            <button onClick={() => save.mutate()} disabled={save.isPending} className="rounded bg-indigo-600 px-2 py-0.5 font-medium text-white hover:bg-indigo-700 disabled:opacity-50">Save</button>
            <button onClick={() => { setDraft(content); setEditing(false); }} className="text-stone-500 hover:underline dark:text-stone-400">Cancel</button>
          </>
        ) : (
          <button onClick={() => setEditing(true)} className="text-indigo-600 hover:underline dark:text-indigo-400" disabled={truncated} title={truncated ? "File too large to edit in-app" : ""}>Edit</button>
        )}
      </div>
      {editing ? (
        <textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          spellCheck={false}
          className="h-[58vh] w-full rounded border border-indigo-300 bg-white p-3 font-mono text-xs leading-relaxed text-stone-800 focus:outline-none dark:border-stone-700 dark:bg-stone-800 dark:text-stone-100"
        />
      ) : (
        <pre className="max-h-[58vh] overflow-auto rounded border border-stone-200 bg-stone-50 p-3 font-mono text-xs leading-relaxed text-stone-700 dark:border-stone-800 dark:bg-stone-800 dark:text-stone-300">
          {content}
          {truncated && "\n\n… (truncated)"}
        </pre>
      )}
    </div>
  );
}

export default function Files() {
  const { slug } = useParams();
  const { data, isLoading, error } = useQuery({
    queryKey: ["tree", slug],
    queryFn: () => api<Tree>(`/projects/${slug}/tree/`),
  });
  const [expanded, setExpanded] = useState<Record<number, boolean>>({});
  const [selected, setSelected] = useState<FileNode | null>(null);
  const [showTerminal, setShowTerminal] = useState(false);
  const queryClient = useQueryClient();
  const refreshTree = () => queryClient.invalidateQueries({ queryKey: ["tree", slug] });

  const newFolder = useMutation({
    mutationFn: (name: string) =>
      api("/folders/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project: slug, parent: null, name }),
      }),
    onSuccess: refreshTree,
  });
  const deleteDoc = useMutation({
    mutationFn: (id: number) => api(`/documents/${id}/`, { method: "DELETE" }),
    onSuccess: () => {
      setSelected(null);
      refreshTree();
    },
  });
  const renameDoc = useMutation({
    mutationFn: (v: { id: number; title: string }) =>
      api(`/documents/${v.id}/`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: v.title }),
      }),
    onSuccess: refreshTree,
  });
  const moveDoc = useMutation({
    mutationFn: (v: { id: number; folder: number | null }) =>
      api(`/documents/${v.id}/`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ folder: v.folder }),
      }),
    onSuccess: () => {
      setSelected(null);
      refreshTree();
    },
  });
  const saveTemplate = useMutation({
    mutationFn: (name: string) =>
      api(`/projects/${slug}/save-template/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      }),
    onSuccess: () => window.alert("Saved — pick it under Scaffold when creating a project."),
  });
  const isDesktop = typeof window !== "undefined" && "__TAURI__" in window;
  const [localFile, setLocalFile] = useState<{ name: string; path: string; content: string } | null>(null);
  const openFromDisk = async () => {
    const tauri = (await import("@tauri-apps/api")) as unknown as {
      core: { invoke: (c: string) => Promise<{ name: string; path: string; content: string } | null> };
    };
    try {
      const f = await tauri.core.invoke("open_local_file");
      if (f) { setLocalFile(f); setSelected(null); }
    } catch (e) {
      window.alert(String(e));
    }
  };
  const [quickOpen, setQuickOpen] = useState(false);
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "p") {
        e.preventDefault();
        setQuickOpen((v) => !v);
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  const [dragging, setDragging] = useState(false);
  const upload = useMutation({
    mutationFn: (files: FileList) => {
      const fd = new FormData();
      for (const f of Array.from(files)) fd.append("files", f);
      return api(`/projects/${slug}/upload-file/`, { method: "POST", body: fd });
    },
    onSuccess: refreshTree,
  });

  const { childFolders, folderFiles, rootFolders, rootFiles } = useMemo(() => {
    const cf: Record<number, FolderNode[]> = {};
    const ff: Record<number, FileNode[]> = {};
    const rootFolders: FolderNode[] = [];
    const rootFiles: FileNode[] = [];
    for (const f of data?.folders ?? []) {
      if (f.parent_id == null) rootFolders.push(f);
      else (cf[f.parent_id] ??= []).push(f);
    }
    for (const f of data?.files ?? []) {
      if (f.folder_id == null) rootFiles.push(f);
      else (ff[f.folder_id] ??= []).push(f);
    }
    const byName = <T extends { name: string }>(a: T, b: T) => a.name.localeCompare(b.name);
    rootFolders.sort(byName);
    rootFiles.sort(byName);
    Object.values(cf).forEach((l) => l.sort(byName));
    Object.values(ff).forEach((l) => l.sort(byName));
    return { childFolders: cf, folderFiles: ff, rootFolders, rootFiles };
  }, [data]);

  // [REV] keyboard navigation: flatten the *visible* tree in render order so arrow keys
  // can walk it like a real IDE explorer.
  type FlatRow =
    | { kind: "folder"; id: number; depth: number; hasChildren: boolean; folder: FolderNode }
    | { kind: "file"; id: number; depth: number; file: FileNode };
  const flat = useMemo<FlatRow[]>(() => {
    const out: FlatRow[] = [];
    const walk = (f: FolderNode, depth: number) => {
      const kids = childFolders[f.id] ?? [];
      const files = folderFiles[f.id] ?? [];
      out.push({ kind: "folder", id: f.id, depth, hasChildren: !!(kids.length || files.length), folder: f });
      if (expanded[f.id]) {
        kids.forEach((k) => walk(k, depth + 1));
        files.forEach((fl) => out.push({ kind: "file", id: fl.id, depth: depth + 1, file: fl }));
      }
    };
    rootFolders.forEach((f) => walk(f, 0));
    rootFiles.forEach((fl) => out.push({ kind: "file", id: fl.id, depth: 0, file: fl }));
    return out;
  }, [childFolders, folderFiles, rootFolders, rootFiles, expanded]);

  const [focusIdx, setFocusIdx] = useState(0);
  useEffect(() => {
    if (focusIdx > flat.length - 1) setFocusIdx(Math.max(0, flat.length - 1));
  }, [flat.length, focusIdx]);
  useEffect(() => {
    document.querySelector('[data-tree-focus="true"]')?.scrollIntoView({ block: "nearest" });
  }, [focusIdx]);
  const focusKey = flat[focusIdx] ? `${flat[focusIdx].kind}${flat[focusIdx].id}` : "";

  // [REV] type-to-select: like a real file explorer, typing letters jumps to the next
  // visible row whose name starts with what you've typed. The buffer resets after a pause,
  // on Escape, or when the tree loses focus (#168/#169); the current buffer shows as a hint.
  const typeahead = useRef<{ buffer: string; at: number }>({ buffer: "", at: 0 });
  const hintTimer = useRef<ReturnType<typeof setTimeout>>();
  const [typedHint, setTypedHint] = useState("");
  const rowName = (r: FlatRow) => (r.kind === "folder" ? r.folder.name : r.file.name);
  const clearTypeahead = () => {
    typeahead.current.buffer = "";
    setTypedHint("");
    if (hintTimer.current) clearTimeout(hintTimer.current);
  };
  const jumpToTyped = (ch: string) => {
    const now = Date.now();
    const ta = typeahead.current;
    ta.buffer = now - ta.at > 800 ? ch : ta.buffer + ch;
    ta.at = now;
    setTypedHint(ta.buffer);
    if (hintTimer.current) clearTimeout(hintTimer.current);
    hintTimer.current = setTimeout(clearTypeahead, 1000);
    const q = ta.buffer.toLowerCase();
    // start the search just after the current row so repeated letters cycle matches
    const start = ta.buffer.length === 1 ? focusIdx + 1 : focusIdx;
    for (let n = 0; n < flat.length; n++) {
      const idx = (start + n) % flat.length;
      if (rowName(flat[idx]).toLowerCase().startsWith(q)) { setFocusIdx(idx); return; }
    }
  };

  const onTreeKey = (e: {
    key: string;
    ctrlKey?: boolean;
    metaKey?: boolean;
    altKey?: boolean;
    preventDefault: () => void;
  }) => {
    const r = flat[focusIdx];
    if (e.key === "Escape" && typeahead.current.buffer) {
      // a pending typeahead buffer swallows Escape to clear itself first (#169)
      e.preventDefault();
      clearTypeahead();
      return;
    }
    if (e.key.length === 1 && /\S/.test(e.key) && !e.ctrlKey && !e.metaKey && !e.altKey) {
      // printable single char with no modifier → typeahead (leave Ctrl-P etc. alone)
      e.preventDefault();
      jumpToTyped(e.key);
      return;
    }
    if (e.key === "ArrowDown") { e.preventDefault(); setFocusIdx((i) => Math.min(flat.length - 1, i + 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setFocusIdx((i) => Math.max(0, i - 1)); }
    else if (e.key === "Enter") {
      e.preventDefault();
      if (r?.kind === "file") setSelected(r.file);
      else if (r?.kind === "folder") setExpanded((x) => ({ ...x, [r.id]: !x[r.id] }));
    } else if (e.key === "ArrowRight" && r?.kind === "folder") {
      if (r.hasChildren && !expanded[r.id]) { e.preventDefault(); setExpanded((x) => ({ ...x, [r.id]: true })); }
      else { e.preventDefault(); setFocusIdx((i) => Math.min(flat.length - 1, i + 1)); }
    } else if (e.key === "ArrowLeft" && r?.kind === "folder" && expanded[r.id]) {
      e.preventDefault();
      setExpanded((x) => ({ ...x, [r.id]: false }));
    }
  };

  if (isLoading) return <p className="text-sm text-stone-400">Loading files…</p>;
  if (error || !data) return <p className="text-sm text-red-600">Couldn't load the file tree.</p>;

  const fileRow = (f: FileNode, depth: number) => (
    <button
      key={`f${f.id}`}
      data-tree-focus={focusKey === `file${f.id}`}
      onClick={() => { setSelected(f); setFocusIdx(flat.findIndex((r) => r.kind === "file" && r.id === f.id)); }}
      style={{ paddingLeft: depth * 14 + 8 }}
      className={`flex w-full items-center gap-2 rounded py-1 pr-2 text-left text-sm hover:bg-stone-50 dark:hover:bg-stone-800 ${focusKey === `file${f.id}` ? "ring-1 ring-indigo-200" : ""} ${selected?.id === f.id ? "bg-indigo-50 font-medium text-indigo-700 dark:bg-indigo-500/15 dark:text-indigo-300" : "text-stone-700 dark:text-stone-300"}`}
    >
      <Icon kind={f.kind || "other"} name={f.name} />
      <span className="min-w-0 flex-1 truncate">{f.name}</span>
      {f.role === "manuscript_source" && (
        <span className="shrink-0 rounded bg-stone-100 px-1 text-[10px] uppercase tracking-wide text-stone-400 dark:bg-stone-800">ms</span>
      )}
      <span className="shrink-0 font-mono text-[11px] text-stone-400">{humanSize(f.size)}</span>
    </button>
  );

  const folderRow = (folder: FolderNode, depth: number) => {
    const open = expanded[folder.id];
    const kids = childFolders[folder.id] ?? [];
    const files = folderFiles[folder.id] ?? [];
    return (
      <div key={`d${folder.id}`}>
        <button
          data-tree-focus={focusKey === `folder${folder.id}`}
          onClick={() => { setExpanded((e) => ({ ...e, [folder.id]: !e[folder.id] })); setFocusIdx(flat.findIndex((r) => r.kind === "folder" && r.id === folder.id)); }}
          style={{ paddingLeft: depth * 14 + 8 }}
          className={`flex w-full items-center gap-2 rounded py-1 pr-2 text-left text-sm text-stone-700 hover:bg-stone-50 dark:text-stone-300 dark:hover:bg-stone-800 ${focusKey === `folder${folder.id}` ? "ring-1 ring-indigo-200" : ""}`}
        >
          <span className="w-3 shrink-0 text-xs text-stone-400">{kids.length || files.length ? (open ? "▾" : "▸") : ""}</span>
          <Icon kind="folder" open={open} />
          <span className="min-w-0 flex-1 truncate font-medium">{folder.name}</span>
        </button>
        {open && (
          <div>
            {kids.map((k) => folderRow(k, depth + 1))}
            {files.map((f) => fileRow(f, depth + 1))}
          </div>
        )}
      </div>
    );
  };

  const total = data.files.length;
  return (
    <div>
      <nav className="mb-4 text-sm text-stone-500 dark:text-stone-400">
        <Link to="/projects" className="hover:underline">Projects</Link> /{" "}
        <Link to={`/projects/${slug}`} className="hover:underline">{slug}</Link> / Files
      </nav>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight dark:text-stone-100">Files</h1>
          <p className="mt-0.5 text-sm text-stone-500 dark:text-stone-400">{total} file{total === 1 ? "" : "s"} · everything in one tree</p>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <button
            onClick={() => {
              const name = window.prompt("New folder name");
              if (name) newFolder.mutate(name.trim());
            }}
            className="rounded border border-stone-200 bg-white px-2 py-1 text-xs text-stone-500 hover:border-stone-300 hover:text-indigo-700 dark:border-stone-800 dark:bg-stone-900 dark:text-stone-400 dark:hover:border-stone-700 dark:hover:text-indigo-300"
          >
            + Folder
          </button>
          <button
            onClick={() => {
              const name = window.prompt("Save this project's structure as a template named");
              if (name) saveTemplate.mutate(name.trim());
            }}
            className="rounded border border-stone-200 bg-white px-2 py-1 text-xs text-stone-500 hover:border-stone-300 hover:text-indigo-700 dark:border-stone-800 dark:bg-stone-900 dark:text-stone-400 dark:hover:border-stone-700 dark:hover:text-indigo-300"
            title="Reuse this folder layout when creating new projects"
          >
            Save as template
          </button>
          <button
            onClick={() => setShowTerminal((v) => !v)}
            className={`flex items-center gap-1 rounded border px-2 py-1 text-xs ${showTerminal ? "border-indigo-200 bg-indigo-50 text-indigo-700 dark:border-indigo-500/30 dark:bg-indigo-500/15 dark:text-indigo-300" : "border-stone-200 bg-white text-stone-500 hover:border-stone-300 hover:text-indigo-700 dark:border-stone-800 dark:bg-stone-900 dark:text-stone-400 dark:hover:border-stone-700 dark:hover:text-indigo-300"}`}
            title="Toggle the terminal (Atlas desktop app)"
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="4 17 10 11 4 5" /><line x1="12" y1="19" x2="20" y2="19" /></svg>
            Terminal
          </button>
          {isDesktop && (
            <button onClick={openFromDisk} className="rounded border border-stone-200 bg-white px-2 py-1 text-xs text-stone-500 hover:border-stone-300 hover:text-indigo-700 dark:border-stone-800 dark:bg-stone-900 dark:text-stone-400 dark:hover:border-stone-700 dark:hover:text-indigo-300" title="Open any file from your computer (desktop app)">Open from disk…</button>
          )}
          <button onClick={() => setQuickOpen(true)} className="rounded border border-stone-200 bg-white px-2 py-1 font-mono text-xs text-stone-500 hover:border-stone-300 hover:text-indigo-700 dark:border-stone-800 dark:bg-stone-900 dark:text-stone-400 dark:hover:border-stone-700 dark:hover:text-indigo-300" title="Quick open (Ctrl/Cmd-P)">⌘P</button>
        </div>
      </div>
      {quickOpen && (
        <QuickOpen
          files={data.files}
          onPick={(f) => setSelected(f)}
          onClose={() => setQuickOpen(false)}
        />
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div
          tabIndex={0}
          onKeyDown={onTreeKey}
          onBlur={clearTypeahead}
          role="tree"
          aria-label="Project files"
          className={`relative col-span-1 max-h-[75vh] overflow-y-auto rounded border bg-white p-2 focus:outline-none dark:bg-stone-900 ${dragging ? "border-indigo-400 ring-2 ring-indigo-100" : "border-stone-200 dark:border-stone-800"}`}
          onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            if (e.dataTransfer.files.length) upload.mutate(e.dataTransfer.files);
          }}
        >
          <div className="sticky top-0 z-10 -mx-2 -mt-2 mb-1 border-b border-stone-100 bg-white px-3 py-2 text-sm font-medium uppercase tracking-wide text-stone-400 dark:border-stone-800 dark:bg-stone-900">
            Explorer
          </div>
          {typedHint && (
            <span className="pointer-events-none absolute right-2 top-2 z-20 rounded bg-stone-700/90 px-1.5 py-0.5 font-mono text-xs text-white">
              {typedHint}
            </span>
          )}
          {dragging && <p className="mb-1 rounded bg-indigo-50 py-1 text-center text-xs font-medium text-indigo-600 dark:bg-indigo-500/15 dark:text-indigo-300">Drop to upload</p>}
          {rootFolders.map((f) => folderRow(f, 0))}
          {rootFiles.map((f) => fileRow(f, 0))}
          {total === 0 && !rootFolders.length && (
            <div className="px-3 py-8 text-center">
              <p className="text-sm font-medium text-stone-600 dark:text-stone-300">This project has no files yet</p>
              <p className="mt-1 text-sm text-stone-400">Drag files here to upload, or add them on the{" "}
                <a href={`/projects/${slug}/documents/`} className="text-indigo-600 hover:underline dark:text-indigo-400">documents page</a>.
              </p>
            </div>
          )}
        </div>
        <div className="card col-span-1 lg:col-span-2 lg:min-h-[75vh]">
          {localFile ? (
            <div>
              <div className="mb-2 flex items-center gap-2 border-b border-stone-100 pb-2 dark:border-stone-800">
                <h2 className="min-w-0 flex-1 truncate text-sm font-medium text-stone-800 dark:text-stone-100">{localFile.name}</h2>
                <button onClick={() => setLocalFile(null)} className="shrink-0 text-xs text-stone-400 hover:text-stone-600 dark:hover:text-stone-300">✕ close</button>
              </div>
              <p className="mb-3 truncate font-mono text-xs text-stone-400">{localFile.path} · from disk</p>
              <pre className="max-h-[58vh] overflow-auto rounded border border-stone-200 bg-stone-50 p-3 font-mono text-xs leading-relaxed text-stone-700 dark:border-stone-800 dark:bg-stone-800 dark:text-stone-300">{localFile.content}</pre>
            </div>
          ) : selected ? (
            <div>
              <div className="mb-2 flex items-center gap-2 border-b border-stone-100 pb-2 dark:border-stone-800">
                <Icon kind={selected.kind || "other"} name={selected.name} />
                <h2 className="min-w-0 flex-1 truncate text-sm font-medium text-stone-800 dark:text-stone-100">{selected.name}</h2>
              </div>
              <dl className="mb-3 flex flex-wrap gap-x-4 gap-y-0.5 text-xs text-stone-400">
                <span className="font-mono text-stone-500 dark:text-stone-400">{selected.rel_path}</span>
                <span>· {selected.kind || "file"}</span>
                {selected.role === "manuscript_source" && <span>· manuscript source</span>}
                {!!humanSize(selected.size) && <span>· {humanSize(selected.size)}</span>}
              </dl>
              {selected.role !== "manuscript_source" && (
                <div className="mb-3 flex items-center gap-3 text-xs">
                  <select
                    value={selected.folder_id ?? ""}
                    onChange={(e) =>
                      moveDoc.mutate({ id: selected.id, folder: e.target.value ? Number(e.target.value) : null })
                    }
                    title="Move to folder"
                    className="rounded border border-stone-200 bg-white px-1.5 py-1 text-stone-600 hover:border-stone-300 dark:border-stone-700 dark:bg-stone-800 dark:text-stone-300"
                  >
                    <option value="">(project root)</option>
                    {(data.folders ?? [])
                      .filter((f) => !f.name.startsWith("manuscript-"))
                      .map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
                  </select>
                  <button
                    onClick={() => {
                      const title = window.prompt("Rename file to", selected.name);
                      if (title) renameDoc.mutate({ id: selected.id, title: title.trim() });
                    }}
                    className="text-indigo-600 hover:underline dark:text-indigo-400"
                  >
                    Rename
                  </button>
                  <button
                    onClick={() => {
                      if (window.confirm(`Delete ${selected.name}?`)) deleteDoc.mutate(selected.id);
                    }}
                    className="text-red-600 hover:underline"
                  >
                    Delete
                  </button>
                </div>
              )}
              <FilePreview key={selected.id} file={selected} />
            </div>
          ) : (
            <div className="flex h-full min-h-[40vh] flex-col items-center justify-center px-6 text-center">
              <File size={28} className="mb-3 text-stone-300" />
              <p className="text-sm font-medium text-stone-600 dark:text-stone-300">No file selected</p>
              <p className="mt-1 max-w-xs text-sm text-stone-400">Pick a file from the tree to preview it here — images, PDFs, tables, and text all open inline.</p>
            </div>
          )}
        </div>
      </div>

      {showTerminal && (
        <div className="mt-3 h-64 overflow-hidden rounded border border-stone-800 bg-stone-900 p-1">
          <Suspense fallback={<p className="p-3 text-sm text-stone-400">Loading terminal…</p>}>
            <TerminalPanel cwd={undefined} />
          </Suspense>
        </div>
      )}
    </div>
  );
}
