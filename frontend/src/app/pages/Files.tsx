import { useQuery } from "@tanstack/react-query";
import { useMemo, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api } from "../api";

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

// stroke-SVG icons in the editor's visual language (#30 slice 2b; lucide swap is a later slice)
function Icon({ kind, open }: { kind: string; open?: boolean }) {
  const p = { width: 15, height: 15, viewBox: "0 0 24 24", fill: "none", stroke: "currentColor", strokeWidth: 2, strokeLinecap: "round" as const, strokeLinejoin: "round" as const };
  if (kind === "folder")
    return (
      <svg {...p} className="shrink-0 text-stone-400">
        {open ? (
          <path d="M3 7a2 2 0 0 1 2-2h3.9a2 2 0 0 1 1.7.9l.8 1.1H19a2 2 0 0 1 2 2v1H6l-3 8Z" />
        ) : (
          <path d="M4 20h16a2 2 0 0 0 2-2V8a2 2 0 0 0-2-2h-7.9a2 2 0 0 1-1.7-.9L9.2 3.9A2 2 0 0 0 7.5 3H4a2 2 0 0 0-2 2v13a2 2 0 0 0 2 2Z" />
        )}
      </svg>
    );
  const base = (children: React.ReactNode, cls = "text-stone-400") => (
    <svg {...p} className={`shrink-0 ${cls}`}>
      <path d="M14 3H6a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V9Z" />
      <polyline points="14 3 14 9 20 9" />
      {children}
    </svg>
  );
  if (kind === "tex" || kind === "bib") return base(<text x="7.5" y="18" fontSize="6" fill="currentColor" stroke="none">{kind === "tex" ? "T" : "B"}</text>, "text-indigo-400");
  if (kind === "pdf") return base(null, "text-red-400");
  if (kind === "asset") return base(<circle cx="9" cy="13" r="1.5" />, "text-amber-400");
  return base(null);
}

export default function Files() {
  const { slug } = useParams();
  const { data, isLoading, error } = useQuery({
    queryKey: ["tree", slug],
    queryFn: () => api<Tree>(`/projects/${slug}/tree/`),
  });
  const [expanded, setExpanded] = useState<Record<number, boolean>>({});
  const [selected, setSelected] = useState<FileNode | null>(null);

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

  if (isLoading) return <p className="text-sm text-stone-400">Loading files…</p>;
  if (error || !data) return <p className="text-sm text-red-600">Couldn't load the file tree.</p>;

  const fileRow = (f: FileNode, depth: number) => (
    <button
      key={`f${f.id}`}
      onClick={() => setSelected(f)}
      style={{ paddingLeft: depth * 16 + 8 }}
      className={`flex w-full items-center gap-2 rounded py-1 pr-2 text-left text-sm hover:bg-stone-50 ${selected?.id === f.id ? "bg-indigo-50 text-indigo-700" : "text-stone-700"}`}
    >
      <Icon kind={f.kind || "other"} />
      <span className="min-w-0 flex-1 truncate">{f.name}</span>
      {f.role === "manuscript_source" && (
        <span className="shrink-0 rounded bg-stone-100 px-1 text-[10px] text-stone-400">ms</span>
      )}
      <span className="shrink-0 text-xs text-stone-400">{humanSize(f.size)}</span>
    </button>
  );

  const folderRow = (folder: FolderNode, depth: number) => {
    const open = expanded[folder.id];
    const kids = childFolders[folder.id] ?? [];
    const files = folderFiles[folder.id] ?? [];
    return (
      <div key={`d${folder.id}`}>
        <button
          onClick={() => setExpanded((e) => ({ ...e, [folder.id]: !e[folder.id] }))}
          style={{ paddingLeft: depth * 16 + 8 }}
          className="flex w-full items-center gap-2 rounded py-1 pr-2 text-left text-sm text-stone-700 hover:bg-stone-50"
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
      <nav className="mb-4 text-sm text-stone-500">
        <Link to="/projects" className="hover:underline">Projects</Link> /{" "}
        <Link to={`/projects/${slug}`} className="hover:underline">{slug}</Link> / Files
      </nav>
      <div className="mb-3 flex items-baseline justify-between">
        <h1 className="text-2xl font-semibold tracking-tight">Files</h1>
        <span className="text-xs text-stone-400">{total} file{total === 1 ? "" : "s"} · everything in one tree</span>
      </div>

      <div className="grid grid-cols-3 gap-3">
        <div className="card col-span-1 max-h-[75vh] overflow-y-auto">
          {rootFolders.map((f) => folderRow(f, 0))}
          {rootFiles.map((f) => fileRow(f, 0))}
          {total === 0 && !rootFolders.length && (
            <p className="p-2 text-sm text-stone-400">
              No files yet. Upload on the{" "}
              <a href={`/projects/${slug}/documents/`} className="text-indigo-600 hover:underline">documents page</a>.
            </p>
          )}
        </div>
        <div className="card col-span-2">
          {selected ? (
            <div>
              <div className="mb-2 flex items-center gap-2">
                <Icon kind={selected.kind || "other"} />
                <h2 className="min-w-0 flex-1 truncate text-sm font-medium">{selected.name}</h2>
              </div>
              <dl className="grid grid-cols-2 gap-x-4 gap-y-1 text-xs text-stone-500">
                <div><dt className="text-stone-400">Path</dt><dd className="truncate font-mono">{selected.rel_path}</dd></div>
                <div><dt className="text-stone-400">Kind</dt><dd>{selected.kind || "—"}</dd></div>
                <div><dt className="text-stone-400">Type</dt><dd>{selected.role === "manuscript_source" ? "manuscript source" : "document"}</dd></div>
                <div><dt className="text-stone-400">Size</dt><dd>{humanSize(selected.size) || "—"}</dd></div>
              </dl>
              <p className="mt-3 text-xs text-stone-400">In-app preview & editing land in the next slice.</p>
            </div>
          ) : (
            <p className="text-sm text-stone-400">Select a file to see its details.</p>
          )}
        </div>
      </div>
    </div>
  );
}
