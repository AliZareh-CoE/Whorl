"""Bulk import of a projects folder (owner ask 2026-09-15, #535: "I have a project folder
with all my projects inside it — add all the old projects real quick").

Every immediate subfolder of the root becomes one Atlas project, named after the folder (or
its README's first heading). Inside it: the README becomes the description, Markdown files
become notes, PDFs go into the library (through the same pipeline as a dropped PDF — DOI read
off page one, metadata fetched, a stub when there is none) and are linked to the project,
.bib / .ris files are imported into the library and kept as files, everything else becomes a
workspace document in the same folder structure.

Two entry points: `plan(root)` looks without touching the database or the network (the dry
run every caller shows first) and `import_project(root, folder)` brings one folder in. Both
are idempotent — a project that already exists (by slug) is reused and only what is missing
is added; nothing the owner edited is overwritten.
"""

from __future__ import annotations

import mimetypes
import os
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

from django.utils.text import slugify

from core.security import MAX_UPLOAD_BYTES
from documents.paths import MAX_PATH_SEGMENTS, PATH_SEGMENT_RE

JUNK_DIRS = {
    ".git",
    ".hg",
    ".svn",
    "node_modules",
    "__pycache__",
    ".venv",
    "venv",
    "env",
    ".tox",
    ".mypy_cache",
    ".pytest_cache",
    ".ruff_cache",
    "build",
    "dist",
    "target",
    ".idea",
    ".vscode",
}
JUNK_FILES = {".DS_Store", "Thumbs.db", "desktop.ini"}
README_NAMES = ("readme.md", "readme.markdown", "readme.txt", "readme.rst", "readme")
MARKDOWN_SUFFIXES = {".md", ".markdown"}
BIB_SUFFIXES = {".bib", ".bibtex", ".ris"}
MAX_FILES = 2000  # per project: a monorepo must not hang the import
MAX_DESCRIPTION = 20_000
MAX_NOTE_BYTES = 2 * 1024 * 1024
PDFS_CHOICES = ("library", "documents")
MARKDOWN_CHOICES = ("notes", "documents")


@dataclass
class Entry:
    """One file inside a project folder, already classified and given a safe tree path."""

    path: Path
    rel_path: str  # posix, sanitized segments — where it lands in the project's tree
    kind: str  # readme / note / pdf / bib / file
    size: int
    title: str  # the original file name


@dataclass
class Plan:
    folder: str
    name: str
    slug: str
    exists: bool
    description: str = ""
    entries: list[Entry] = field(default_factory=list)
    skipped: list[dict] = field(default_factory=list)

    def counts(self) -> dict:
        by = {k: 0 for k in ("pdfs", "notes", "bibs", "files")}
        for e in self.entries:
            if e.kind == "pdf":
                by["pdfs"] += 1
            elif e.kind == "note":
                by["notes"] += 1
            elif e.kind == "bib":
                by["bibs"] += 1
            elif e.kind == "file":
                by["files"] += 1
        return by

    def as_dict(self) -> dict:
        return {
            "folder": self.folder,
            "name": self.name,
            "slug": self.slug,
            "exists": self.exists,
            "has_readme": bool(self.description),
            "bytes": sum(e.size for e in self.entries),
            **self.counts(),
            "skipped": list(self.skipped),
        }


# --- names ---------------------------------------------------------------------------------


def humanize(folder_name: str) -> str:
    """`attention_and_memory-2019` → `attention and memory 2019` (case kept: acronyms stay)."""
    text = re.sub(r"[_\-]+", " ", folder_name).strip()
    return re.sub(r"\s+", " ", text) or folder_name


