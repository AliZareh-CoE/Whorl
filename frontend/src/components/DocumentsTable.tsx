/**
 * DocumentsTable island (Owner idea #19, slice 1).
 *
 * Mounts over the server-rendered documents table: client-side sort + filter,
 * shift-click range selection, and a sticky action bar driving the cycle-53
 * bulk endpoints. The server table remains the no-JS fallback.
 */
import { useEffect, useMemo, useState } from "react";

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
  comments: number;
  downloadUrl: string;
  previewUrl: string | null;
  previewKind: "image" | "text" | null;
  editUrl: string;
};
type Comment = { id: number; body: string; created_at: string };
type Props = {
  documents: Doc[];
  folders: Folder[];
  tags: Tag[];
  bulkUrl: string;
  nextUrl: string;
  onDone?: () => void; // SPA mode: refetch instead of full reload
};

function csrfToken(): string {
  const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
  return match ? decodeURIComponent(match[1]) : "";
}

type SortKey = "title" | "folder" | "size" | "added";

export function DocumentsTable({ documents, folders, tags, bulkUrl, nextUrl, onDone }: Props) {
  const [filter, setFilter] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("added");
  const [asc, setAsc] = useState(false);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [lastClicked, setLastClicked] = useState<number | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [folderChoice, setFolderChoice] = useState("");
  const [tagChoice, setTagChoice] = useState(tags[0] ? String(tags[0].id) : "");
  const [busy, setBusy] = useState(false);
  const [commentsDoc, setCommentsDoc] = useState<Doc | null>(null);
  const [previewImage, setPreviewImage] = useState<Doc | null>(null);
  const [extraCounts, setExtraCounts] = useState<Record<number, number>>({});

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
      headers: { "X-CSRFToken": csrfToken(), ...(onDone ? { "X-SPA": "1" } : {}) },
      body,
      redirect: "manual", // don't follow the 302 — it would consume the flash message
    });
    if (onDone) {
      setSelected(new Set());
      setConfirmOpen(false);
      setBusy(false);
      onDone(); // SPA: refetch the table query
    } else {
      location.reload(); // classic page: server re-renders with flash messages
    }
  }

  const allShownSelected = rows.length > 0 && rows.every((r) => selected.has(r.id));
  const arrow = (key: SortKey) => (sortKey === key ? (asc ? " ↑" : " ↓") : "");
  const th =
    "py-2 pr-4 font-medium cursor-pointer select-none hover:text-stone-600 focus:outline-none focus:text-indigo-700";
  // a11y (#177): announce the sort state to screen readers and make the header
  // keyboard-operable, matching the server-rendered library table's aria-sort.
  const ariaSort = (key: SortKey): "ascending" | "descending" | "none" =>
    sortKey === key ? (asc ? "ascending" : "descending") : "none";
  const sortProps = (key: SortKey) => ({
    scope: "col" as const,
    "aria-sort": ariaSort(key),
    tabIndex: 0,
    onClick: () => toggleSort(key),
    onKeyDown: (e: { key: string; preventDefault: () => void }) => {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        toggleSort(key);
      }
    },
  });

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
              <th className={th} {...sortProps("title")}>
                Title{arrow("title")}
              </th>
              <th className={th} {...sortProps("folder")}>
                Folder{arrow("folder")}
              </th>
              <th className="py-2 pr-4 font-medium" scope="col">
                Tags
              </th>
              <th className={th} {...sortProps("size")}>
                Size{arrow("size")}
              </th>
              <th className={th} {...sortProps("added")}>
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
                  <button
                    onClick={() => setCommentsDoc(doc)}
                    aria-haspopup="dialog"
                    aria-label={`Comments on ${doc.title}`}
                    className="text-xs text-stone-500 hover:text-indigo-700"
                  >
                    💬 {(doc.comments ?? 0) + (extraCounts[doc.id] ?? 0) || ""}
                  </button>
                  {doc.previewUrl &&
                    (doc.previewKind === "image" ? (
                      <button
                        type="button"
                        onClick={() => setPreviewImage(doc)}
                        aria-haspopup="dialog"
                        className="ml-2 text-xs text-indigo-600 hover:underline"
                      >
                        Preview
                      </button>
                    ) : (
                      <a
                        href={doc.previewUrl}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="ml-2 text-xs text-indigo-600 hover:underline"
                      >
                        Preview
                      </a>
                    ))}
                  <a href={doc.downloadUrl} className="ml-2 text-xs text-indigo-600 hover:underline">
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

      {commentsDoc && (
        <CommentsModal
          doc={commentsDoc}
          onClose={() => setCommentsDoc(null)}
          onAdded={(id) => setExtraCounts((c) => ({ ...c, [id]: (c[id] ?? 0) + 1 }))}
        />
      )}

      {previewImage && (
        <ImageLightbox doc={previewImage} onClose={() => setPreviewImage(null)} />
      )}

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

