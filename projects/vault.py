"""A project as a folder of Markdown (#416): the Obsidian-shaped export.

No lock-in: everything a project knows, as files a text editor (or Obsidian, or git) can
read — notes keep their ``[[wiki-links]]``, decisions and lab entries keep their ``@keys``,
the plan is the same outline the Plan page round-trips, the library is a ``.bib`` plus a
reading list, manuscripts are their source trees, documents are the uploaded files.
"""

from __future__ import annotations

import io
import json
import re
import zipfile
from datetime import UTC, datetime
from pathlib import Path

from core.archives import safe_archive_name


def _slug(text: str, fallback: str = "untitled") -> str:
    out = re.sub(r"[^\w\s.-]", "", str(text or "")).strip()
    out = re.sub(r"\s+", " ", out)[:80].strip(" .")
    return out or fallback


def _front_matter(**fields) -> str:
    lines = ["---"]
    for key, value in fields.items():
        if value in (None, "", [], {}):
            continue
        if isinstance(value, list):
            lines.append(f"{key}:")
            lines += [
                f"  - {json.dumps(v) if not isinstance(v, str) else json.dumps(v)}" for v in value
            ]
        else:
            lines.append(
                f"{key}: {json.dumps(value) if not isinstance(value, str) else json.dumps(value)}"
            )
    lines.append("---")
    return "\n".join(lines) + "\n\n"


