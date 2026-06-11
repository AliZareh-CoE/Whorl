/**
 * DocumentsTable island (Owner idea #19, slice 1).
 *
 * Mounts over the server-rendered documents table: client-side sort + filter,
 * shift-click range selection, and a sticky action bar driving the cycle-53
 * bulk endpoints. The server table remains the no-JS fallback.
 */
import { useMemo, useState } from "react";
import { createRoot } from "react-dom/client";

type Tag = { id: number; name: string };
type Folder = { id: number; name: string };
type Doc = {
  id: number;
  title: string;
  description: string;
  folder: string;
  folderId: number | null;
  tags: string[];
  size: number;
  sizeDisplay: string;
  added: string;
  downloadUrl: string;
  editUrl: string;
};
type Props = {
  documents: Doc[];
  folders: Folder[];
  tags: Tag[];
  bulkUrl: string;
  nextUrl: string;
};

function csrfToken(): string {
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : "";
}

type SortKey = "title" | "folder" | "size" | "added";

function DocumentsTable({ documents, folders, tags, bulkUrl, nextUrl }: Props) {
  const [filter, setFilter] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("added");
  const [asc, setAsc] = useState(false);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [lastClicked, setLastClicked] = useState<number | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [folderChoice, setFolderChoice] = useState("");
  const [tagChoice, setTagChoice] = useState(tags[0] ? String(tags[0].id) : "");
  const [busy, setBusy] = useState(false);

  const rows = useMemo(() => {
    const needle = filter.trim().toLowerCase();
    const shown = needle
      ? documents.filter(
          (d) =>
            d.title.toLowerCase().includes(needle) ||
            d.description.toLowerCase().includes(needle) ||
            d.folder.toLowerCase().includes(needle) ||
            d.tags.some((t) => t.toLowerCase().includes(needle)),
        )
      : [...documents];
    shown.sort((a, b) => {
      const dir = asc ? 1 : -1;
      if (sortKey === "size") return (a.size - b.size) * dir;
      const av = String(a[sortKey]).toLowerCase();
      const bv = String(b[sortKey]).toLowerCase();
      return av < bv ? -dir : av > bv ? dir : 0;
    });
    return shown;
  }, [documents, filter, sortKey, asc]);

  function toggleSort(key: SortKey) {
    if (key === sortKey) setAsc(!asc);
    else {
      setSortKey(key);
      setAsc(key === "title" || key === "folder");
    }
  }

  function toggleRow(id: number, index: number, shift: boolean) {
    const next = new Set(selected);
    if (shift && lastClicked !== null) {
      const ids = rows.map((r) => r.id);
      const from = ids.indexOf(lastClicked);
      if (from !== -1) {
        const [lo, hi] = [Math.min(from, index), Math.max(from, index)];
        const turnOn = !selected.has(id);
        for (let i = lo; i <= hi; i++) turnOn ? next.add(ids[i]) : next.delete(ids[i]);
        setSelected(next);
        setLastClicked(id);
        return;
      }
    }
    next.has(id) ? next.delete(id) : next.add(id);
    setSelected(next);
    setLastClicked(id);
  }

  async function bulk(action: string, extra: Record<string, string> = {}) {
    setBusy(true);
    const body = new URLSearchParams({ action, next: nextUrl, ...extra });
    selected.forEach((id) => body.append("ids", String(id)));
    await fetch(bulkUrl, {
      method: "POST",
      headers: { "X-CSRFToken": csrfToken() },
      body,
      redirect: "manual", // don't follow the 302 — it would consume the flash message
    });
    location.reload(); // server is the source of truth — re-render with messages
  }

  const allShownSelected = rows.length > 0 && rows.every((r) => selected.has(r.id));
  const arrow = (key: SortKey) => (sortKey === key ? (asc ? " ↑" : " ↓") : "");
  const th =
    "py-2 pr-4 font-medium cursor-pointer select-none hover:text-stone-600";

  return (
    <div>
      <div className="mb-3 flex items-center gap-2">
        <input
          type="search"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
          placeholder={`Filter ${documents.length} documents…`}
          className="w-64 rounded border border-stone-300 bg-white px-3 py-1.5 text-sm focus:border-indigo-600 focus:outline-none"
        />
        {filter && (
          <span className="text-xs text-stone-400">
            {rows.length} match{rows.length === 1 ? "" : "es"}
          </span>
        )}
      </div>

      {selected.size > 0 && (
        <div className="mb-3 flex flex-wrap items-center gap-2 rounded border border-indigo-200 bg-indigo-50 px-3 py-2 text-sm">
          <span className="font-medium text-indigo-800">{selected.size} selected</span>
          <span className="mx-1 text-indigo-200">|</span>
          <select
            value={folderChoice}
            onChange={(e) => setFolderChoice(e.target.value)}
            className="rounded border border-stone-300 bg-white px-2 py-1 text-xs"
          >
            <option value="">— root</option>
            {folders.map((f) => (
              <option key={f.id} value={f.id}>
                {f.name}
              </option>
            ))}
          </select>
          <button
            disabled={busy}
            onClick={() => bulk("move", { folder: folderChoice })}
            className="rounded border border-stone-300 bg-white px-2 py-1 text-xs hover:border-stone-400"
          >
            Move
          </button>
          {tags.length > 0 && (
            <>
              <select
                value={tagChoice}
                onChange={(e) => setTagChoice(e.target.value)}
                className="ml-2 rounded border border-stone-300 bg-white px-2 py-1 text-xs"
              >
                {tags.map((t) => (
                  <option key={t.id} value={t.id}>
                    {t.name}
                  </option>
                ))}
              </select>
              <button
                disabled={busy}
                onClick={() => bulk("tag", { tag: tagChoice })}
                className="rounded border border-stone-300 bg-white px-2 py-1 text-xs hover:border-stone-400"
              >
                Tag
              </button>
            </>
          )}
          <span className="ml-auto" />
          <button
            onClick={() => setConfirmOpen(true)}
            className="rounded border border-red-200 bg-white px-2 py-1 text-xs text-red-600 hover:border-red-400"
          >
            Delete…
          </button>
        </div>
      )}

      <div className="overflow-x-auto">
        <table className="w-full min-w-[640px] border-collapse text-sm">
          <thead>
            <tr className="border-b border-stone-200 text-left text-xs uppercase tracking-wide text-stone-400">
              <th className="w-6 py-2 pr-2">
                <input
                  type="checkbox"
                  aria-label="Select all documents"
                  checked={allShownSelected}
                  onChange={() =>
                    setSelected(allShownSelected ? new Set() : new Set(rows.map((r) => r.id)))
                  }
                  className="size-4 rounded border-stone-300 accent-indigo-600"
                />
              </th>
              <th className={th} onClick={() => toggleSort("title")}>
                Title{arrow("title")}
              </th>
              <th className={th} onClick={() => toggleSort("folder")}>
                Folder{arrow("folder")}
              </th>
              <th className="py-2 pr-4 font-medium">Tags</th>
              <th className={th} onClick={() => toggleSort("size")}>
                Size{arrow("size")}
              </th>
              <th className={th} onClick={() => toggleSort("added")}>
                Added{arrow("added")}
              </th>
              <th className="py-2"></th>
            </tr>
          </thead>
          <tbody>
            {rows.map((doc, index) => (
              <tr
                key={doc.id}
                className={`border-b border-stone-100 transition-colors hover:bg-stone-50 ${
                  selected.has(doc.id) ? "bg-indigo-50/60" : ""
                }`}
              >
                <td className="w-6 py-2 pr-2">
                  <input
                    type="checkbox"
                    aria-label={`Select ${doc.title}`}
                    checked={selected.has(doc.id)}
                    onClick={(e) => toggleRow(doc.id, index, e.shiftKey)}
                    onChange={() => {}}
                    className="size-4 rounded border-stone-300 accent-indigo-600"
                  />
                </td>
                <td className="py-2 pr-4">
                  <a href={doc.downloadUrl} className="font-medium hover:underline">
                    {doc.title}
                  </a>
                  {doc.description && (
                    <p className="text-xs text-stone-400">{doc.description}</p>
                  )}
                </td>
                <td className="py-2 pr-4 text-stone-500">{doc.folder || "— root"}</td>
                <td className="py-2 pr-4">
                  {doc.tags.map((t) => (
                    <span
                      key={t}
                      className="mr-1 rounded-full border border-stone-200 px-2 py-0.5 text-xs text-stone-500"
                    >
                      {t}
                    </span>
                  ))}
                </td>
                <td className="py-2 pr-4 text-stone-500">{doc.sizeDisplay}</td>
                <td className="py-2 pr-4 text-stone-500">{doc.added}</td>
                <td className="whitespace-nowrap py-2 text-right">
                  <a href={doc.downloadUrl} className="text-xs text-indigo-600 hover:underline">
                    Download
                  </a>
                  <a href={doc.editUrl} className="ml-2 text-xs text-stone-500 hover:underline">
                    Edit
                  </a>
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={7} className="py-6 text-center text-sm text-stone-400">
                  No documents match “{filter}”.
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>

      {confirmOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center p-4"
          onKeyDown={(e) => e.key === "Escape" && setConfirmOpen(false)}
        >
          <div
            className="absolute inset-0 bg-stone-900/40"
            onClick={() => setConfirmOpen(false)}
            aria-hidden="true"
          />
          <div
            role="dialog"
            aria-modal="true"
            aria-label="Confirm bulk delete"
            className="relative w-full max-w-sm rounded-lg border border-stone-200 bg-white p-6 shadow-xl"
          >
            <h2 className="mb-2 text-lg font-semibold tracking-tight">
              Delete selected documents?
            </h2>
            <p className="mb-4 text-sm text-stone-500">
              {selected.size} document(s) and their files will be removed. This cannot be
              undone.
            </p>
            <div className="flex items-center gap-3">
              <button
                disabled={busy}
                onClick={() => bulk("delete")}
                className="rounded bg-red-600 px-4 py-2 text-sm font-medium text-white hover:bg-red-700"
              >
                Delete
              </button>
              <button
                onClick={() => setConfirmOpen(false)}
                className="text-sm text-stone-500 hover:underline"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

export default function mount(el: HTMLElement, props: Props) {
  el.innerHTML = ""; // replace the server-rendered fallback table
  createRoot(el).render(<DocumentsTable {...props} />);
}
