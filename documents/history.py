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

from django.core.files.base import ContentFile
from django.db import transaction

from .models import Document, DocumentVersion

KEEP = 20
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