def safe_segment(name: str) -> str:
    """A folder or file name the workspace tree accepts (ASCII, no leading dot, ≤ 80 chars),
    keeping the extension readable: `Résumé (final).PDF` → `Resume-final.PDF`."""
    text = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    text = re.sub(r"[^A-Za-z0-9._\-]+", "-", text)
    text = re.sub(r"-{2,}", "-", text)
    text = re.sub(r"-+\.", ".", text)
    text = re.sub(r"\.-+", ".", text).strip("-.")
    if len(text) > 80:
        stem, dot, ext = text.rpartition(".")
        if dot and 0 < len(ext) <= 10:
            text = stem[: 80 - len(ext) - 1].rstrip("-.") + "." + ext
        else:
            text = text[:80].rstrip("-.")
    if not text or not PATH_SEGMENT_RE.match(text):
        text = "file"
    return text


def _size() -> str:
    cap = MAX_UPLOAD_BYTES
    return f"{cap // 2**20} MB" if cap >= 2**20 else f"{cap} bytes"


def _unique(rel_path: str, used: set[str]) -> str:
    """`a/b.pdf` → `a/b-2.pdf` when the path is already taken."""
    if rel_path.lower() not in used:
        used.add(rel_path.lower())
        return rel_path
    head, _, name = rel_path.rpartition("/")
    stem, dot, ext = name.rpartition(".")
    if not dot:
        stem, ext = name, ""
    n = 2
    while True:
        candidate = f"{stem}-{n}.{ext}" if ext else f"{stem}-{n}"
        candidate = f"{head}/{candidate}" if head else candidate
        if candidate.lower() not in used:
            used.add(candidate.lower())
            return candidate
        n += 1


