"""#553: file history for general documents.

A data CSV, a figure, an export — the files a researcher revises most — had no memory: an
upload with the same name made a silent duplicate, and an in-place edit, an MCP write or a
same-name upload replaced the bytes for good. Now every overwrite path first files the state
it is about to replace as a ``DocumentVersion`` (numbered ``document.version`` at that time),
bumps the version, and keeps the last ``KEEP`` states. A version can be downloaded, read as
text, or restored — a restore files the current state first, so it is itself undoable.
Manuscript-source nodes are refused everywhere here; the studio keeps their revisions.
"""

from __future__ import annotations

import csv
import difflib
import io

from django.core.files.base import ContentFile
from django.db import transaction

from .models import Document, DocumentVersion

KEEP = 20
# #555: texts larger than this are not diffed in place (download both instead)
DIFF_CAP = 1_000_000
TABLE_ROWS_CAP = 5000  # rows read per side for the cell diff
TABLE_CHANGES_CAP = 500  # cell changes reported
CHUNK = 1024 * 1024


class HistoryError(Exception):
    pass


def _guard(doc: Document) -> None:
    if doc.role == Document.Role.MANUSCRIPT_SOURCE:
        raise HistoryError("Manuscript files are edited in the LaTeX editor.")


def _basename(doc: Document) -> str:
    """The node's own name (never the storage name, which may carry a collision suffix)."""
    return (doc.rel_path or doc.title or "file").rsplit("/", 1)[-1]


def snapshot(doc: Document, *, source: str, note: str = "") -> DocumentVersion:
    """File the document's current file / inline text as version ``doc.version``, then prune."""
    _guard(doc)
    row = DocumentVersion(
        document=doc,
        number=doc.version,
        content="" if doc.file else (doc.content or ""),
        file_size=doc.file_size if doc.file else len((doc.content or "").encode()),
        content_type=doc.content_type or "",
        note=(note or "")[:200],
        source=source,
    )
    if doc.file:
        with doc.file.open("rb") as handle:
            row.file.save(_basename(doc), ContentFile(handle.read()), save=False)
    row.save()
    stale = list(doc.versions.order_by("-number")[KEEP:])
    for old in stale:
        if old.file:
            old.file.delete(save=False)
        old.delete()
    return row


def _drop_old_storage(doc: Document, old_name: str) -> None:
    """``FieldFile.save`` writes a new storage file and never removes the old one; the version
    row already holds its copy, so the old bytes would otherwise sit on disk twice."""
    if old_name and old_name != doc.file.name:
        doc.file.storage.delete(old_name)


def _apply_bytes(doc: Document, name: str, data: bytes, content_type: str) -> None:
    old_name = doc.file.name if doc.file else ""
    doc.file.save(name, ContentFile(data), save=False)
    _drop_old_storage(doc, old_name)
    doc.content = ""
    doc.file_size = len(data)
    doc.content_type = content_type or doc.content_type


@transaction.atomic
def replace_file(doc: Document, upload, *, note: str = "", source: str = "upload") -> dict:
    """A newer version of the file: the current state is filed, the upload's bytes take its
    place under the same tree node (name, folder, tags and description stay)."""
    _guard(doc)
    filed = snapshot(doc, source=source, note=note)
    data = upload.read()
    content_type = getattr(upload, "content_type", "") or ""
    _apply_bytes(doc, _basename(doc), data, content_type)
    doc.version += 1
    doc.save()
    return {"version": doc.version, "filed": filed.number, "size": doc.file_size}


@transaction.atomic
def replace_content(doc: Document, text: str, *, source: str, note: str = "") -> dict | None:
    """A newer version of a text node (in-place edit, API / MCP write). Unchanged text files
    nothing and returns None."""
    _guard(doc)
    if text == current_text(doc):
        return None
    filed = snapshot(doc, source=source, note=note)
    if doc.file:
        old_name = doc.file.name
        doc.file.save(_basename(doc), ContentFile(text.encode()), save=False)
        _drop_old_storage(doc, old_name)
    doc.content = text
    doc.version += 1
    doc.save()
    return {"version": doc.version, "filed": filed.number}


def current_text(doc: Document) -> str | None:
    """The document's text as the content endpoint would serve it, or None when it is not text."""
    if doc.content:
        return doc.content
    if doc.file:
        try:
            with doc.file.open("rb") as handle:
                return handle.read().decode("utf-8")
        except (UnicodeDecodeError, OSError):
            return None
    return ""


def version_text(version: DocumentVersion) -> str | None:
    if version.content:
        return version.content
    if version.file:
        try:
            with version.file.open("rb") as handle:
                return handle.read().decode("utf-8")
        except (UnicodeDecodeError, OSError):
            return None
    return ""


@transaction.atomic
def restore(doc: Document, version: DocumentVersion) -> dict:
    """Put a version's bytes / text back on the node — after filing the current state, so the
    restore can itself be undone."""
    _guard(doc)
    if version.document_id != doc.pk:
        raise HistoryError("That version belongs to another file.")
    filed = snapshot(
        doc, source=DocumentVersion.Source.RESTORE, note=f"before restoring v{version.number}"
    )
    if version.file:
        with version.file.open("rb") as handle:
            _apply_bytes(doc, _basename(doc), handle.read(), version.content_type)
    else:
        if doc.file:
            old_name = doc.file.name
            doc.file.save(_basename(doc), ContentFile(version.content.encode()), save=False)
            _drop_old_storage(doc, old_name)
        doc.content = version.content
        doc.file_size = len(version.content.encode())
    doc.version += 1
    doc.save()
    return {"version": doc.version, "restored": version.number, "filed": filed.number}


