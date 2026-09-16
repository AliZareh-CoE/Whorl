import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { Archive, Copy, Download, ExternalLink, File, FileCode, FileImage, FilePlus2, FileText, Folder, FolderOpen, FolderPlus, History, Pencil, RefreshCw, RotateCcw, Table, Trash2, Upload } from "lucide-react";
import Papa from "papaparse";
import { useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";
import { Skeleton, SkeletonLines } from "../../components/Skeleton";
import { ErrorState } from "../../components/ErrorState";
import { confirmDialog, errorDialog, noticeDialog, promptDialog } from "../../components/Dialog";
import { Kebab, useMenu, type MenuItem } from "../../components/Menu";

import { openTerminal } from "../TerminalDock";
import { openPath, revealPath } from "../external";
import { MOD } from "../shortcuts";

type FileNode = {
  id: number;
  name: string;
  rel_path: string;
  kind: string;
  role: string;
  folder_id: number | null;
  size: number;
  version: number; // #553: bumped by every replace / edit / write / restore
  versions: number; // earlier states kept in its history
  created_at: string; // #557: ISO stamps — modified_at is when the bytes last changed
  updated_at: string;
  modified_at: string;
  description: string; // #554: what the file is, editable in the pane
  tags: Tag[]; // #554: the project's tags on this file (name + colour)
  is_text: boolean;
  local_path?: string | null; // desktop builds only: where the file lives on this computer
};
type Tag = { id: number; name: string; color: string; count?: number };
type Page<T> = { count: number; results: T[] };
// #554: a new tag made from the explorer gets a colour from its name, so chips are never grey by default
const TAG_COLOURS: [string, string][] = [["Red", "#dc2626"], ["Orange", "#ea580c"], ["Amber", "#ca8a04"], ["Green", "#16a34a"], ["Cyan", "#0891b2"], ["Blue", "#2563eb"], ["Violet", "#7c3aed"], ["Pink", "#db2777"]];
const TAG_PALETTE = TAG_COLOURS.map(([, hex]) => hex);
function tagColor(name: string): string {
  let h = 0;
  for (const c of name) h = (h * 31 + c.charCodeAt(0)) >>> 0;
  return TAG_PALETTE[h % TAG_PALETTE.length];
}
function TagDot({ color }: { color: string }) {
  return <span className="inline-block h-2 w-2 shrink-0 rounded-full" style={{ background: color || "#a8a29e" }} aria-hidden="true" />;
}
type Version = { number: number; created_at: string; size: number; content_type: string; note: string; source: string; is_text: boolean };
const SOURCE_LABEL: Record<string, string> = { upload: "replaced by an upload", edit: "edited in place", write: "written by the API or Claude", restore: "before a restore" };
type FolderNode = { id: number; name: string; parent_id: number | null };
type Tree = { folders: FolderNode[]; files: FileNode[] };

// #557: relative stamps for rows and the pane (the absolute time sits in the title)
function ago(iso: string, now: number = Date.now()): string {
  const m = (now - new Date(iso).getTime()) / 60000;
  if (m < 1) return "just now";
  if (m < 60) return `${Math.round(m)} min ago`;
  if (m < 1440) return `${Math.round(m / 60)} h ago`;
  const d = Math.round(m / 1440);
  if (d < 14) return `${d} d ago`;
  if (d < 60) return `${Math.round(d / 7)} wk ago`;
  if (d < 365) return `${Math.round(d / 30)} mo ago`;
  return `${Math.round(d / 365)} y ago`;
}
const FMT = new Intl.DateTimeFormat(undefined, { dateStyle: "medium", timeStyle: "short" }); // one formatter, not one per row per render
const stamp = (iso: string) => FMT.format(new Date(iso));
type SortKey = "name" | "modified" | "size";
const SORT_KEY = "atlas-files-sort";
const RECENT_KEY = "atlas-files-recent";
function readSort(): SortKey {
  try { const v = localStorage.getItem(SORT_KEY); if (v === "modified" || v === "size") return v; } catch { /* private mode */ }
  return "name";
}
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
  const matches = (q ? files.filter((f) => fuzzy(q, f.rel_path) || f.tags.some((t) => fuzzy(q, t.name))) : files).slice(0, 40);
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
                {f.tags.map((t) => <TagDot key={t.id} color={t.color} />)}
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
/** #553: a file's history — the states earlier replaces, edits, writes and restores left
 *  behind. Download any of them; Restore files the current state first, so it is undoable. */
// #555 (backlog 352): what changed from an earlier version to now — a unified line diff, and
// for a .csv / .tsv the changed cells (rows aligned by content, columns by header).
type CellChange = { row: number; column: string; then: string; now: string };
type TableDiff = { headers: string[]; changes: CellChange[]; rows_added: number; rows_removed: number; cols_added: string[]; cols_removed: string[]; truncated: boolean };
type Diff = { number: number; version: number; is_text: boolean; too_large: boolean; same: boolean; diff: string; added: number; removed: number; table: TableDiff | null };
const plural = (n: number, word: string) => `${n} ${word}${n === 1 ? "" : "s"}`;
function VersionDiff({ file, number }: { file: FileNode; number: number }) {
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["file-diff", file.id, number, file.version], // a restore or replace is a new comparison
    queryFn: () => api<Diff>(`/documents/${file.id}/versions/${number}/diff/`),
  });
  if (isLoading) return <div role="status" aria-label="Loading" className="basis-full"><SkeletonLines lines={2} /></div>;
  if (error || !data) return <div className="basis-full"><ErrorState message="Couldn't compare that version." onRetry={() => refetch()} /></div>;
  const t = data.table;
  const summary = data.same
    ? "identical to the current version"
    : !data.is_text
      ? "not text — download both to compare"
      : data.too_large
        ? "too large to compare here — download both"
        : t
          ? [
              t.changes.length ? `${plural(t.changes.length, "cell")} changed` : null,
              t.rows_added ? `${plural(t.rows_added, "row")} added` : null,
              t.rows_removed ? `${plural(t.rows_removed, "row")} removed` : null,
              t.cols_added.length ? `${plural(t.cols_added.length, "column")} added: ${t.cols_added.join(", ")}` : null,
              t.cols_removed.length ? `${plural(t.cols_removed.length, "column")} removed: ${t.cols_removed.join(", ")}` : null,
            ].filter(Boolean).join(" · ") || `+${data.added} −${data.removed} lines`
          : `+${data.added} −${data.removed} lines`;
  // the line diff is the whole story for text; for a table it is shown when cells alone do not tell it
  const showLines = !data.same && data.is_text && !data.too_large && (!t || t.rows_added > 0 || t.rows_removed > 0 || t.cols_added.length > 0 || t.cols_removed.length > 0 || t.changes.length === 0);
  return (
    <div className="mt-1 basis-full rounded-lg border border-stone-200 bg-white p-2 dark:border-stone-700 dark:bg-stone-900" data-testid="version-diff">
      <p className="mb-1 text-stone-500 dark:text-stone-400">v{number} → v{data.version} (now) · {summary}{t?.truncated ? " · truncated" : ""}</p>
      {t && t.changes.length > 0 && (
        <table className="mb-1 w-full text-left font-mono text-[10px]" data-testid="cell-changes">
          <thead><tr className="text-stone-400"><th className="pr-3 font-normal">row</th><th className="pr-3 font-normal">column</th><th className="pr-3 font-normal">then</th><th className="font-normal">now</th></tr></thead>
          <tbody>
            {t.changes.map((c, i) => (
              <tr key={i}><td className="pr-3 text-stone-500">{c.row}</td><td className="pr-3 text-stone-600 dark:text-stone-300">{c.column}</td><td className="pr-3 text-red-600 line-through dark:text-red-300">{c.then}</td><td className="text-emerald-700 dark:text-emerald-300">{c.now}</td></tr>
            ))}
          </tbody>
        </table>
      )}
      {showLines && (
        <pre className="max-h-60 overflow-auto whitespace-pre-wrap break-words font-mono text-[10px] leading-snug" data-testid="line-diff">
          {data.diff.split("\n").slice(2).map((line, i) => <span key={i} className={`block ${line.startsWith("+") ? "text-emerald-700 dark:text-emerald-300" : line.startsWith("-") ? "text-red-600 dark:text-red-300" : line.startsWith("@@") ? "text-stone-400" : "text-stone-600 dark:text-stone-300"}`}>{line}</span>)}
        </pre>
      )}
    </div>
  );
}

