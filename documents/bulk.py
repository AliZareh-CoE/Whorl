"""#556: act on many files at once — move / tag / delete a selection, and pack a selection
or a whole folder into a zip. One service behind the explorer's action bar, the API and
the classic Documents page's bulk form.
"""

from __future__ import annotations

import tempfile
import zipfile

from django.utils import timezone

from core.archives import safe_archive_name
from core.ids import MAX_PK
from projects.models import Project

from .models import Document, Folder, Tag

MAX_IDS = 500
ARCHIVE_CAP = 512 * 1024 * 1024  # bytes of stored files one zip may hold
ACTIONS = ("move", "tag", "delete")


class BulkError(ValueError):
    pass


def clean_ids(raw) -> list[int]:
    """Distinct positive ints, in order, at most MAX_IDS; junk raises BulkError."""
    if isinstance(raw, str):
        raw = raw.split(",")
    if not isinstance(raw, list | tuple):
        raise BulkError("ids must be a list of document ids.")
    out: list[int] = []
    for item in raw:
        if isinstance(item, str) and not item.strip():
            continue  # "" from an empty ?ids= or a trailing comma
        try:
            pk = int(item)
        except (TypeError, ValueError):
            raise BulkError("ids must be a list of document ids.") from None
        if 0 < pk <= MAX_PK and pk not in out:
            out.append(pk)
        if len(out) > MAX_IDS:
            raise BulkError(f"At most {MAX_IDS} files at once.")
    return out


def folder_path(folder: Folder | None) -> str:
    parts, node = [], folder
    while node is not None:
        parts.append(node.name)
        node = node.parent
    return "/".join(reversed(parts))


def sync_rel_path(doc: Document) -> bool:
    """Keep a general file's rel_path in step with its folder (the tree, the same-name
    upload twin lookup and zip member names all read it). True when it changed."""
    if doc.role != Document.Role.GENERAL:
        return False
    filename = doc.rel_path.rsplit("/", 1)[-1] if doc.rel_path else (doc.title or "file")
    prefix = folder_path(doc.folder)
    new_rel = f"{prefix}/{filename}" if prefix else filename
    if new_rel == doc.rel_path:
        return False
    doc.rel_path = new_rel
    doc.save(update_fields=["rel_path", "updated_at"])
    return True


def bulk_documents(
    project: Project,
    ids: list[int],
    action: str,
    folder: Folder | None = None,
    tag: Tag | None = None,
) -> dict:
    """Move (into `folder`, None = root), tag (with `tag`) or delete the project's general
    documents among `ids`. Manuscript sources are skipped and reported, never touched."""
    if action not in ACTIONS:
        raise BulkError("Unknown bulk action.")
    if folder is not None and folder.project_id != project.pk:
        raise BulkError("That folder belongs to another project.")
    if tag is not None and tag.project_id != project.pk:
        raise BulkError("That tag belongs to another project.")
    docs = list(project.documents.filter(pk__in=ids).select_related("folder"))
    skipped = [d.pk for d in docs if d.role != Document.Role.GENERAL]
    docs = [d for d in docs if d.role == Document.Role.GENERAL]
    if action == "move":
        for doc in docs:
            doc.folder = folder
            doc.updated_at = timezone.now()
            doc.save(update_fields=["folder", "updated_at"])
            sync_rel_path(doc)
    elif action == "tag":
        if tag is None:
            raise BulkError("A tag is required.")
        for doc in docs:
            doc.tags.add(tag)
    else:
        for doc in docs:
            doc.delete()  # per instance: versions and their files cascade with the row
    return {"action": action, "count": len(docs), "skipped": skipped}


def archive_members(
    project: Project, ids: list[int] | None = None, folder: Folder | None = None
) -> list[tuple[str, Document]]:
    """(member name, document) pairs: a selection keeps each file's project path; a
    folder's members are relative to the folder. Manuscript sources are included read-only."""
    if folder is not None:
        if folder.project_id != project.pk:
            raise BulkError("That folder belongs to another project.")
        docs = project.documents.filter(folder_id__in=folder.descendant_ids())
        base = folder_path(folder) + "/"
    else:
        docs = project.documents.filter(pk__in=ids or [])
        base = ""
    docs = docs.select_related("folder").order_by("rel_path", "title")
    out = []
    for doc in docs:
        if not doc.file and not doc.content:
            continue
        name = doc.rel_path or (doc.title or f"file-{doc.pk}")
        if base and name.startswith(base):
            name = name[len(base) :]
        elif folder is not None:
            # a legacy node without a rel_path: place it by its folder
            inner = folder_path(doc.folder)
            inner = inner[len(base) :] if inner.startswith(base) else ""
            name = f"{inner}/{doc.title or doc.pk}" if inner else (doc.title or str(doc.pk))
        out.append((name, doc))
    return out


def build_archive(
    project: Project, ids: list[int] | None = None, folder: Folder | None = None
) -> tuple[tempfile.SpooledTemporaryFile, str, int]:
    """A zip of the selection or the folder, spooled to disk past 16 MB; the download name
    and the member count come with it. BulkError when the stored bytes exceed ARCHIVE_CAP."""
    members = archive_members(project, ids, folder)
    total = sum(doc.file_size or 0 for _, doc in members)
    if total > ARCHIVE_CAP:
        raise BulkError(
            f"That is {total // (1024 * 1024)} MB of files; a zip holds at most "
            f"{ARCHIVE_CAP // (1024 * 1024)} MB. Pick fewer files."
        )
    written: set[str] = set()

    def unique(path: str) -> str:
        path = safe_archive_name(path) or "unnamed"
        base, n = path, 2
        while path in written:
            stem, dot, ext = base.rpartition(".")
            path = f"{stem} ({n}).{ext}" if dot else f"{base} ({n})"
            n += 1
        written.add(path)
        return path

    spool = tempfile.SpooledTemporaryFile(max_size=16 * 1024 * 1024)
    with zipfile.ZipFile(spool, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for name, doc in members:
            member = unique(name)
            if doc.file:
                with doc.file.open("rb") as handle:
                    zf.writestr(member, handle.read())
            else:
                zf.writestr(member, doc.content)
    spool.seek(0)
    stem = f"{project.slug}-{folder.name}" if folder is not None else f"{project.slug}-files"
    return spool, f"{stem}.zip", len(members)