/** Comment thread on one document (Owner idea #10 / Backlog #93), modal per owner rule #18. */
function CommentsModal({
  doc,
  onClose,
  onAdded,
}: {
  doc: Doc;
  onClose: () => void;
  onAdded: (docId: number) => void;
}) {
  const [comments, setComments] = useState<Comment[] | null>(null);
  const [body, setBody] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetch(`/api/v1/comments/document/${doc.id}/`, { headers: { Accept: "application/json" } })
      .then((r) => r.json())
      .then((data) => setComments(data.comments ?? []))
      .catch(() => setComments([]));
  }, [doc.id]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  async function save() {
    const text = body.trim();
    if (!text || saving) return;
    setSaving(true);
    const res = await fetch(`/api/v1/comments/document/${doc.id}/`, {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
      body: JSON.stringify({ body: text }),
    });
    if (res.ok) {
      setComments([...(comments ?? []), await res.json()]);
      setBody("");
      onAdded(doc.id);
    }
    setSaving(false);
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="absolute inset-0 bg-stone-900/40" onClick={onClose} aria-hidden="true" />
      <div
        role="dialog"
        aria-modal="true"
        aria-label={`Comments on ${doc.title}`}
        className="relative flex max-h-[80vh] w-full max-w-md flex-col rounded-lg border border-stone-200 bg-white shadow-xl"
      >
        <div className="flex items-start justify-between border-b border-stone-100 px-5 py-3">
          <div className="min-w-0">
            <h2 className="truncate text-base font-semibold tracking-tight">{doc.title}</h2>
            <p className="text-xs text-stone-400">Comments</p>
          </div>
          <button onClick={onClose} aria-label="Close"
                  className="ml-3 rounded px-1.5 text-stone-400 hover:bg-stone-100 hover:text-stone-600">
            ✕
          </button>
        </div>
        <div className="flex-1 space-y-3 overflow-y-auto px-5 py-4">
          {comments === null && <p className="text-sm text-stone-400">Loading…</p>}
          {comments?.length === 0 && (
            <p className="text-sm text-stone-400">
              No comments yet — notes to self about this file go here.
            </p>
          )}
          {comments?.map((c) => (
            <div key={c.id} className="rounded border border-stone-100 bg-stone-50 px-3 py-2">
              <p className="whitespace-pre-wrap text-sm text-stone-700">{c.body}</p>
              <p className="mt-1 text-xs text-stone-400">{c.created_at.slice(0, 10)}</p>
            </div>
          ))}
        </div>
        <div className="border-t border-stone-100 px-5 py-3">
          <textarea
            autoFocus
            value={body}
            onChange={(e) => setBody(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) save();
            }}
            rows={2}
            placeholder="Add a comment… (⌘/Ctrl-Enter to post)"
            className="w-full rounded border border-stone-300 bg-white p-2 text-sm focus:border-indigo-600 focus:outline-none"
          />
          <div className="mt-2 flex items-center gap-3">
            <button
              onClick={save}
              disabled={saving || !body.trim()}
              className="rounded bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
            >
              {saving ? "Posting…" : "Post comment"}
            </button>
            <button onClick={onClose} className="text-xs text-stone-500 hover:underline">
              Close
            </button>
          </div>
        </div>
      </div>
    </div>
  );
}

function ImageLightbox({ doc, onClose }: { doc: Doc; onClose: () => void }) {
  // #227-followup: show an image preview in-app (backdrop click or Esc to dismiss) instead of
  // leaving the page for a new tab. The src is the safe inline-serve endpoint (#227).
  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-center justify-center p-6"
      role="dialog"
      aria-modal="true"
      aria-label={`Preview of ${doc.title}`}
    >
      <div className="absolute inset-0 bg-stone-900/70" onClick={onClose} aria-hidden="true" />
      <figure className="relative flex max-h-full max-w-5xl flex-col items-center gap-2">
        <img
          src={doc.previewUrl ?? ""}
          alt={doc.title}
          className="max-h-[85vh] max-w-full rounded shadow-xl"
        />
        <figcaption className="flex items-center gap-3 text-xs text-stone-300">
          <span className="max-w-md truncate">{doc.title}</span>
          <a href={doc.downloadUrl} className="underline hover:text-white">
            Download
          </a>
          <button onClick={onClose} className="underline hover:text-white">
            Close
          </button>
        </figcaption>
      </figure>
    </div>
  );
}