function HistoryPanel({ file, onRestored }: { file: FileNode; onRestored: () => void }) {
  const [compare, setCompare] = useState<number | null>(null); // #555: the version shown against now
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["file-versions", file.id, file.version],
    queryFn: () => api<{ id: number; version: number; versions: Version[] }>(`/documents/${file.id}/versions/`),
  });
  const restore = useMutation({
    mutationFn: (n: number) => api(`/documents/${file.id}/versions/${n}/restore/`, { method: "POST" }),
    onSuccess: onRestored,
    onError: (e) => void errorDialog("Couldn't restore that version", e),
  });
  if (isLoading) return <div role="status" aria-label="Loading"><SkeletonLines lines={3} /></div>;
  if (error || !data) return <ErrorState message="Couldn't load the history." onRetry={() => refetch()} />;
  return (
    <div className="mb-3 rounded-lg border border-stone-200 bg-stone-50/60 p-2 text-xs dark:border-stone-800 dark:bg-stone-800/40" data-testid="file-history">
      <p className="mb-1 flex items-center gap-1 font-medium text-stone-600 dark:text-stone-300"><History className="h-3.5 w-3.5" aria-hidden="true" />History · now v{data.version}{data.versions.length ? ` · ${data.versions.length} earlier` : ""}</p>
      {data.versions.length === 0 && <p className="text-stone-400">No earlier versions yet — Replace… with a newer file, edit it here, or let Claude write it, and the state it replaces lands here.</p>}
      <ul className="divide-y divide-stone-200 dark:divide-stone-800">
        {data.versions.map((v) => (
          <li key={v.number} className="flex flex-wrap items-center gap-x-3 gap-y-1 py-1" data-testid="file-version">
            <span className="w-8 shrink-0 font-mono font-medium text-stone-600 dark:text-stone-300">v{v.number}</span>
            <span className="min-w-0 flex-1 text-stone-500 dark:text-stone-400">{new Date(v.created_at).toLocaleString(undefined, { dateStyle: "medium", timeStyle: "short" })} · {humanSize(v.size)} · {SOURCE_LABEL[v.source] ?? v.source}{v.note ? <> · <span className="text-stone-700 dark:text-stone-200">{v.note}</span></> : null}</span>
            {(v.is_text || file.is_text) && <button type="button" onClick={() => setCompare((c) => (c === v.number ? null : v.number))} aria-expanded={compare === v.number} className="shrink-0 text-stone-600 hover:underline dark:text-stone-300" data-testid="diff-version">{compare === v.number ? "Hide" : "Compare"}</button>}
            <a href={`/api/v1/documents/${file.id}/versions/${v.number}/raw/`} download className="shrink-0 text-stone-500 hover:underline dark:text-stone-400">Download</a>
            <button type="button" onClick={async () => { if (await confirmDialog({ title: `Restore v${v.number} of “${file.name}”?`, confirmLabel: "Restore", body: `The current v${data.version} is kept in the history, so this can be undone.` })) restore.mutate(v.number); }} disabled={restore.isPending} className="inline-flex shrink-0 items-center gap-1 text-indigo-600 hover:underline disabled:opacity-50 dark:text-indigo-400" data-testid="restore-version"><RotateCcw className="h-3 w-3" aria-hidden="true" />Restore</button>
            {compare === v.number && <VersionDiff file={file} number={v.number} />}
          </li>
        ))}
      </ul>
    </div>
  );
}