def build_vault(project, stream, *, include_documents: bool = True) -> dict:
    """Write the vault zip into ``stream``; return the manifest (also stored inside)."""
    from django.conf import settings

    from literature.library import export_bibtex
    from plans.outline import plan_to_markdown

    root = _slug(project.name, project.slug)
    manifest = {
        "project": project.slug,
        "name": project.name,
        "exported_at": datetime.now(UTC).isoformat(),
        "files": 0,
        "counts": {},
    }
    written: set[str] = set()

    def unique(path: str) -> str:
        # #453: one guard for every archive member name Atlas writes
        path = safe_archive_name(path) or "unnamed"
        base, n = path, 2
        while path in written:
            stem, dot, ext = base.rpartition(".")
            path = f"{stem} ({n}).{ext}" if dot else f"{base} ({n})"
            n += 1
        written.add(path)
        return path

    with zipfile.ZipFile(stream, "w", compression=zipfile.ZIP_DEFLATED) as zf:

        def put(path: str, text: str):
            zf.writestr(f"{root}/{unique(path)}", text)
            manifest["files"] += 1

        # README: the project itself + an index
        counts = manifest["counts"]
        put(
            "README.md",
            _front_matter(status=project.status, color=project.color, slug=project.slug)
            + f"# {project.name}\n\n"
            + (project.description.rstrip() + "\n\n" if project.description else "")
            + "Exported from Atlas. Notes link with `[[Title]]`; papers are cited as `@key` and "
            "resolved by `references.bib`.\n",
        )

        # plan — the same outline the Plan page round-trips
        put("plan.md", plan_to_markdown(project))
        counts["phases"] = project.phases.count()

        # research questions
        questions = list(project.questions.all())
        if questions:
            put(
                "questions.md",
                "# Research questions\n\n"
                + "\n".join(f"- [{q.get_status_display()}] {q.question}" for q in questions)
                + "\n",
            )
        counts["questions"] = len(questions)

        # notes — body as written, references as front matter
        notes = list(project.notes.prefetch_related("references"))
        for note in notes:
            put(
                f"notes/{_slug(note.title)}.md",
                _front_matter(
                    title=note.title,
                    references=[r.bibtex_key for r in note.references.all()],
                    updated=note.updated_at.date().isoformat(),
                )
                + note.body.rstrip()
                + "\n",
            )
        counts["notes"] = len(notes)

        # decisions
        decisions = list(project.decisions.order_by("decided_on"))
        for d in decisions:
            put(
                f"decisions/{d.decided_on.isoformat()} {_slug(d.title)}.md",
                _front_matter(title=d.title, decided_on=d.decided_on.isoformat())
                + f"# {d.title}\n\n"
                + (f"## Context\n\n{d.context.rstrip()}\n\n" if d.context else "")
                + f"## Decision\n\n{d.decision.rstrip()}\n\n"
                + (f"## Alternatives\n\n{d.alternatives.rstrip()}\n" if d.alternatives else ""),
            )
        counts["decisions"] = len(decisions)

        # literature — the .bib and a reading list
        links = list(
            project.project_references.select_related("reference").order_by("reference__bibtex_key")
        )
        refs = [link.reference for link in links]
        put("references.bib", export_bibtex(refs))
        put(
            "literature.md",
            "# Literature\n\n| key | title | year | status | priority |\n|---|---|---|---|---|\n"
            + "\n".join(
                f"| @{link.reference.bibtex_key} | {link.reference.title.replace('|', '/')} | {link.reference.year or ''} | {link.reading_status} | {link.priority} |"
                for link in links
            )
            + "\n"
            + "".join(
                f"\n## @{link.reference.bibtex_key}\n\n{link.notes.rstrip()}\n"
                for link in links
                if link.notes.strip()
            ),
        )
        counts["references"] = len(links)

        # research — hypotheses with evidence, experiment log, datasets, protocols
        hyps = list(project.hypotheses.prefetch_related("evidence__reference"))
        if hyps:
            body = ["# Hypotheses", ""]
            for h in hyps:
                body += [f"## {h.statement}", "", f"Status: {h.get_status_display()}", ""]
                for ev in h.evidence.all():
                    cite = f" (@{ev.reference.bibtex_key})" if ev.reference_id else ""
                    body.append(f"- **{ev.direction}** — {ev.summary.strip()}{cite}")
                body.append("")
            put("research/hypotheses.md", "\n".join(body))
        counts["hypotheses"] = len(hyps)
        entries = list(project.experiment_entries.order_by("date"))
        for e in entries:
            put(
                f"research/experiments/{e.date.isoformat()} {_slug(e.title)}.md",
                _front_matter(title=e.title, date=e.date.isoformat(), commit=e.commit_url or None)
                + f"# {e.title}\n\n{e.body.rstrip()}\n",
            )
        counts["experiments"] = len(entries)
        datasets = list(project.datasets.all())
        if datasets:
            put(
                "research/datasets.md",
                "# Datasets\n\n"
                + "\n".join(
                    f"- **{d.name}** — `{d.location}`"
                    + (f" v{d.version}" if d.version else "")
                    + (f" — {d.description.strip()}" if d.description else "")
                    for d in datasets
                )
                + "\n",
            )
        counts["datasets"] = len(datasets)
        protocols = list(project.protocols.all())
        for pr in protocols:
            put(
                f"protocols/{_slug(pr.title)} v{pr.version}.md",
                _front_matter(title=pr.title, version=pr.version, current=bool(pr.is_current))
                + f"# {pr.title} (v{pr.version})\n\n{pr.body.rstrip()}\n",
            )
        counts["protocols"] = len(protocols)

        # manuscripts — source trees + a status sheet
        manuscripts = list(project.manuscripts.prefetch_related("files", "events"))
        for m in manuscripts:
            folder = f"manuscripts/{_slug(m.title)}"
            put(
                f"{folder}/README.md",
                _front_matter(
                    title=m.title,
                    status=m.status,
                    venue=m.target_venue or None,
                    deadline=m.deadline.isoformat() if m.deadline else None,
                )
                + f"# {m.title}\n\n"
                + (m.abstract.rstrip() + "\n\n" if m.abstract else "")
                + (
                    "## Timeline\n\n"
                    + "\n".join(
                        f"- {ev.date.isoformat()} — {ev.get_kind_display()}"
                        + (f": {ev.notes.strip()}" if ev.notes else "")
                        for ev in m.events.all()
                    )
                    + "\n"
                    if m.events.exists()
                    else ""
                ),
            )
            text_files = [f for f in m.files.all() if f.kind != "asset"]
            for f in text_files:
                put(f"{folder}/{f.path}", f.content)
            if not text_files and m.latex_source:
                put(f"{folder}/main.tex", m.latex_source)
        counts["manuscripts"] = len(manuscripts)

        # documents — the uploaded files, in their folders
        docs = 0
        if include_documents:
            media_root = Path(settings.MEDIA_ROOT)
            for doc in project.documents.select_related("folder"):
                if not doc.file:
                    continue
                path = Path(str(doc.file.name))
                source = media_root / path
                if not source.is_file():
                    continue
                folder = doc.folder
                parts = []
                while folder is not None:
                    parts.insert(0, _slug(folder.name))
                    folder = folder.parent
                # the title as the file name (the stored name carries an upload suffix)
                name = f"{_slug(doc.title, path.stem)}{path.suffix.lower()}"
                target = "/".join(["documents", *parts, name])
                zf.write(source, f"{root}/{unique(target)}")
                manifest["files"] += 1
                docs += 1
        counts["documents"] = docs

        manifest_json = json.dumps(manifest, indent=1)
        zf.writestr(f"{root}/atlas-vault.json", manifest_json)
    return manifest


def vault_bytes(project, **kwargs) -> tuple[bytes, dict]:
    buffer = io.BytesIO()
    manifest = build_vault(project, buffer, **kwargs)
    return buffer.getvalue(), manifest