def _read_readme(path: Path) -> tuple[str, str]:
    """(heading, body): the first `# Heading` becomes the project name, the rest the
    description."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return "", ""
    lines = text.splitlines()
    heading = ""
    for i, line in enumerate(lines[:5]):
        m = re.match(r"^#\s+(.+?)\s*#*\s*$", line)
        if m:
            heading = m.group(1).strip()
            lines = lines[:i] + lines[i + 1 :]
            break
    body = "\n".join(lines).strip()
    return heading[:200], body[:MAX_DESCRIPTION]


# --- looking -------------------------------------------------------------------------------


def _classify(path: Path, pdfs: str, markdown: str) -> str:
    suffix = path.suffix.lower()
    if suffix == ".pdf":
        return "pdf" if pdfs == "library" else "file"
    if suffix in MARKDOWN_SUFFIXES:
        return "note" if markdown == "notes" else "file"
    if suffix in BIB_SUFFIXES:
        return "bib"
    return "file"


def plan_folder(root: Path, folder: str, pdfs: str = "library", markdown: str = "notes") -> Plan:
    """Look at one project folder: what it would become, without the database or the network."""
    from projects.models import Project

    base = root / folder
    name = humanize(folder)
    description = ""
    readme: Path | None = None
    for candidate in sorted(base.iterdir()) if base.is_dir() else []:
        if candidate.is_file() and candidate.name.lower() in README_NAMES:
            readme = candidate
            break
    if readme is not None:
        heading, description = _read_readme(readme)
        if heading:
            name = heading
    slug = slugify(name) or "project"
    existing = (
        Project.objects.filter(slug=slug).first()
        or Project.objects.filter(name__iexact=name).first()
    )
    plan = Plan(
        folder=folder, name=name, slug=existing.slug if existing else slug, exists=bool(existing)
    )
    if existing:
        plan.name = existing.name
    used: set[str] = set()
    count = 0
    for dirpath, dirnames, filenames in os.walk(base, followlinks=False):
        dirnames[:] = sorted(d for d in dirnames if d not in JUNK_DIRS and not d.startswith("."))
        rel_dir = Path(dirpath).relative_to(base)
        segments = [safe_segment(p) for p in rel_dir.parts]
        for filename in sorted(filenames):
            path = Path(dirpath) / filename
            if path == readme:
                continue
            rel_original = (rel_dir / filename).as_posix()
            if filename in JUNK_FILES or filename.startswith("."):
                continue
            if path.is_symlink() or not path.is_file():
                plan.skipped.append({"path": rel_original, "reason": "not a regular file"})
                continue
            if len(segments) + 1 > MAX_PATH_SEGMENTS:
                plan.skipped.append({"path": rel_original, "reason": "nested too deep"})
                continue
            try:
                size = path.stat().st_size
            except OSError as exc:
                plan.skipped.append({"path": rel_original, "reason": exc.__class__.__name__})
                continue
            if size > MAX_UPLOAD_BYTES:
                plan.skipped.append({"path": rel_original, "reason": f"larger than {_size()}"})
                continue
            count += 1
            if count > MAX_FILES:
                plan.skipped.append(
                    {"path": rel_original, "reason": f"more than {MAX_FILES} files"}
                )
                continue
            kind = _classify(path, pdfs, markdown)
            rel_path = _unique("/".join(segments + [safe_segment(filename)]), used)
            plan.entries.append(Entry(path, rel_path, kind, size, filename))
    plan.description = description
    return plan


def list_folders(root: Path) -> list[str]:
    return sorted(
        p.name
        for p in root.iterdir()
        if p.is_dir()
        and not p.is_symlink()
        and not p.name.startswith(".")
        and p.name not in JUNK_DIRS
    )


def resolve_root(path: str) -> Path:
    """The projects folder, checked the way the watched folder is: it must exist."""
    text = (path or "").strip()
    if not text:
        raise ValueError("Give the path of the folder that holds your projects.")
    root = Path(text).expanduser()
    if not root.is_dir():
        raise ValueError(f"{text} is not a folder that exists.")
    return root


def plan(
    root: Path, only: list[str] | None = None, pdfs: str = "library", markdown: str = "notes"
) -> list[Plan]:
    """The dry run: one row per project folder (or per name in `only`)."""
    folders = list_folders(root)
    if only:
        wanted = {o.strip() for o in only if o and o.strip()}
        missing = sorted(wanted - set(folders))
        if missing:
            raise ValueError(f"No such folder under {root}: {', '.join(missing)}")
        folders = [f for f in folders if f in wanted]
    return [plan_folder(root, f, pdfs, markdown) for f in folders]


# --- bringing it in ------------------------------------------------------------------------


def _ensure_folders(project, segments: list[str], cache: dict):
    from documents.models import Folder

    parent = None
    key = ()
    for name in segments:
        key = (*key, name)
        if key not in cache:
            cache[key], _ = Folder.objects.get_or_create(project=project, parent=parent, name=name)
        parent = cache[key]
    return parent


def _import_pdf(entry: Entry, project, result: dict) -> None:
    from literature.importers import import_pdf
    from literature.models import Reference

    marker = f"{project.slug}:{entry.rel_path}"
    if Reference.objects.filter(extra__imported_from=marker).exists():
        result["skipped"].append({"path": entry.rel_path, "reason": "already in the library"})
        return
    outcome = import_pdf(entry.title, entry.path.read_bytes(), project)
    if outcome.reference_id:
        ref = Reference.objects.get(pk=outcome.reference_id)
        ref.extra = {**(ref.extra or {}), "imported_from": marker}
        ref.save(update_fields=["extra", "updated_at"])
        result["references"] += 1
        if outcome.needs_metadata:
            result["needs_metadata"] += 1
    else:
        result["errors"].append({"path": entry.rel_path, "reason": outcome.error or "not imported"})


def _import_file(entry: Entry, project, folders: dict, result: dict) -> None:
    from django.core.files import File

    from documents.models import Document
    from documents.paths import kind_for_node_path

    if Document.objects.filter(project=project, rel_path=entry.rel_path).exists():
        result["skipped"].append({"path": entry.rel_path, "reason": "already imported"})
        return
    *dirs, filename = entry.rel_path.split("/")
    folder = _ensure_folders(project, dirs, folders) if dirs else None
    content_type = mimetypes.guess_type(entry.title)[0] or "application/octet-stream"
    with entry.path.open("rb") as fh:
        doc = Document(
            project=project,
            folder=folder,
            title=entry.title,
            rel_path=entry.rel_path,
            role=Document.Role.GENERAL,
            kind=kind_for_node_path(entry.rel_path),
            content_type=content_type,
        )
        doc.file.save(filename, File(fh), save=False)
        doc.file_size = entry.size
        doc.save()
    result["documents"] += 1


def _import_bib(entry: Entry, project, result: dict) -> None:
    from literature.importers import import_file

    summary = import_file(entry.title, entry.path.read_bytes(), project)
    result["references"] += summary.created
    for r in summary.results:
        if r.error:
            result["errors"].append({"path": entry.rel_path, "reason": r.error})


def _import_note(entry: Entry, project, result: dict) -> None:
    from notes.models import Note

    if entry.size > MAX_NOTE_BYTES:
        result["skipped"].append({"path": entry.rel_path, "reason": "too large for a note"})
        return
    title = Path(entry.title).stem.strip()[:300] or entry.title[:300]
    if Note.objects.filter(project=project, title__iexact=title).exists():
        result["skipped"].append(
            {"path": entry.rel_path, "reason": "a note with this title exists"}
        )
        return
    body = entry.path.read_text(encoding="utf-8", errors="replace")
    note = Note.objects.create(project=project, title=title, body=body)
    result["notes"] += 1
    result["_notes"].append(note)


def import_project(root: Path, folder: str, pdfs: str = "library", markdown: str = "notes") -> dict:
    """Bring one project folder in. Returns the plan row plus what was created."""
    from django.db import transaction

    from notes.services import sync_note_links, sync_note_references
    from notes.tags import sync_note_tags
    from projects.models import Project

    if pdfs not in PDFS_CHOICES or markdown not in MARKDOWN_CHOICES:
        raise ValueError("pdfs must be library|documents and markdown notes|documents.")
    p = plan_folder(root, folder, pdfs, markdown)
    result = {
        **p.as_dict(),
        "created": False,
        "description_set": False,
        "documents": 0,
        "notes": 0,
        "references": 0,
        "needs_metadata": 0,
        "errors": [],
        "_notes": [],
    }
    with transaction.atomic():
        project = Project.objects.filter(slug=p.slug).first()
        if project is None:
            project = Project.objects.create(name=p.name, description=p.description)
            result["created"] = True
            result["description_set"] = bool(p.description)
        elif p.description and not project.description.strip():
            project.description = p.description
            project.save(update_fields=["description", "updated_at"])
            result["description_set"] = True
        result["slug"], result["name"] = project.slug, project.name
        folders: dict = {}
        for entry in p.entries:
            if entry.kind == "note":
                _import_note(entry, project, result)
            elif entry.kind == "bib":
                _import_file(entry, project, folders, result)
                _import_bib(entry, project, result)
            elif entry.kind == "file":
                _import_file(entry, project, folders, result)
        # links resolve only once every note of the folder exists
        for note in result["_notes"]:
            sync_note_links(note)
            sync_note_references(note)
            sync_note_tags(note)
    # PDFs last and outside the transaction: each one may talk to Crossref / OpenAlex
    for entry in p.entries:
        if entry.kind == "pdf":
            try:
                _import_pdf(entry, project, result)
            except Exception as exc:  # noqa: BLE001 - one bad PDF must not stop the folder
                result["errors"].append({"path": entry.rel_path, "reason": str(exc)[:200]})
    result.pop("_notes")
    result["skipped"] = list(p.skipped) + [s for s in result["skipped"] if s not in p.skipped]
    return result


def import_folder(
    root: Path, only: list[str] | None = None, pdfs: str = "library", markdown: str = "notes"
) -> list[dict]:
    """Every project folder (or the ones in `only`), one after the other."""
    return [
        import_project(root, p.folder, pdfs, markdown) for p in plan(root, only, pdfs, markdown)
    ]