function FilePreview({ file }: { file: FileNode }) {
  const rawUrl = `/api/v1/documents/${file.id}/raw/?v=${file.version}`; // #553: the raw bytes are cached a day by id; a new version is a new URL
  const { data, isLoading, error, refetch } = useQuery({
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
        <a href={`/api/v1/documents/${file.id}/raw/?v=${file.version}`} className="text-indigo-600 hover:underline dark:text-indigo-400" download>
          Download {file.name}
        </a>
      </div>
    );

  if (isLoading)
    return (
      <div role="status" aria-label="Loading">
        <SkeletonLines lines={6} />
      </div>
    );
  if (error || !data) return <ErrorState message="Couldn't load this file." onRetry={() => refetch()} />;

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
  const { data, isLoading, error, refetch } = useQuery({
    queryKey: ["tree", slug],
    queryFn: () => api<Tree>(`/projects/${slug}/tree/`),
  });
  const [expanded, setExpanded] = useState<Record<number, boolean>>({});
  const [selected, setSelected] = useState<FileNode | null>(null);
  // #557: files sort by name, last change or size (folders always first, by name); remembered
  const [sort, setSortState] = useState<SortKey>(readSort);
  const setSort = (k: SortKey) => { setSortState(k); try { localStorage.setItem(SORT_KEY, k); } catch { /* private mode */ } };
  const [recentOpen, setRecentOpen] = useState<boolean>(() => { try { return localStorage.getItem(RECENT_KEY) !== "0"; } catch { return true; } });
  const toggleRecent = () => setRecentOpen((o) => { try { localStorage.setItem(RECENT_KEY, o ? "0" : "1"); } catch { /* private mode */ } return !o; });
  // #554: one tag narrows the tree to the files carrying it (folders keep only matching descendants)
  // #559 (backlog 354): several chips = the files carrying every one of them (AND)
  const [tagFilter, setTagFilter] = useState<string[]>([]);
  const filtering = tagFilter.length > 0;
  const isOpen = (id: number) => expanded[id] ?? filtering; // filtered folders start open
  const tagsQ = useQuery({ queryKey: ["doc-tags", slug], queryFn: () => api<Page<Tag>>(`/tags/?project=${slug}`) });
  const queryClient = useQueryClient();
  const refreshTree = () => queryClient.invalidateQueries({ queryKey: ["tree", slug] });

  const fail = (title: string) => (e: unknown) => void errorDialog(title, e);
  const newFolder = useMutation({
    mutationFn: ({ name, parent }: { name: string; parent: number | null }) =>
      api("/folders/", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ project: slug, parent, name }),
      }),
    onSuccess: (_, v) => { if (v.parent != null) setExpanded((e) => ({ ...e, [v.parent as number]: true })); refreshTree(); },
    onError: fail("Couldn't create the folder"),
  });
  const renameFolder = useMutation({
    mutationFn: (v: { id: number; name: string }) => api(`/folders/${v.id}/`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ name: v.name }) }),
    onSuccess: refreshTree,
    onError: fail("Couldn't rename the folder"),
  });
  const deleteFolder = useMutation({
    mutationFn: (id: number) => api(`/folders/${id}/`, { method: "DELETE" }),
    onSuccess: () => { setSelected(null); refreshTree(); },
    onError: fail("Couldn't delete the folder"),
  });
  const deleteDoc = useMutation({
    mutationFn: (id: number) => api(`/documents/${id}/`, { method: "DELETE" }),
    onSuccess: () => {
      setSelected(null);
      refreshTree();
    },
    onError: fail("Couldn't delete the file"),
  });
  const renameDoc = useMutation({
    mutationFn: (v: { id: number; title: string }) =>
      api(`/documents/${v.id}/`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: v.title }),
      }),
    onSuccess: refreshTree,
    onError: fail("Couldn't rename the file"),
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
    onError: fail("Couldn't move the file"),
  });
  // #556: the action bar's verbs, one endpoint; manuscript sources come back as `skipped`
  const bulk = useMutation({
    mutationFn: ({ ids, ...v }: { action: "move" | "tag" | "untag" | "duplicate" | "delete"; folder?: number | null; tag?: number; ids?: number[] }) =>
      api<{ action: string; count: number; skipped: number[]; created?: number[] }>(`/projects/${slug}/documents/bulk/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ids: ids ?? [...checked], ...v }), // #560: a drag passes its own ids
      }),
    onSuccess: (r) => {
      refreshTree();
      if (r.action === "delete") setChecked(new Set());
      // #560: the copies become the selection, so a second verb (move, tag) acts on them
      if (r.action === "duplicate") { setChecked(new Set(r.created ?? [])); setSelected(null); }
      setSelected((s) => (s && checked.has(s.id) && r.action !== "tag" && r.action !== "untag" && r.action !== "duplicate" ? null : s));
      if (r.skipped.length) void noticeDialog({ title: `${r.skipped.length} file${r.skipped.length === 1 ? "" : "s"} skipped`, body: "Manuscript sources are managed in the LaTeX editor; the rest were handled." });
    },
    onError: fail("Couldn't apply that to the selection"),
  });
  const downloadUrl = (url: string) => { const a = document.createElement("a"); a.href = url; a.download = ""; a.click(); };
  const bulkZip = () => downloadUrl(`/api/v1/projects/${slug}/archive/?ids=${[...checked].join(",")}`);
  const bulkMoveItems = (): MenuItem[] => [
    { label: "(project root)", icon: <Folder className="h-3.5 w-3.5" />, onSelect: () => bulk.mutate({ action: "move", folder: null }) },
    ...(data?.folders ?? []).filter((f) => !f.name.startsWith("manuscript-")).map((f): MenuItem => ({ label: f.name, icon: <Folder className="h-3.5 w-3.5" />, onSelect: () => bulk.mutate({ action: "move", folder: f.id }) })),
  ];
  const bulkTagItems = (): MenuItem[] => [
    ...(tagsQ.data?.results ?? []).map((t): MenuItem => ({ label: t.name, icon: <TagDot color={t.color} />, onSelect: () => { bulk.mutate({ action: "tag", tag: t.id }); setSelected((s) => (s && checked.has(s.id) && !s.tags.some((x) => x.id === t.id) ? { ...s, tags: [...s.tags, t] } : s)); } })),
    ...((tagsQ.data?.results ?? []).length ? ["-" as const] : []),
    { label: "New tag…", icon: <FilePlus2 className="h-3.5 w-3.5" />, onSelect: async () => {
      const name = await promptDialog({ title: "New tag", label: "Name", placeholder: "e.g. key-paper", validate: (v) => (v.trim() ? null : "Name the tag.") });
      if (!name) return;
      const wanted = name.trim();
      let tag = (tagsQ.data?.results ?? []).find((t) => t.name.toLowerCase() === wanted.toLowerCase());
      if (!tag) {
        try { tag = await api<Tag>(`/tags/`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ project: slug, name: wanted, color: tagColor(wanted) }) }); }
        catch (e) { void errorDialog("Couldn't create the tag", e); return; }
        queryClient.invalidateQueries({ queryKey: ["doc-tags", slug] });
      }
      bulk.mutate({ action: "tag", tag: tag.id });
    } },
  ];
  const askBulkDelete = async () => {
    const n = checked.size;
    if (await confirmDialog({ title: `Delete ${n} file${n === 1 ? "" : "s"}?`, danger: true, confirmLabel: `Delete ${n}`, body: "They are removed from the project and from disk, with their histories." })) bulk.mutate({ action: "delete" });
  };

  // #554: description + tags edited in the pane (PATCH by tag ids; the tree refreshes its rows)
  const patchMeta = useMutation({
    mutationFn: (v: { id: number; body: { description?: string; tags?: number[] } }) =>
      api(`/documents/${v.id}/`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(v.body) }),
    onSuccess: () => refreshTree(),
    onError: fail("Couldn't save the file's details"),
  });
  const editDescription = async (f: FileNode) => {
    const d = await promptDialog({ title: `Describe “${f.name}”`, label: "What is this file?", initial: f.description, multiline: true, placeholder: "e.g. Per-trial reaction times from the pilot (ms)." });
    if (d === null || d === f.description) return;
    try { await patchMeta.mutateAsync({ id: f.id, body: { description: d } }); } catch { return; }
    setSelected((s) => (s && s.id === f.id ? { ...s, description: d } : s));
  };
  const setTags = async (f: FileNode, tags: Tag[]) => {
    try { await patchMeta.mutateAsync({ id: f.id, body: { tags: tags.map((t) => t.id) } }); } catch { return; }
    setSelected((s) => (s && s.id === f.id ? { ...s, tags } : s));
  };
  const newTag = async (f: FileNode) => {
    const name = await promptDialog({ title: "New tag", label: "Name", placeholder: "e.g. key-paper", validate: (v) => (v.trim() ? null : "Name the tag.") });
    if (!name) return;
    const wanted = name.trim();
    // the name is unique per project: reuse a match (any case) instead of a 400 from the server
    const existing = (tagsQ.data?.results ?? []).find((t) => t.name.toLowerCase() === wanted.toLowerCase());
    let tag = existing;
    if (!tag) {
      try {
        tag = await api<Tag>(`/tags/`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ project: slug, name: wanted, color: tagColor(wanted) }) });
      } catch (e) { void errorDialog("Couldn't create the tag", e); return; }
      queryClient.invalidateQueries({ queryKey: ["doc-tags", slug] });
    }
    if (!f.tags.some((t) => t.id === tag!.id)) await setTags(f, [...f.tags, tag]);
  };
  // #559 (backlog 354): manage a tag where it is used — from its chip in the filter row
  const tagPool = () => tagsQ.data?.results ?? [];
  const tagCount = (t: Tag) => tagPool().find((x) => x.id === t.id)?.count ?? t.count ?? 0;
  const filesLabel = (n: number) => `${n} file${n === 1 ? "" : "s"}`;
  const tagTouched = () => { refreshTree(); queryClient.invalidateQueries({ queryKey: ["doc-tags", slug] }); };
  const patchTag = (id: number, body: Record<string, string>) => api<Tag>(`/tags/${id}/`, { method: "PATCH", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body) });
  const mergeTag = async (t: Tag, into: Tag) => {
    try { await api(`/tags/${t.id}/merge/`, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ into: into.id }) }); } catch (e) { void errorDialog("Couldn't merge the tags", e); return; }
    setTagFilter((cur) => (cur.includes(into.name) ? cur.filter((n) => n !== t.name) : cur.map((n) => (n === t.name ? into.name : n))));
    setSelected((s) => (s && s.tags.some((x) => x.id === t.id) ? { ...s, tags: [...s.tags.filter((x) => x.id !== t.id && x.id !== into.id), into] } : s));
    tagTouched();
  };
  const renameTag = async (t: Tag) => {
    const name = await promptDialog({ title: `Rename the tag “${t.name}”`, label: "Name", initial: t.name, validate: (v) => (v.trim() ? null : "Name the tag.") });
    if (!name) return;
    const wanted = name.trim();
    if (wanted === t.name) return;
    // the same name in any case is the tag the explorer would have reused: offer the merge
    const clash = tagPool().find((x) => x.id !== t.id && x.name.toLowerCase() === wanted.toLowerCase());
    if (clash) {
      if (await confirmDialog({ title: `A tag named “${clash.name}” already exists`, confirmLabel: `Merge into ${clash.name}`, body: `Merge “${t.name}” into it? ${filesLabel(tagCount(t))} will carry “${clash.name}” instead.` })) await mergeTag(t, clash);
      return;
    }
    try { await patchTag(t.id, { name: wanted }); } catch (e) { void errorDialog("Couldn't rename the tag", e); return; }
    setTagFilter((cur) => cur.map((n) => (n === t.name ? wanted : n)));
    setSelected((s) => (s ? { ...s, tags: s.tags.map((x) => (x.id === t.id ? { ...x, name: wanted } : x)) } : s));
    tagTouched();
  };
  const recolourTag = async (t: Tag, color: string) => {
    try { await patchTag(t.id, { color }); } catch (e) { void errorDialog("Couldn't recolour the tag", e); return; }
    setSelected((s) => (s ? { ...s, tags: s.tags.map((x) => (x.id === t.id ? { ...x, color } : x)) } : s));
    tagTouched();
  };
  const deleteTag = async (t: Tag) => {
    const n = tagCount(t);
    if (!(await confirmDialog({ title: `Delete the tag “${t.name}”?`, danger: true, confirmLabel: "Delete tag", body: n ? `It is on ${filesLabel(n)}; they keep their other tags.` : "No file carries it." }))) return;
    try { await api(`/tags/${t.id}/`, { method: "DELETE" }); } catch (e) { void errorDialog("Couldn't delete the tag", e); return; }
    setTagFilter((cur) => cur.filter((x) => x !== t.name));
    setSelected((s) => (s ? { ...s, tags: s.tags.filter((x) => x.id !== t.id) } : s));
    tagTouched();
  };
  type At = { clientX: number; clientY: number; preventDefault: () => void };
  const tagMenuItems = (t: Tag, at: At): MenuItem[] => {
    const others = tagPool().filter((x) => x.id !== t.id);
    const n = tagCount(t);
    const only = tagFilter.length === 1 && tagFilter[0] === t.name;
    return [
      { label: only ? "Show every file" : "Only this tag", onSelect: () => setTagFilter(only ? [] : [t.name]) },
      "-",
      { label: "Rename…", icon: <Pencil className="h-3.5 w-3.5" />, onSelect: () => void renameTag(t) },
      { label: "Colour…", icon: <TagDot color={t.color} />, onSelect: () => menu.open(at, TAG_COLOURS.map(([label, hex]): MenuItem => ({ label, icon: <TagDot color={hex} />, hint: hex === t.color ? "current" : undefined, onSelect: () => void recolourTag(t, hex) }))) },
      { label: "Merge into…", disabled: others.length === 0, onSelect: () => menu.open(at, others.map((o): MenuItem => ({ label: o.name, icon: <TagDot color={o.color} />, hint: filesLabel(o.count ?? 0), onSelect: async () => { if (await confirmDialog({ title: `Merge “${t.name}” into “${o.name}”?`, confirmLabel: "Merge", body: `${filesLabel(n)} will carry “${o.name}” instead, and “${t.name}” is removed.` })) await mergeTag(t, o); } }))) },
      "-",
      { label: "Delete tag…", icon: <Trash2 className="h-3.5 w-3.5" />, danger: true, hint: filesLabel(n), onSelect: () => void deleteTag(t) },
    ];
  };
  const tagItems = (f: FileNode): MenuItem[] => {
    const have = new Set(f.tags.map((t) => t.id));
    const pool = (tagsQ.data?.results ?? []).filter((t) => !have.has(t.id));
    return [
      ...pool.map((t): MenuItem => ({ label: t.name, icon: <TagDot color={t.color} />, onSelect: () => void setTags(f, [...f.tags, t]) })),
      ...(pool.length ? ["-" as const] : []),
      { label: "New tag…", icon: <FilePlus2 className="h-3.5 w-3.5" />, onSelect: () => void newTag(f) },
    ];
  };
  const saveTemplate = useMutation({
    mutationFn: (name: string) =>
      api(`/projects/${slug}/save-template/`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name }),
      }),
    onSuccess: () => void noticeDialog({ title: "Template saved", body: "Pick it under Scaffold when creating a project." }),
    onError: fail("Couldn't save the template"),
  });
  // #553: a newer version of a file — the node stays, the old bytes go to its history
  const replacePicker = useRef<HTMLInputElement>(null);
  const replaceTarget = useRef<FileNode | null>(null);
  const [historyFor, setHistoryFor] = useState<number | null>(null);
  const replaceDoc = useMutation({
    mutationFn: async ({ file, upload }: { file: FileNode; upload: globalThis.File }) => {
      const note = await promptDialog({ title: `Replace “${file.name}” with ${upload.name}`, label: "What changed? (optional)", placeholder: "e.g. re-exported after excluding participant 7", initial: "" });
      if (note === null) return null;
      const fd = new FormData();
      fd.append("file", upload);
      if (note.trim()) fd.append("note", note.trim().slice(0, 200));
      return api<{ id: number; version: number }>(`/documents/${file.id}/replace/`, { method: "POST", body: fd });
    },
    onSuccess: async (r, { file }) => {
      if (!r) return;
      await refreshTree();
      setSelected((s) => (s && s.id === file.id ? { ...s, version: r.version, versions: s.versions + 1 } : s));
      queryClient.invalidateQueries({ queryKey: ["file-content", file.id] });
      setHistoryFor(file.id);
    },
    onError: fail("Couldn't replace the file"),
  });
  const askReplace = (f: FileNode) => { replaceTarget.current = f; replacePicker.current?.click(); };
  const isDesktop = typeof window !== "undefined" && "__TAURI__" in window;
  type LocalFile = { name: string; path: string; size: number; content: string | null; data_b64: string };
  const [localFile, setLocalFile] = useState<LocalFile | null>(null);
  const openFromDisk = async () => {
    try {
      const tauri = (await import("@tauri-apps/api")) as unknown as { core: { invoke: (c: string) => Promise<LocalFile | null> } };
      const f = await tauri.core.invoke("open_local_file");
      if (f) { setLocalFile(f); setSelected(null); }
    } catch (e) {
      // the desktop shell refusing (an ACL miss on an old build, a >25 MB file) must be visible
      void errorDialog("Couldn't open a file from disk", e);
    }
  };
  // "Add to this project": the picked bytes become a document in the chosen folder
  const addLocalFile = async (f: LocalFile, folder: number | null) => {
    const bytes = Uint8Array.from(atob(f.data_b64), (c) => c.charCodeAt(0));
    const fd = new FormData();
    fd.append("files", new Blob([bytes]), f.name);
    if (folder != null) fd.append("folder", String(folder));
    try { await api(`/projects/${slug}/upload-file/`, { method: "POST", body: fd }); setLocalFile(null); refreshTree(); }
    catch (e) { void errorDialog("Couldn't add the file", e); }
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
  const [dropFolder, setDropFolder] = useState<number | null>(null);
  // #410: a file row being dragged inside the tree (moves on drop); OS files still upload
  const [dragDoc, setDragDoc] = useState<FileNode | null>(null);
  const DOC_MIME = "application/x-atlas-doc";
  // #560: a checked row drags the whole selection (Finder); an unchecked row drags alone
  const dragIds = (f: FileNode): number[] => (checked.has(f.id) ? [...checked] : [f.id]);
  // the ids from a drop, minus the ones already in the target; null when it was not a row drag
  const droppedIds = (dt: DataTransfer, target: number | null): number[] | null => {
    const raw = dt.getData(DOC_MIME);
    if (!raw) return null;
    const ids = raw.split(",").map(Number).filter(Boolean);
    const here = new Set((target == null ? rootFiles : folderFiles[target] ?? []).map((x) => x.id));
    return ids.filter((id) => !here.has(id));
  };
  const dropMove = (ids: number[], folder: number | null) => {
    setDragDoc(null);
    if (!ids.length) return;
    if (ids.length === 1) moveDoc.mutate({ id: ids[0], folder });
    else bulk.mutate({ action: "move", folder, ids });
  };
  const upload = useMutation({
    mutationFn: async ({ files, folder }: { files: File[]; folder: number | null }) => { // File[] on purpose: a FileList empties once the picker resets
      // #553: a same-name file in the target folder is never a silent duplicate — ask
      const here = (folder == null ? rootFiles : folderFiles[folder] ?? []).map((x) => x.name);
      const clashes = Array.from(files).map((f) => f.name).filter((n) => here.includes(n));
      let onConflict = "keep";
      if (clashes.length) {
        const replace = await confirmDialog({ title: clashes.length === 1 ? `“${clashes[0]}” is already here` : `${clashes.length} of these files are already here`, confirmLabel: "Replace (keeps history)", cancelLabel: "Keep both", body: "Replace puts the new bytes on the existing file and keeps the old version in its history; Keep both adds the upload under a numbered name." });
        onConflict = replace ? "replace" : "keep";
      }
      const fd = new FormData();
      for (const f of Array.from(files)) fd.append("files", f);
      if (folder != null) fd.append("folder", String(folder));
      fd.append("on_conflict", onConflict);
      return api<{ created: string[]; replaced: { id: number; name: string; version: number }[]; renamed: string[] }>(`/projects/${slug}/upload-file/`, { method: "POST", body: fd });
    },
    onSuccess: (r, v) => {
      if (v.folder != null) setExpanded((e) => ({ ...e, [v.folder as number]: true }));
      refreshTree();
      for (const x of r.replaced ?? []) queryClient.invalidateQueries({ queryKey: ["file-content", x.id] });
      if (r.replaced?.length) setSelected((s) => { const hit = r.replaced.find((x) => s && x.id === s.id); return s && hit ? { ...s, version: hit.version, versions: s.versions + 1 } : s; });
    },
    onError: fail("Upload failed"),
  });
  // hidden picker for "Upload here…" (context menu) — the target folder is remembered
  const picker = useRef<HTMLInputElement>(null);
  const pickTarget = useRef<number | null>(null);
  const pickFiles = (folder: number | null) => { pickTarget.current = folder; picker.current?.click(); };
  const menu = useMenu();

  // --- actions (one definition, reached from right-click, ⋯ and the detail pane) ----------
  const isManuscriptFolder = (f: FolderNode) => f.name.startsWith("manuscript-");
  const askNewFolder = async (parent: number | null, parentName?: string) => {
    const name = await promptDialog({ title: parentName ? `New folder in ${parentName}` : "New folder", label: "Name", placeholder: "e.g. data, drafts, figures", validate: (v) => (v.trim() ? null : "Give the folder a name.") });
    if (name) newFolder.mutate({ name: name.trim(), parent });
  };
  const askRenameFolder = async (f: FolderNode) => {
    const name = await promptDialog({ title: "Rename folder", label: "Name", initial: f.name, validate: (v) => (v.trim() ? null : "A folder needs a name.") });
    if (name && name.trim() !== f.name) renameFolder.mutate({ id: f.id, name: name.trim() });
  };
  const askDeleteFolder = async (f: FolderNode) => {
    const inside = countInside(f.id);
    const ok = await confirmDialog({ title: `Delete the folder “${f.name}”?`, danger: true, confirmLabel: "Delete folder", body: inside ? <>It holds <b>{inside} item{inside === 1 ? "" : "s"}</b>. Files inside move to the project root; subfolders are deleted with it.</> : "The folder is empty." });
    if (ok) deleteFolder.mutate(f.id);
  };
  const askRenameFile = async (f: FileNode) => {
    const title = await promptDialog({ title: "Rename file", label: "Name", initial: f.name, validate: (v) => (v.trim() ? null : "A file needs a name.") });
    if (title && title.trim() !== f.name) renameDoc.mutate({ id: f.id, title: title.trim() });
  };
  const askDeleteFile = async (f: FileNode) => {
    if (await confirmDialog({ title: `Delete “${f.name}”?`, danger: true, confirmLabel: "Delete file", body: "The file is removed from the project and from disk." })) deleteDoc.mutate(f.id);
  };
  // #560: a copy next to the original (numbered name, description + tags, no history); the
  // selection wins over the focused row, like Delete
  const duplicate = (f?: FileNode) => {
    const ids = f && !(checked.has(f.id) && checked.size > 1) ? [f.id] : [...checked];
    if (ids.length) bulk.mutate({ action: "duplicate", ids });
  };
  const copyText = async (text: string) => { try { await navigator.clipboard.writeText(text); } catch { void noticeDialog({ title: "Copy blocked", body: <code className="text-xs">{text}</code> }); } };
  const fileItems = (f: FileNode): MenuItem[] => {
    const ms = f.role === "manuscript_source";
    const raw = `/api/v1/documents/${f.id}/raw/?v=${f.version}`;
    return [
      { label: "Open", icon: <File className="h-3.5 w-3.5" />, hint: "↵", onSelect: () => setSelected(f) },
      // the desktop webview has no tabs — window.open would spawn a bare window without the session
      ...(isDesktop ? [] : [{ label: "Open in a new tab", icon: <ExternalLink className="h-3.5 w-3.5" />, onSelect: () => window.open(raw, "_blank", "noopener") }]),
      // desktop: hand the stored file to the operating system
      ...(isDesktop && f.local_path ? [
        { label: "Open with the system app", icon: <ExternalLink className="h-3.5 w-3.5" />, onSelect: async () => { try { await openPath(f.local_path!); } catch (e) { void errorDialog("Couldn't open the file", e); } } },
        { label: "Show in folder", icon: <FolderOpen className="h-3.5 w-3.5" />, onSelect: async () => { try { await revealPath(f.local_path!); } catch (e) { void errorDialog("Couldn't show the file", e); } } },
      ] : []),
      { label: "Download", icon: <Download className="h-3.5 w-3.5" />, onSelect: () => { const a = document.createElement("a"); a.href = raw; a.download = f.name; a.click(); } },
      { label: "Copy path", icon: <Copy className="h-3.5 w-3.5" />, onSelect: () => void copyText(isDesktop && f.local_path ? f.local_path : f.rel_path) },
      "-",
      { label: "Replace with a newer version…", icon: <Upload className="h-3.5 w-3.5" />, disabled: ms, onSelect: () => askReplace(f) },
      { label: f.versions ? `History (${f.versions})` : "History", icon: <History className="h-3.5 w-3.5" />, disabled: ms, onSelect: () => { setSelected(f); setHistoryFor(f.id); } },
      { label: "Rename…", icon: <Pencil className="h-3.5 w-3.5" />, hint: "F2", disabled: ms, onSelect: () => void askRenameFile(f) },
      { label: checked.has(f.id) && checked.size > 1 ? `Duplicate ${checked.size} files` : "Duplicate", icon: <Copy className="h-3.5 w-3.5" />, hint: `${MOD} D`, disabled: ms, onSelect: () => duplicate(f) },
      { label: "Delete…", icon: <Trash2 className="h-3.5 w-3.5" />, hint: "Del", danger: true, disabled: ms, onSelect: () => void askDeleteFile(f) },
    ];
  };
  const folderItems = (f: FolderNode): MenuItem[] => {
    const ms = isManuscriptFolder(f);
    return [
      { label: "New folder inside…", icon: <FolderPlus className="h-3.5 w-3.5" />, disabled: ms, onSelect: () => void askNewFolder(f.id, f.name) },
      { label: "Upload here…", icon: <Upload className="h-3.5 w-3.5" />, disabled: ms, onSelect: () => pickFiles(f.id) },
      { label: "Download as zip", icon: <Archive className="h-3.5 w-3.5" />, onSelect: () => downloadUrl(`/api/v1/projects/${slug}/archive/?folder=${f.id}`) },
      "-",
      { label: "Rename…", icon: <Pencil className="h-3.5 w-3.5" />, hint: "F2", disabled: ms, onSelect: () => void askRenameFolder(f) },
      { label: "Delete…", icon: <Trash2 className="h-3.5 w-3.5" />, hint: "Del", danger: true, disabled: ms, onSelect: () => void askDeleteFolder(f) },
    ];
  };
  const blankItems = (): MenuItem[] => [
    { label: "New folder…", icon: <FolderPlus className="h-3.5 w-3.5" />, onSelect: () => void askNewFolder(null) },
    { label: "Upload files…", icon: <FilePlus2 className="h-3.5 w-3.5" />, onSelect: () => pickFiles(null) },
    "-",
    { label: "Refresh", icon: <RefreshCw className="h-3.5 w-3.5" />, onSelect: () => void refreshTree() },
  ];

  const { childFolders, folderFiles, rootFolders, rootFiles } = useMemo(() => {
    const cf: Record<number, FolderNode[]> = {};
    const ff: Record<number, FileNode[]> = {};
    const rootFolders: FolderNode[] = [];
    const rootFiles: FileNode[] = [];
    // #554: with a tag filter only the files carrying it and the folders above them remain
    const shown = filtering ? (data?.files ?? []).filter((f) => tagFilter.every((n) => f.tags.some((t) => t.name === n))) : (data?.files ?? []);
    const keep = new Set<number>();
    if (filtering) {
      const parentOf = new Map((data?.folders ?? []).map((f) => [f.id, f.parent_id] as const));
      for (const f of shown) {
        let id = f.folder_id;
        while (id != null && !keep.has(id)) { keep.add(id); id = parentOf.get(id) ?? null; }
      }
    }
    for (const f of data?.folders ?? []) {
      if (filtering && !keep.has(f.id)) continue;
      if (f.parent_id == null) rootFolders.push(f);
      else (cf[f.parent_id] ??= []).push(f);
    }
    for (const f of shown) {
      if (f.folder_id == null) rootFiles.push(f);
      else (ff[f.folder_id] ??= []).push(f);
    }
    const byName = <T extends { name: string }>(a: T, b: T) => a.name.localeCompare(b.name);
    // #557: newest change first, largest first; ties fall back to the name
    const byFile = (a: FileNode, b: FileNode) =>
      sort === "modified" ? (b.modified_at.localeCompare(a.modified_at) || byName(a, b))
      : sort === "size" ? ((b.size - a.size) || byName(a, b))
      : byName(a, b);
    rootFolders.sort(byName);
    rootFiles.sort(byFile);
    Object.values(cf).forEach((l) => l.sort(byName));
    Object.values(ff).forEach((l) => l.sort(byFile));
    return { childFolders: cf, folderFiles: ff, rootFolders, rootFiles };
  }, [data, tagFilter, filtering, sort]);
  const countInside = (id: number): number => (folderFiles[id]?.length ?? 0) + (childFolders[id] ?? []).reduce((n, k) => n + 1 + countInside(k.id), 0);

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
      if (isOpen(f.id)) {
        kids.forEach((k) => walk(k, depth + 1));
        files.forEach((fl) => out.push({ kind: "file", id: fl.id, depth: depth + 1, file: fl }));
      }
    };
    rootFolders.forEach((f) => walk(f, 0));
    rootFiles.forEach((fl) => out.push({ kind: "file", id: fl.id, depth: 0, file: fl }));
    return out;
  }, [childFolders, folderFiles, rootFolders, rootFiles, expanded, filtering]);

  const [focusIdx, setFocusIdx] = useState(0);
  // #556: a multi-selection of file rows (checkbox, shift-click range, space, ⌘A) with an
  // action bar: zip, move, tag, delete. Pruned to the files the tree currently shows.
  const [checked, setChecked] = useState<Set<number>>(() => new Set());
  const anchorRef = useRef<number | null>(null);
  const shownIds = useMemo(() => new Set([...rootFiles, ...Object.values(folderFiles).flat()].map((f) => f.id)), [rootFiles, folderFiles]);
  useEffect(() => {
    setChecked((c) => {
      const kept = new Set([...c].filter((id) => shownIds.has(id)));
      return kept.size === c.size ? c : kept;
    });
  }, [shownIds]);
  const toggleCheck = (f: FileNode, shift: boolean) => {
    const idx = flat.findIndex((r) => r.kind === "file" && r.id === f.id);
    setChecked((c) => {
      const n = new Set(c);
      if (shift && anchorRef.current != null && idx >= 0) {
        const [a, b] = [Math.min(anchorRef.current, idx), Math.max(anchorRef.current, idx)];
        for (const r of flat.slice(a, b + 1)) if (r.kind === "file") n.add(r.id);
      } else if (n.has(f.id)) n.delete(f.id);
      else n.add(f.id);
      return n;
    });
    if (!shift || anchorRef.current == null) anchorRef.current = idx;
  };
  const checkAllVisible = () => setChecked(new Set(flat.filter((r) => r.kind === "file").map((r) => r.id)));
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
  const [typedMiss, setTypedMiss] = useState(false); // #402 (backlog #185): no row matches → the hint shakes red
  const rowName = (r: FlatRow) => (r.kind === "folder" ? r.folder.name : r.file.name);
  const clearTypeahead = () => {
    typeahead.current.buffer = "";
    setTypedHint("");
    setTypedMiss(false);
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
      if (rowName(flat[idx]).toLowerCase().startsWith(q)) { setFocusIdx(idx); setTypedMiss(false); return; }
    }
    setTypedMiss(true);
  };

  const onTreeKey = (e: {
    key: string;
    ctrlKey?: boolean;
    metaKey?: boolean;
    altKey?: boolean;
    target?: EventTarget | null;
    currentTarget?: EventTarget | null;
    preventDefault: () => void;
  }) => {
    // a control inside the tree (the sort select, a tag chip, the bar, a checkbox, a Recent row)
    // keeps its own keys — the tree's navigation only runs on the tree itself
    if (e.target !== e.currentTarget && (e.target as HTMLElement | null)?.closest?.("button, select, input, a")) return;
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
    if (e.key === " " && r?.kind === "file") { e.preventDefault(); toggleCheck(r.file, false); return; }
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "a") { e.preventDefault(); checkAllVisible(); return; }
    if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "d") { e.preventDefault(); if (checked.size) duplicate(); else if (r?.kind === "file" && r.file.role !== "manuscript_source") duplicate(r.file); return; }
    if (e.key === "Escape" && checked.size) { e.preventDefault(); setChecked(new Set()); return; }
    if (e.key === "F2" && r) { e.preventDefault(); if (r.kind === "file") void askRenameFile(r.file); else void askRenameFolder(r.folder); return; }
    if ((e.key === "Delete" || e.key === "Backspace") && checked.size) { e.preventDefault(); void askBulkDelete(); return; } // the selection wins
    if ((e.key === "Delete" || e.key === "Backspace") && r) { e.preventDefault(); if (r.kind === "file") void askDeleteFile(r.file); else void askDeleteFolder(r.folder); return; }
    if (e.key === "ArrowDown") { e.preventDefault(); setFocusIdx((i) => Math.min(flat.length - 1, i + 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setFocusIdx((i) => Math.max(0, i - 1)); }
    else if (e.key === "Enter") {
      e.preventDefault();
      if (r?.kind === "file") setSelected(r.file);
      else if (r?.kind === "folder") setExpanded((x) => ({ ...x, [r.id]: !(x[r.id] ?? filtering) }));
    } else if (e.key === "ArrowRight" && r?.kind === "folder") {
      if (r.hasChildren && !isOpen(r.id)) { e.preventDefault(); setExpanded((x) => ({ ...x, [r.id]: true })); }
      else { e.preventDefault(); setFocusIdx((i) => Math.min(flat.length - 1, i + 1)); }
    } else if (e.key === "ArrowLeft" && r?.kind === "folder" && isOpen(r.id)) {
      e.preventDefault();
      setExpanded((x) => ({ ...x, [r.id]: false }));
    }
  };

  if (isLoading)
    return (
      <div role="status" aria-label="Loading">
        <Skeleton className="mb-4 h-4 w-44" />
        <div className="mb-4">
          <Skeleton className="mb-2 h-7 w-32" />
          <Skeleton className="h-4 w-48" />
        </div>
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
          <div className="col-span-1 rounded border border-stone-200 bg-white p-3 dark:border-stone-800 dark:bg-stone-900">
            <Skeleton className="mb-3 h-3 w-20" />
            <div className="space-y-2">
              {Array.from({ length: 8 }).map((_, i) => (
                <div key={i} style={{ paddingLeft: (i % 3) * 14 }}>
                  <Skeleton className="h-4" />
                </div>
              ))}
            </div>
          </div>
          <div className="card col-span-1 lg:col-span-2 lg:min-h-[40vh]">
            <Skeleton className="mb-3 h-4 w-1/3" />
            <Skeleton className="h-[40vh] w-full" />
          </div>
        </div>
      </div>
    );
  if (error || !data) return <ErrorState message="Couldn't load the file tree." onRetry={() => refetch()} />;

  const fileRow = (f: FileNode, depth: number) => (
    <div
      key={`f${f.id}`}
      role="treeitem"
      aria-selected={selected?.id === f.id}
      data-tree-focus={focusKey === `file${f.id}`}
      data-testid="tree-file"
      data-dragging={dragDoc?.id === f.id || (dragDoc != null && checked.has(dragDoc.id) && checked.has(f.id)) ? "1" : undefined}
      draggable={f.role !== "manuscript_source"}
      title={`changed ${stamp(f.modified_at)} · added ${stamp(f.created_at)}${f.role !== "manuscript_source" ? " · drag onto a folder to move it" : ""}`}
      onDragStart={(e) => { if (f.role === "manuscript_source") { e.preventDefault(); return; } e.dataTransfer.setData(DOC_MIME, dragIds(f).join(",")); e.dataTransfer.effectAllowed = "move"; setDragDoc(f); }}
      onDragEnd={() => { setDragDoc(null); setDropFolder(null); setDragging(false); }}
      onClick={() => { setSelected(f); setFocusIdx(flat.findIndex((r) => r.kind === "file" && r.id === f.id)); }}
      onContextMenu={(e) => { setFocusIdx(flat.findIndex((r) => r.kind === "file" && r.id === f.id)); menu.open(e, fileItems(f)); }}
      style={{ paddingLeft: depth * 14 + 8 }}
      className={`group flex w-full cursor-pointer items-center gap-2 rounded py-1 pr-1 text-left text-sm hover:bg-stone-50 dark:hover:bg-stone-800 ${dragDoc?.id === f.id ? "opacity-40" : ""} ${focusKey === `file${f.id}` ? "ring-1 ring-indigo-200" : ""} ${selected?.id === f.id ? "bg-indigo-50 font-medium text-indigo-700 dark:bg-indigo-500/15 dark:text-indigo-300" : checked.has(f.id) ? "bg-indigo-50/60 text-stone-700 dark:bg-indigo-500/10 dark:text-stone-300" : "text-stone-700 dark:text-stone-300"}`}
    >
      <input
        type="checkbox"
        checked={checked.has(f.id)}
        onChange={() => undefined}
        onClick={(e) => { e.stopPropagation(); setFocusIdx(flat.findIndex((r) => r.kind === "file" && r.id === f.id)); toggleCheck(f, e.shiftKey); }}
        aria-label={`Select ${f.name}`}
        className={`h-3.5 w-3.5 shrink-0 cursor-pointer accent-indigo-600 ${checked.size ? "" : "opacity-0 group-hover:opacity-100 focus:opacity-100 pointer-coarse:opacity-100"}`}
        data-testid="file-check"
      />
      <Icon kind={f.kind || "other"} name={f.name} />
      <span className="min-w-0 flex-1 truncate">{f.name}</span>
      {f.tags.length > 0 && (
        <span className="flex shrink-0 items-center gap-0.5" title={f.tags.map((t) => t.name).join(", ")} data-testid="tag-dots">
          {f.tags.map((t) => <TagDot key={t.id} color={t.color} />)}
        </span>
      )}
      {f.role === "manuscript_source" && (
        <span className="shrink-0 rounded bg-stone-100 px-1 text-[10px] uppercase tracking-wide text-stone-400 dark:bg-stone-800">ms</span>
      )}
      {f.versions > 0 && <span className="shrink-0 rounded bg-indigo-500/10 px-1 font-mono text-[10px] text-indigo-600 dark:text-indigo-300" title={`${f.versions} earlier version${f.versions === 1 ? "" : "s"} in its history`} data-testid="version-chip">v{f.version}</span>}
      {sort === "modified"
        ? <span className="shrink-0 text-[10px] text-stone-400" data-testid="row-stamp">{ago(f.modified_at)}</span>
        : <span className="shrink-0 font-mono text-[11px] text-stone-400">{humanSize(f.size)}</span>}
      <Kebab items={fileItems(f)} label={`Actions for ${f.name}`} className="h-5 w-5 opacity-0 group-hover:opacity-100 focus:opacity-100" />
    </div>
  );

  const folderRow = (folder: FolderNode, depth: number) => {
    const open = isOpen(folder.id);
    const kids = childFolders[folder.id] ?? [];
    const files = folderFiles[folder.id] ?? [];
    return (
      <div key={`d${folder.id}`}>
        <div
          role="treeitem"
          aria-expanded={!!open}
          data-tree-focus={focusKey === `folder${folder.id}`}
          data-testid="tree-folder"
          onClick={() => { setExpanded((e) => ({ ...e, [folder.id]: !(e[folder.id] ?? filtering) })); setFocusIdx(flat.findIndex((r) => r.kind === "folder" && r.id === folder.id)); }}
          onContextMenu={(e) => { setFocusIdx(flat.findIndex((r) => r.kind === "folder" && r.id === folder.id)); menu.open(e, folderItems(folder)); }}
          onDragOver={(e) => { if (!isManuscriptFolder(folder)) { e.preventDefault(); e.stopPropagation(); e.dataTransfer.dropEffect = dragDoc ? "move" : "copy"; setDropFolder(folder.id); } }}
          onDragLeave={() => setDropFolder((d) => (d === folder.id ? null : d))}
          onDrop={(e) => {
            if (isManuscriptFolder(folder)) return;
            e.preventDefault(); e.stopPropagation(); setDragging(false); setDropFolder(null);
            const moved = droppedIds(e.dataTransfer, folder.id);
            if (moved) { dropMove(moved, folder.id); return; }
            if (e.dataTransfer.files.length) upload.mutate({ files: Array.from(e.dataTransfer.files), folder: folder.id });
          }}
          style={{ paddingLeft: depth * 14 + 8 }}
          className={`group flex w-full cursor-pointer items-center gap-2 rounded py-1 pr-1 text-left text-sm text-stone-700 hover:bg-stone-50 dark:text-stone-300 dark:hover:bg-stone-800 ${focusKey === `folder${folder.id}` ? "ring-1 ring-indigo-200" : ""} ${dropFolder === folder.id ? "bg-indigo-50 ring-1 ring-indigo-300 dark:bg-indigo-500/15" : ""}`}
        >
          <span className="w-3 shrink-0 text-xs text-stone-400">{kids.length || files.length ? (open ? "▾" : "▸") : ""}</span>
          <Icon kind="folder" open={open} />
          <span className="min-w-0 flex-1 truncate font-medium">{folder.name}</span>
          <Kebab items={folderItems(folder)} label={`Actions for ${folder.name}`} className="h-5 w-5 opacity-0 group-hover:opacity-100 focus:opacity-100" />
        </div>
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
  // #554: the filter row lists the tags files actually carry (with counts), never an empty one
  const tagsInUse = (() => {
    const m = new Map<number, Tag & { count: number }>();
    for (const f of data.files) for (const t of f.tags) { const e = m.get(t.id); if (e) e.count++; else m.set(t.id, { ...t, count: 1 }); }
    return [...m.values()].sort((a, b) => a.name.localeCompare(b.name));
  })();
  // #557: the last-touched files across the project (by the bytes' last change), shown when
  // the tree is big enough for them to be worth a shortcut
  const recent = total >= 6 ? [...data.files].sort((a, b) => b.modified_at.localeCompare(a.modified_at)).slice(0, 6) : [];
  const parentOfFolder = new Map(data.folders.map((f) => [f.id, f.parent_id] as const));
  const reveal = (f: FileNode) => {
    const open: Record<number, boolean> = {};
    let id = f.folder_id;
    while (id != null) { open[id] = true; id = parentOfFolder.get(id) ?? null; }
    setExpanded((e) => ({ ...e, ...open }));
    setSelected(f);
  };
  return (
    <div>
      <nav className="mb-4 text-sm text-stone-500 dark:text-stone-400">
        <Link to="/projects" className="transition-colors hover:underline">Projects</Link> /{" "}
        <Link to={`/projects/${slug}`} className="transition-colors hover:underline">{slug}</Link> / Files
      </nav>
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-2xl font-semibold tracking-tight dark:text-stone-100">Files</h1>
          <p className="mt-0.5 text-sm text-stone-500 dark:text-stone-400">{total} file{total === 1 ? "" : "s"} · everything in one tree</p>
        </div>
        <div className="flex flex-wrap items-center gap-1.5">
          <button
            onClick={() => void askNewFolder(null)}
            className="rounded border border-stone-200 bg-white px-2 py-1 text-xs text-stone-500 transition-colors hover:border-stone-300 hover:text-indigo-700 dark:border-stone-800 dark:bg-stone-900 dark:text-stone-400 dark:hover:border-stone-700 dark:hover:text-indigo-300"
            data-testid="new-folder"
          >
            + Folder
          </button>
          <button
            onClick={() => pickFiles(null)}
            className="rounded border border-stone-200 bg-white px-2 py-1 text-xs text-stone-500 transition-colors hover:border-stone-300 hover:text-indigo-700 dark:border-stone-800 dark:bg-stone-900 dark:text-stone-400 dark:hover:border-stone-700 dark:hover:text-indigo-300"
            title="Upload files into the project root (or drop them on a folder)"
            data-testid="upload-files"
          >
            ↑ Upload
          </button>
          <input ref={picker} type="file" multiple className="hidden" aria-hidden="true" tabIndex={-1} onChange={(e) => { if (e.target.files?.length) upload.mutate({ files: Array.from(e.target.files), folder: pickTarget.current }); e.target.value = ""; }} />
          <input ref={replacePicker} type="file" className="hidden" aria-hidden="true" tabIndex={-1} data-testid="replace-picker" onChange={(e) => { const f = e.target.files?.[0]; const t = replaceTarget.current; if (f && t) replaceDoc.mutate({ file: t, upload: f }); e.target.value = ""; }} />
          <button
            onClick={async () => {
              const name = await promptDialog({ title: "Save this folder layout as a template", label: "Template name", placeholder: "e.g. Behavioural study", validate: (v) => (v.trim() ? null : "Name the template.") });
              if (name) saveTemplate.mutate(name.trim());
            }}
            className="rounded border border-stone-200 bg-white px-2 py-1 text-xs text-stone-500 transition-colors hover:border-stone-300 hover:text-indigo-700 dark:border-stone-800 dark:bg-stone-900 dark:text-stone-400 dark:hover:border-stone-700 dark:hover:text-indigo-300"
            title="Reuse this folder layout when creating new projects"
          >
            Save as template
          </button>
          <button
            onClick={() => openTerminal({ toggle: true })}
            className="flex items-center gap-1 rounded border border-stone-200 bg-white px-2 py-1 text-xs text-stone-500 transition-colors hover:border-stone-300 hover:text-indigo-700 dark:border-stone-800 dark:bg-stone-900 dark:text-stone-400 dark:hover:border-stone-700 dark:hover:text-indigo-300"
            title="Toggle the terminal dock (⌃`)"
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="4 17 10 11 4 5" /><line x1="12" y1="19" x2="20" y2="19" /></svg>
            Terminal
          </button>
          {isDesktop && (
            <button onClick={openFromDisk} className="rounded border border-stone-200 bg-white px-2 py-1 text-xs text-stone-500 transition-colors hover:border-stone-300 hover:text-indigo-700 dark:border-stone-800 dark:bg-stone-900 dark:text-stone-400 dark:hover:border-stone-700 dark:hover:text-indigo-300" title="Open any file from your computer (desktop app)">Open from disk…</button>
          )}
          <button onClick={() => setQuickOpen(true)} className="rounded border border-stone-200 bg-white px-2 py-1 font-mono text-xs text-stone-500 transition-colors hover:border-stone-300 hover:text-indigo-700 dark:border-stone-800 dark:bg-stone-900 dark:text-stone-400 dark:hover:border-stone-700 dark:hover:text-indigo-300" title="Quick open (Ctrl/Cmd-P)">⌘P</button>
        </div>
      </div>
      {quickOpen && (
        <QuickOpen
          files={data.files}
          onPick={(f) => reveal(f)}
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
          onContextMenu={(e) => menu.open(e, blankItems())}
          onDragOver={(e) => { e.preventDefault(); if (dragDoc) e.dataTransfer.dropEffect = "move"; setDragging(true); }}
          onDragLeave={() => setDragging(false)}
          onDrop={(e) => {
            e.preventDefault();
            setDragging(false);
            setDropFolder(null);
            const moved = droppedIds(e.dataTransfer, null);
            if (moved) { dropMove(moved, null); return; }
            if (e.dataTransfer.files.length) upload.mutate({ files: Array.from(e.dataTransfer.files), folder: null });
          }}
        >
          <div className="sticky top-0 z-10 -mx-2 -mt-2 mb-1 flex items-center justify-between border-b border-stone-100 bg-white px-3 py-2 text-sm font-medium uppercase tracking-wide text-stone-400 dark:border-stone-800 dark:bg-stone-900">
            <span>Explorer</span>
            <select
              value={sort}
              onChange={(e) => setSort(e.target.value as SortKey)}
              onClick={(e) => e.stopPropagation()}
              aria-label="Sort files"
              title="How files are ordered inside each folder"
              className="h-5 rounded border border-stone-200 bg-white px-1 text-[10px] font-medium normal-case tracking-normal text-stone-500 hover:border-stone-300 dark:border-stone-700 dark:bg-stone-900 dark:text-stone-400"
              data-testid="sort-files"
            >
              <option value="name">Name</option>
              <option value="modified">Last change</option>
              <option value="size">Size</option>
            </select>
          </div>
          {tagsInUse.length > 0 && (
            <div className="sticky top-9 z-10 -mx-2 mb-1.5 flex flex-wrap items-center gap-1 border-b border-stone-100 bg-white px-3 pb-1.5 dark:border-stone-800 dark:bg-stone-900" data-testid="tag-filter">
              {tagsInUse.map((t) => {
                const on = tagFilter.includes(t.name);
                const at = (x: number, y: number): At => ({ clientX: x, clientY: y, preventDefault: () => {} });
                return (
                  <span
                    key={t.id}
                    className={`inline-flex items-center rounded-full border text-[11px] transition-colors ${on ? "border-indigo-300 bg-indigo-50 text-indigo-700 dark:border-indigo-500/40 dark:bg-indigo-500/15 dark:text-indigo-300" : "border-stone-200 text-stone-500 hover:border-stone-300 hover:text-stone-700 dark:border-stone-700 dark:text-stone-400 dark:hover:text-stone-200"}`}
                    data-testid="tag-chip"
                    onContextMenu={(e) => { e.stopPropagation(); menu.open(e, tagMenuItems(t, at(e.clientX, e.clientY))); }}
                  >
                    <button
                      onClick={(e) => { e.stopPropagation(); setTagFilter((cur) => (cur.includes(t.name) ? cur.filter((n) => n !== t.name) : [...cur, t.name])); }}
                      aria-pressed={on}
                      title={on ? `Stop filtering by ${t.name}` : filtering ? `Also require ${t.name}` : `Only files tagged ${t.name} — right-click to manage the tag`}
                      className="inline-flex items-center gap-1 rounded-full px-1.5 py-0.5"
                    >
                      <TagDot color={t.color} />{t.name}<span className="font-mono text-[10px] opacity-70">{t.count}</span>
                    </button>
                    {on && (
                      <button
                        onClick={(e) => { e.stopPropagation(); const r = e.currentTarget.getBoundingClientRect(); menu.open(at(r.left, r.bottom + 4), tagMenuItems(t, at(r.left, r.bottom + 4))); }}
                        aria-label={`Manage the tag ${t.name}`}
                        title="Rename, recolour, merge or delete this tag"
                        className="mr-1 rounded-full px-0.5 opacity-70 hover:opacity-100"
                        data-testid="tag-menu"
                      >⋯</button>
                    )}
                  </span>
                );
              })}
              {filtering && <span className="text-[11px] text-stone-400" data-testid="tag-filter-count">{rootFiles.length + Object.values(folderFiles).reduce((n, l) => n + l.length, 0)} of {total}{tagFilter.length > 1 ? ` · all ${tagFilter.length} tags` : ""}</span>}
              {filtering && <button onClick={(e) => { e.stopPropagation(); setTagFilter([]); }} className="text-[11px] text-stone-400 hover:underline" data-testid="tag-filter-clear">Clear</button>}
            </div>
          )}
          {checked.size > 0 && (
            <div className="mb-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 rounded-md border border-indigo-200 bg-indigo-50 px-2 py-1 text-xs text-indigo-800 dark:border-indigo-500/40 dark:bg-indigo-500/15 dark:text-indigo-200" data-testid="bulk-bar" onClick={(e) => e.stopPropagation()}>
              <span className="font-medium" data-testid="bulk-count">{checked.size} selected</span>
              <button onClick={bulkZip} className="inline-flex items-center gap-1 hover:underline" data-testid="bulk-zip"><Archive className="h-3 w-3" aria-hidden="true" />Download zip</button>
              <button onClick={(e) => menu.open(e, bulkMoveItems())} className="hover:underline" data-testid="bulk-move" disabled={bulk.isPending}>Move to…</button>
              <button onClick={(e) => menu.open(e, bulkTagItems())} className="hover:underline" data-testid="bulk-tag" disabled={bulk.isPending}>Tag…</button>
              <button onClick={() => bulk.mutate({ action: "duplicate" })} className="hover:underline" data-testid="bulk-duplicate" disabled={bulk.isPending} title={`Copies land next to their originals and become the selection (${MOD} D)`}>Duplicate</button>
              <button onClick={() => void askBulkDelete()} className="text-red-600 hover:underline dark:text-red-300" data-testid="bulk-delete" disabled={bulk.isPending}>Delete…</button>
              <button onClick={() => setChecked(new Set())} className="ml-auto text-stone-500 hover:underline dark:text-stone-400" data-testid="bulk-clear" title="Clear the selection (Esc)">Clear</button>
            </div>
          )}
          {recent.length > 0 && !filtering && (
            <div className="mb-1.5 rounded-md border border-stone-100 bg-stone-50/60 px-2 py-1 text-xs dark:border-stone-800 dark:bg-stone-800/40" data-testid="recent-strip">
              <button onClick={(e) => { e.stopPropagation(); toggleRecent(); }} aria-expanded={recentOpen} className="flex w-full items-center gap-1 text-[11px] font-medium uppercase tracking-wide text-stone-400 hover:text-stone-600 dark:hover:text-stone-200" data-testid="recent-toggle">
                <span className="w-3 text-xs">{recentOpen ? "▾" : "▸"}</span>Recent
              </button>
              {recentOpen && (
                <ul className="mt-0.5">
                  {recent.map((f) => (
                    <li key={f.id}>
                      <button onClick={(e) => { e.stopPropagation(); reveal(f); }} title={`${f.rel_path || f.name} · changed ${stamp(f.modified_at)}`} className={`flex w-full items-center gap-2 rounded px-1 py-0.5 text-left hover:bg-stone-100 dark:hover:bg-stone-800 ${selected?.id === f.id ? "text-indigo-700 dark:text-indigo-300" : "text-stone-600 dark:text-stone-300"}`} data-testid="recent-file">
                        <Icon kind={f.kind || "other"} name={f.name} />
                        <span className="min-w-0 flex-1 truncate">{f.name}</span>
                        <span className="shrink-0 text-[10px] text-stone-400">{ago(f.modified_at)}</span>
                      </button>
                    </li>
                  ))}
                </ul>
              )}
            </div>
          )}
          {typedHint && (
            <span data-testid="typeahead-hint" data-miss={typedMiss ? "1" : undefined} className={`pointer-events-none absolute right-2 top-2 z-20 rounded px-1.5 py-0.5 font-mono text-xs text-white ${typedMiss ? "typeahead-miss bg-red-600/90" : "bg-stone-700/90"}`}>
              {typedHint}{typedMiss && <span className="ml-1 opacity-80">— no match</span>}
            </span>
          )}
          {dragging && <p className="mb-1 rounded bg-indigo-50 py-1 text-center text-xs font-medium text-indigo-600 dark:bg-indigo-500/15 dark:text-indigo-300">{dragDoc ? `Move ${dragIds(dragDoc).length === 1 ? "the file" : `${dragIds(dragDoc).length} files`} ${dropFolder != null ? "into this folder" : "to the project root"}` : dropFolder != null ? "Drop to upload into this folder" : "Drop to upload"}</p>}
          {rootFolders.map((f) => folderRow(f, 0))}
          {rootFiles.map((f) => fileRow(f, 0))}
          {total === 0 && !rootFolders.length && (
            <div className="px-3 py-8 text-center">
              <p className="text-sm font-medium text-stone-600 dark:text-stone-300">This project has no files yet</p>
              <p className="mt-1 text-sm text-stone-400">Drag files here, use <b>↑ Upload</b>, or right-click for a menu.</p>
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
              <p className="mb-3 flex flex-wrap items-center gap-3 font-mono text-xs text-stone-400"><span className="min-w-0 truncate">{localFile.path}</span><span>· {humanSize(localFile.size)} · from disk</span>
                <span className="ml-auto flex items-center gap-2 font-sans">
                  <select id="local-target" className="rounded border border-stone-200 bg-white px-1.5 py-1 text-stone-600 dark:border-stone-700 dark:bg-stone-800 dark:text-stone-300" aria-label="Add into folder" defaultValue="">
                    <option value="">(project root)</option>
                    {(data.folders ?? []).filter((f) => !isManuscriptFolder(f)).map((f) => <option key={f.id} value={f.id}>{f.name}</option>)}
                  </select>
                  <button onClick={() => { const v = (document.getElementById("local-target") as HTMLSelectElement | null)?.value; void addLocalFile(localFile, v ? Number(v) : null); }} className="rounded bg-indigo-600 px-2 py-1 font-medium text-white hover:bg-indigo-700" data-testid="add-local-file">Add to this project</button>
                </span>
              </p>
              {localFile.content != null
                ? <pre className="max-h-[58vh] overflow-auto rounded border border-stone-200 bg-stone-50 p-3 font-mono text-xs leading-relaxed text-stone-700 dark:border-stone-800 dark:bg-stone-800 dark:text-stone-300">{localFile.content}</pre>
                : <p className="rounded border border-dashed border-stone-200 p-6 text-center text-sm text-stone-500 dark:border-stone-700">Binary file — no text preview. Add it to the project to open it with the in-app viewers.</p>}
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
                {selected.role !== "manuscript_source" && <span data-testid="version-line">· v{selected.version}{selected.versions ? ` (${selected.versions} earlier)` : ""}</span>}
                <span className="basis-full text-stone-400" data-testid="pane-dates">
                  added <time dateTime={selected.created_at} title={stamp(selected.created_at)}>{ago(selected.created_at)}</time> · changed <time dateTime={selected.modified_at} title={stamp(selected.modified_at)}>{ago(selected.modified_at)}</time>
                </span>
              </dl>
              {selected.role !== "manuscript_source" && (
                <div className="mb-3 space-y-1.5 text-xs" data-testid="file-meta">
                  {selected.description ? (
                    <p className="whitespace-pre-line text-stone-600 dark:text-stone-300" data-testid="file-description">
                      {selected.description}
                      <button onClick={() => void editDescription(selected)} className="ml-1.5 text-indigo-600 hover:underline dark:text-indigo-400" data-testid="edit-description">Edit</button>
                    </p>
                  ) : (
                    <button onClick={() => void editDescription(selected)} className="text-stone-400 hover:text-indigo-600 hover:underline dark:hover:text-indigo-400" data-testid="edit-description">+ Add a description</button>
                  )}
                  <div className="flex flex-wrap items-center gap-1" data-testid="file-tags">
                    {selected.tags.map((t) => (
                      <span key={t.id} className="inline-flex items-center gap-1 rounded-full border border-stone-200 bg-stone-50 py-0.5 pl-1.5 pr-0.5 text-[11px] text-stone-600 dark:border-stone-700 dark:bg-stone-800 dark:text-stone-300" data-testid="file-tag">
                        <TagDot color={t.color} />{t.name}
                        <button onClick={() => void setTags(selected, selected.tags.filter((x) => x.id !== t.id))} aria-label={`Remove tag ${t.name}`} className="rounded-full px-1 text-stone-400 hover:text-red-600">×</button>
                      </span>
                    ))}
                    <button onClick={(e) => menu.open(e, tagItems(selected))} className="rounded-full border border-dashed border-stone-300 px-1.5 py-0.5 text-[11px] text-stone-400 transition-colors hover:border-indigo-400 hover:text-indigo-600 dark:border-stone-600 dark:hover:text-indigo-400" data-testid="add-tag">+ Tag</button>
                  </div>
                </div>
              )}
              {selected.role !== "manuscript_source" && (
                <div className="mb-3 flex flex-wrap items-center gap-3 text-xs">
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
                  <button onClick={() => void askRenameFile(selected)} className="text-indigo-600 hover:underline dark:text-indigo-400">Rename</button>
                  <button onClick={() => askReplace(selected)} className="text-indigo-600 hover:underline dark:text-indigo-400" data-testid="replace-file">Replace…</button>
                  <button onClick={() => setHistoryFor((h) => (h === selected.id ? null : selected.id))} aria-expanded={historyFor === selected.id} className="inline-flex items-center gap-1 text-stone-600 hover:underline dark:text-stone-300" data-testid="history-toggle"><History className="h-3 w-3" aria-hidden="true" />History{selected.versions ? ` (${selected.versions})` : ""}</button>
                  <button onClick={() => void askDeleteFile(selected)} className="text-red-600 hover:underline">Delete</button>
                  <a href={`/api/v1/documents/${selected.id}/raw/?v=${selected.version}`} download={selected.name} className="text-stone-500 hover:underline dark:text-stone-400">Download</a>
                </div>
              )}
              {selected.role !== "manuscript_source" && historyFor === selected.id && (
                <HistoryPanel file={selected} onRestored={async () => { await refreshTree(); queryClient.invalidateQueries({ queryKey: ["file-content", selected.id] }); setSelected((s) => (s ? { ...s, version: s.version + 1, versions: s.versions + 1 } : s)); }} />
              )}
              <FilePreview key={`${selected.id}-${selected.version}`} file={selected} />
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
      {menu.element}
    </div>
  );
}