def version_rows(doc: Document) -> list[dict]:
    return [
        {
            "number": v.number,
            "created_at": v.created_at,
            "size": v.file_size,
            "content_type": v.content_type,
            "note": v.note,
            "source": v.source,
            "is_text": bool(v.content) or (v.content_type or "").startswith("text/"),
        }
        for v in doc.versions.order_by("-number")
    ]


def _table_kind(doc: Document) -> str | None:
    name = (doc.rel_path or doc.title or "").lower()
    if name.endswith(".csv"):
        return ","
    if name.endswith(".tsv"):
        return "\t"
    return None


def _rows(text: str, delimiter: str) -> list[list[str]]:
    reader = csv.reader(io.StringIO(text), delimiter=delimiter)
    out = []
    for row in reader:
        if len(out) >= TABLE_ROWS_CAP:
            break
        if any(cell.strip() for cell in row):
            out.append(row)
    return out


def table_diff(then_text: str, now_text: str, delimiter: str = ",") -> dict:
    """Cell-level changes from `then` to `now` for a delimited table (#555, backlog 352).

    Rows are aligned with a sequence matcher (a row removed in the middle is one removed
    row, not a shift of everything after it); columns by header name, so an added column
    is reported as such and the cells of the columns both sides share are compared.
    """
    then_rows, now_rows = _rows(then_text, delimiter), _rows(now_text, delimiter)
    then_head = then_rows[0] if then_rows else []
    now_head = now_rows[0] if now_rows else []
    cols_added = [c for c in now_head if c not in then_head]
    cols_removed = [c for c in then_head if c not in now_head]
    shared = [c for c in now_head if c in then_head]
    then_ix = {c: then_head.index(c) for c in shared}
    now_ix = {c: now_head.index(c) for c in shared}

    def key(row: list[str], ix: dict[str, int]) -> tuple[str, ...]:
        return tuple(row[i] if i < len(row) else "" for i in (ix[c] for c in shared))

    then_body, now_body = then_rows[1:], now_rows[1:]
    then_keys = [key(r, then_ix) for r in then_body]
    now_keys = [key(r, now_ix) for r in now_body]
    matcher = difflib.SequenceMatcher(a=then_keys, b=now_keys, autojunk=False)
    changes: list[dict] = []
    rows_added = rows_removed = 0
    truncated = False

    def record(i: int, j: int) -> None:
        nonlocal truncated
        for col, x, y in zip(shared, then_keys[i], now_keys[j], strict=False):
            if x != y:
                if len(changes) >= TABLE_CHANGES_CAP:
                    truncated = True
                    return
                changes.append({"row": j + 2, "column": col, "then": x, "now": y})

    need = max(1, (len(shared) + 1) // 2)  # a pair shares at least half its cells
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        if tag != "replace":
            rows_removed += i2 - i1
            rows_added += j2 - j1
            continue
        # a replaced block: pair each new row with the old row it most resembles (an edited
        # row next to a removed one is one change and one removal, not two rewritten rows)
        unused = list(range(i1, i2))
        if (i2 - i1) * (j2 - j1) > 250_000:  # keep a huge block linear: pair in order
            for offset in range(min(i2 - i1, j2 - j1)):
                record(i1 + offset, j1 + offset)
            rows_removed += max(0, (i2 - i1) - (j2 - j1))
            rows_added += max(0, (j2 - j1) - (i2 - i1))
            continue
        for j in range(j1, j2):
            best, score = None, 0
            for i in unused:
                same = sum(1 for x, y in zip(then_keys[i], now_keys[j], strict=False) if x == y)
                if same > score:
                    best, score = i, same
            if best is not None and score >= need:
                unused.remove(best)
                record(best, j)
            else:
                rows_added += 1
        rows_removed += len(unused)
    return {
        "headers": now_head,
        "changes": changes,
        "rows_added": rows_added,
        "rows_removed": rows_removed,
        "cols_added": cols_added,
        "cols_removed": cols_removed,
        "truncated": truncated
        or len(then_rows) >= TABLE_ROWS_CAP
        or len(now_rows) >= TABLE_ROWS_CAP,
    }


def version_diff(doc: Document, version: DocumentVersion) -> dict:
    """An earlier version compared with the file as it is now (#555, backlog 352): a unified
    line diff (like a note's revision diff) plus, for a .csv / .tsv, the changed cells."""
    then, now = version_text(version), current_text(doc)
    row = {
        "number": version.number,
        "created_at": version.created_at,
        "note": version.note,
        "source": version.source,
        "version": doc.version,
        "is_text": then is not None and now is not None,
        "too_large": False,
        "same": False,
        "diff": "",
        "added": 0,
        "removed": 0,
        "table": None,
    }
    if not row["is_text"]:
        return row
    if len(then) > DIFF_CAP or len(now) > DIFF_CAP:
        row["too_large"] = True
        return row
    lines = list(
        difflib.unified_diff(
            then.splitlines(),
            now.splitlines(),
            fromfile=f"v{version.number}",
            tofile=f"v{doc.version} (now)",
            lineterm="",
            n=2,
        )
    )
    row["same"] = then == now
    row["diff"] = "\n".join(lines)
    row["added"] = sum(1 for line in lines[2:] if line.startswith("+"))
    row["removed"] = sum(1 for line in lines[2:] if line.startswith("-"))
    delimiter = _table_kind(doc)
    if delimiter and not row["same"]:
        row["table"] = table_diff(then, now, delimiter)
    return row
