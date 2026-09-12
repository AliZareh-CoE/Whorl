/**
 * DocumentsTable island (Owner idea #19, slice 1).
 *
 * Mounts over the server-rendered documents table: client-side sort + filter,
 * shift-click range selection, and a sticky action bar driving the cycle-53
 * bulk endpoints. The server table remains the no-JS fallback.
 */
import { useEffect, useMemo, useState } from "react";
import { Download, MessageSquare, Pencil, Trash2 } from "lucide-react";
import { confirmDialog, errorDialog, promptDialog } from "./Dialog";
import { Kebab, useMenu, type MenuItem } from "./Menu";

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

export function DocumentsTable({ documents, folders, tags, bulkUrl, nextUrl, onDone, filesUrl }: Props & { filesUrl?: string }) {
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
  // CRUD sweep 2026-09-06: rename / describe / delete one document without leaving the table
  const menu = useMenu();
  async function patchDoc(id: number, body: Record<string, unknown>) {
    const res = await fetch(`/api/v1/documents/${id}/`, { method: "PATCH", headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() }, credentials: "same-origin", body: JSON.stringify(body) });
    if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  }
  async function deleteDoc(id: number) {
    const res = await fetch(`/api/v1/documents/${id}/`, { method: "DELETE", headers: { "X-CSRFToken": csrfToken() }, credentials: "same-origin" });
    if (!res.ok) throw new Error(`${res.status} ${await res.text()}`);
  }
  const finish = () => (onDone ? onDone() : window.location.reload());
  const rowItems = (doc: Doc): MenuItem[] => [
    { label: "Download", icon: <Download className="h-3.5 w-3.5" />, onSelect: () => { const a = document.createElement("a"); a.href = doc.downloadUrl; a.download = doc.title; a.click(); } },
    { label: "Comments…", icon: <MessageSquare className="h-3.5 w-3.5" />, onSelect: () => setCommentsDoc(doc) },
    "-",
    { label: "Rename…", icon: <Pencil className="h-3.5 w-3.5" />, onSelect: async () => { const t = await promptDialog({ title: "Rename document", label: "Title", initial: doc.title, validate: (v) => (v.trim() ? null : "A document needs a title.") }); if (t && t.trim() !== doc.title) { try { await patchDoc(doc.id, { title: t.trim() }); finish(); } catch (e) { void errorDialog("Couldn't rename the document", e); } } } },
    { label: "Edit description…", onSelect: async () => { const d = await promptDialog({ title: "Description", label: "What is this file?", initial: doc.description, multiline: true }); if (d !== null && d !== doc.description) { try { await patchDoc(doc.id, { description: d }); finish(); } catch (e) { void errorDialog("Couldn't save the description", e); } } } },
    "-",
    { label: "Delete…", icon: <Trash2 className="h-3.5 w-3.5" />, danger: true, onSelect: async () => { if (await confirmDialog({ title: `Delete “${doc.title}”?`, body: "The file is removed from the project and from disk.", danger: true, confirmLabel: "Delete document" })) { try { await deleteDoc(doc.id); finish(); } catch (e) { void errorDialog("Couldn't delete the document", e); } } } },
  ];

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
    "py-2 pr-4 font-medium cursor-pointer select-none transition-colors hover:text-stone-600 focus:outline-none focus-visible:rounded-sm focus-visible:text-indigo-700 focus-visible:ring-1 focus-visible:ring-indigo-500 dark:hover:text-stone-300";
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
          className="w-64 rounded border border-stone-300 bg-white px-3 py-1.5 text-sm placeholder:text-stone-400 focus:border-indigo-600 focus:outline-none focus:ring-1 focus:ring-indigo-600 dark:border-stone-700 dark:bg-stone-800 dark:text-stone-100"
        />
        {filter && (
          <span className="text-xs uppercase tracking-wide text-stone-400">
            {rows.length} match{rows.length === 1 ? "" : "es"}
          </span>
        )}
      </div>

      {selected.size > 0 && (
        <div className="mb-3 flex flex-wrap items-center gap-2 rounded border border-indigo-200 bg-indigo-50 px-3 py-2 text-sm dark:border-indigo-500/30 dark:bg-indigo-500/10">
          <span className="font-medium text-indigo-800 dark:text-indigo-300">{selected.size} selected</span>
          <span className="mx-1 text-indigo-200 dark:text-indigo-500/40">|</span>
          <select
            value={folderChoice}
            onChange={(e) => setFolderChoice(e.target.value)}
            className="rounded border border-stone-300 bg-white px-2 py-1 text-xs dark:border-stone-700 dark:bg-stone-800 dark:text-stone-300"
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
            className="rounded border border-stone-300 bg-white px-2 py-1 text-xs hover:border-stone-400 dark:border-stone-700 dark:bg-stone-800 dark:text-stone-300"
          >
            Move
          </button>
          {tags.length > 0 && (
            <>
              <select
                value={tagChoice}
                onChange={(e) => setTagChoice(e.target.value)}
                className="ml-2 rounded border border-stone-300 bg-white px-2 py-1 text-xs dark:border-stone-700 dark:bg-stone-800 dark:text-stone-300"
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
                className="rounded border border-stone-300 bg-white px-2 py-1 text-xs hover:border-stone-400 dark:border-stone-700 dark:bg-stone-800 dark:text-stone-300"
              >
                Tag
              </button>
            </>
          )}
          <span className="ml-auto" />
          <button
            onClick={() => setConfirmOpen(true)}
            className="rounded border border-red-200 bg-white px-2 py-1 text-xs text-red-600 hover:border-red-400 dark:border-red-500/30 dark:bg-stone-800 dark:text-red-300"
          >
            Delete…
          </button>
        </div>
      )}

      {/* relative: the header's sr-only labels are absolutely positioned and would otherwise
          escape the scroller and widen the page at narrow widths (#420) */}
      <div className="relative overflow-x-auto">
        <table className="w-full min-w-[640px] border-collapse text-sm">
          <thead>
            <tr className="border-b border-stone-200 text-left text-[11px] uppercase tracking-wide text-stone-400 dark:border-stone-800">
              <th className="w-6 py-2 pr-2">
                <input
                  type="checkbox"
                  aria-label="Select all documents"
                  checked={allShownSelected}
                  onChange={() =>
                    setSelected(allShownSelected ? new Set() : new Set(rows.map((r) => r.id)))
                  }
                  className="size-4 rounded border-stone-300 accent-indigo-600 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-indigo-500"
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
              <th className={`${th} text-right`} {...sortProps("size")}>
                Size{arrow("size")}
              </th>
              <th className={`${th} text-right`} {...sortProps("added")}>
                Added{arrow("added")}
              </th>
              <th className="py-2 text-right font-medium" scope="col">
                <span className="sr-only">Actions</span>
              </th>
            </tr>
          </thead>
          <tbody>
            {rows.map((doc, index) => (
              <tr
                key={doc.id}
                onContextMenu={(e) => menu.open(e, rowItems(doc))}
                data-testid="document-row"
                className={`group border-b border-stone-100 transition-colors hover:bg-stone-50 dark:border-stone-800 dark:hover:bg-stone-800 ${
                  selected.has(doc.id) ? "bg-indigo-50/60 dark:bg-indigo-500/10" : ""
                }`}
              >
                <td className="w-6 py-2 pr-2 align-top">
                  <input
                    type="checkbox"
                    aria-label={`Select ${doc.title}`}
                    checked={selected.has(doc.id)}
                    onClick={(e) => toggleRow(doc.id, index, e.shiftKey)}
                    onChange={() => {}}
                    className="mt-0.5 size-4 rounded border-stone-300 accent-indigo-600 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-indigo-500"
                  />
                </td>
                <td className="py-2 pr-4 align-top">
                  <a
                    href={doc.downloadUrl}
                    className="font-medium text-stone-900 hover:text-indigo-700 focus:outline-none focus-visible:text-indigo-700 focus-visible:underline dark:text-stone-100 dark:hover:text-indigo-300"
                  >
                    {doc.title}
                  </a>
                  {doc.description && (
                    <p className="mt-0.5 truncate text-xs text-stone-400">{doc.description}</p>
                  )}
                </td>
                <td className="py-2 pr-4 align-top text-stone-500 dark:text-stone-300">{doc.folder || "— root"}</td>
                <td className="py-2 pr-4 align-top">
                  <div className="flex flex-wrap gap-1">
                    {doc.tags.map((t) => (
                      <span
                        key={t}
                        className="inline-flex items-center rounded-full bg-stone-100 px-2 py-0.5 text-[11px] text-stone-500 dark:bg-stone-800 dark:text-stone-300"
                      >
                        {t}
                      </span>
                    ))}
                  </div>
                </td>
                <td className="whitespace-nowrap py-2 pr-4 text-right align-top tabular-nums text-stone-400">
                  {doc.sizeDisplay}
                </td>
                <td className="whitespace-nowrap py-2 pr-4 text-right align-top tabular-nums text-stone-400">
                  {doc.added}
                </td>
                <td className="whitespace-nowrap py-2 text-right align-top">
                  <div className="flex items-center justify-end gap-2 text-xs opacity-70 transition-opacity group-hover:opacity-100 focus-within:opacity-100">
                    <button
                      onClick={() => setCommentsDoc(doc)}
                      aria-haspopup="dialog"
                      aria-label={`Comments on ${doc.title}`}
                      className="text-stone-400 hover:text-indigo-700 focus:outline-none focus-visible:rounded-sm focus-visible:ring-1 focus-visible:ring-indigo-500 dark:hover:text-indigo-300"
                    >
                      💬 {(doc.comments ?? 0) + (extraCounts[doc.id] ?? 0) || ""}
                    </button>
                    {doc.previewUrl &&
                      (doc.previewKind === "image" ? (
                        <button
                          type="button"
                          onClick={() => setPreviewImage(doc)}
                          aria-haspopup="dialog"
                          className="text-stone-500 hover:text-indigo-700 focus:outline-none focus-visible:rounded-sm focus-visible:ring-1 focus-visible:ring-indigo-500 dark:text-stone-300 dark:hover:text-indigo-300"
                        >
                          Preview
                        </button>
                      ) : (
                        <a
                          href={doc.previewUrl}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-stone-500 hover:text-indigo-700 focus:outline-none focus-visible:rounded-sm focus-visible:ring-1 focus-visible:ring-indigo-500 dark:text-stone-300 dark:hover:text-indigo-300"
                        >
                          Preview
                        </a>
                      ))}
                    <a
                      href={doc.downloadUrl}
                      className="text-stone-500 hover:text-indigo-700 focus:outline-none focus-visible:rounded-sm focus-visible:ring-1 focus-visible:ring-indigo-500 dark:text-stone-300 dark:hover:text-indigo-300"
                    >
                      Download
                    </a>
                    <Kebab items={rowItems(doc)} label={`Actions for ${doc.title}`} />
                  </div>
                </td>
              </tr>
            ))}
            {rows.length === 0 && (
              <tr>
                <td colSpan={7} className="px-4 py-12 text-center">
                  <p className="text-sm font-medium text-stone-500 dark:text-stone-300">
                    {filter.trim() ? "No matches" : "No documents yet"}
                  </p>
                  <p className="mx-auto mt-1 max-w-sm text-xs text-stone-400">
                    {filter.trim()
                      ? `Nothing matches “${filter.trim()}”. Try a different title, folder, or tag.`
                      : "Upload a file into any folder to start filling this project's library."}
                  </p>
                  {!filter.trim() && filesUrl && (
                    <a href={filesUrl} className="mt-3 inline-block rounded bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-700" data-testid="documents-upload-cta">Upload in Files →</a>
                  )}
                </td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      {/* #421 (backlog #178): a three-row table in a wide page leaves a lot of quiet space —
          say what the page is for and offer the next step instead of leaving it blank */}
      {!filter.trim() && documents.length > 0 && documents.length <= 3 && (
        <div className="mt-4 rounded border border-dashed border-stone-200 px-4 py-5 text-center dark:border-stone-800" data-testid="documents-sparse">
          <p className="text-sm text-stone-500 dark:text-stone-300">
            {documents.length === 1 ? "One file so far." : `${documents.length} files so far.`} This page is the project's file cabinet: protocols, data notes, figures, drafts — anything worth finding again.
          </p>
          <p className="mt-2 text-xs text-stone-400">
            {filesUrl ? <><a href={filesUrl} className="font-medium text-indigo-600 hover:underline dark:text-indigo-300">Upload or drop files in Files →</a> · </> : null}
            PDFs of papers belong in the Library; tag files here so filters mean something.
          </p>
        </div>
      )}

      {menu.element}
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
            className="relative w-full max-w-sm rounded-lg border border-stone-200 bg-white p-6 shadow-xl dark:border-stone-800 dark:bg-stone-900"
          >
            <h2 className="mb-2 text-lg font-semibold tracking-tight">
              Delete selected documents?
            </h2>
            <p className="mb-4 text-sm text-stone-500 dark:text-stone-300">
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
                className="text-sm text-stone-500 hover:underline dark:text-stone-300"
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
        className="relative flex max-h-[80vh] w-full max-w-md flex-col rounded-lg border border-stone-200 bg-white shadow-xl dark:border-stone-800 dark:bg-stone-900"
      >
        <div className="flex items-start justify-between border-b border-stone-100 px-5 py-3 dark:border-stone-800">
          <div className="min-w-0">
            <h2 className="truncate text-base font-semibold tracking-tight">{doc.title}</h2>
            <p className="text-xs text-stone-400">Comments</p>
          </div>
          <button onClick={onClose} aria-label="Close"
                  className="ml-3 rounded px-1.5 text-stone-400 hover:bg-stone-100 hover:text-stone-600 dark:hover:bg-stone-800 dark:hover:text-stone-300">
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
            <div key={c.id} className="rounded border border-stone-100 bg-stone-50 px-3 py-2 dark:border-stone-800 dark:bg-stone-800">
              <p className="whitespace-pre-wrap text-sm text-stone-700 dark:text-stone-300">{c.body}</p>
              <p className="mt-1 text-xs text-stone-400">{c.created_at.slice(0, 10)}</p>
            </div>
          ))}
        </div>
        <div className="border-t border-stone-100 px-5 py-3 dark:border-stone-800">
          <textarea
            autoFocus
            value={body}
            onChange={(e) => setBody(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) save();
            }}
            rows={2}
            placeholder="Add a comment… (⌘/Ctrl-Enter to post)"
            className="w-full rounded border border-stone-300 bg-white p-2 text-sm focus:border-indigo-600 focus:outline-none dark:border-stone-700 dark:bg-stone-800 dark:text-stone-100"
          />
          <div className="mt-2 flex items-center gap-3">
            <button
              onClick={save}
              disabled={saving || !body.trim()}
              className="rounded bg-indigo-600 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-700 disabled:opacity-50"
            >
              {saving ? "Posting…" : "Post comment"}
            </button>
            <button onClick={onClose} className="text-xs text-stone-500 hover:underline dark:text-stone-300">
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
