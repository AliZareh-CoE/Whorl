"""Where a paper appears (#411): every place in Atlas that links to or mentions a reference.

Backlinks for papers. Notes link a reference explicitly (the M2M) or cite it as ``@key`` in
the body; decisions, experiment entries, protocols and captures can only mention it (#407
made those mentions live links); manuscripts carry it in their bibliography; evidence rows
point at it. One list, grouped by kind, each row with the SPA route to jump to.
"""

from __future__ import annotations

import re

from django.db.models import Q

from notes.services import CITE_RE


def _mentions(text: str, key: str) -> bool:
    """True when ``@key`` appears as a whole cite key (not as a prefix of a longer key)."""
    if not text:
        return False
    key = key.lower()
    return any(m.group(1).rstrip(".").lower() == key for m in CITE_RE.finditer(text))


def usage_of(reference) -> dict:
    from notes.models import Note, QuickCapture
    from projects.models import DecisionRecord
    from research.models import Evidence, ExperimentEntry, Protocol
    from writing.models import ManuscriptReference

    key = reference.bibtex_key
    needle = f"@{key}"
    rows: list[dict] = []

    def add(kind, obj, *, title, project, how, url, detail=""):
        rows.append(
            {
                "kind": kind,
                "id": obj.pk,
                "title": title,
                "project": project.slug if project else None,
                "project_name": project.name if project else None,
                "how": how,
                "url": url,
                "detail": detail,
                "updated_at": getattr(obj, "updated_at", None),
            }
        )

    linked_ids = set(reference.notes.values_list("pk", flat=True))
    notes = Note.objects.filter(Q(pk__in=linked_ids) | Q(body__icontains=needle)).select_related(
        "project"
    )
    for note in notes:
        mentioned = _mentions(note.body, key)
        if note.pk not in linked_ids and not mentioned:
            continue
        add(
            "note",
            note,
            title=note.title,
            project=note.project,
            how="linked" if note.pk in linked_ids else "mentioned",
            url=f"/projects/{note.project.slug}/notes/{note.pk}",
        )

    for decision in DecisionRecord.objects.filter(
        Q(context__icontains=needle)
        | Q(decision__icontains=needle)
        | Q(alternatives__icontains=needle)
    ).select_related("project"):
        if _mentions(" ".join((decision.context, decision.decision, decision.alternatives)), key):
            add(
                "decision",
                decision,
                title=decision.title,
                project=decision.project,
                how="mentioned",
                url=f"/projects/{decision.project.slug}/decisions",
                detail=decision.decided_on.isoformat(),
            )

    for entry in ExperimentEntry.objects.filter(body__icontains=needle).select_related("project"):
        if _mentions(entry.body, key):
            add(
                "experiment",
                entry,
                title=entry.title,
                project=entry.project,
                how="mentioned",
                url=f"/projects/{entry.project.slug}/research",
                detail=entry.date.isoformat(),
            )

    for protocol in Protocol.objects.filter(body__icontains=needle).select_related("project"):
        if _mentions(protocol.body, key):
            add(
                "protocol",
                protocol,
                title=f"{protocol.title} v{protocol.version}",
                project=protocol.project,
                how="mentioned",
                url=f"/projects/{protocol.project.slug}/research",
            )

    for capture in QuickCapture.objects.filter(text__icontains=needle).select_related("project"):
        if _mentions(capture.text, key):
            add(
                "capture",
                capture,
                title=re.sub(r"\s+", " ", capture.text)[:120],
                project=capture.project,
                how="mentioned",
                url="/inbox",
                detail="filed" if capture.processed else "in the inbox",
            )

    for link in ManuscriptReference.objects.filter(reference=reference).select_related(
        "manuscript__project"
    ):
        ms = link.manuscript
        add(
            "manuscript",
            ms,
            title=ms.title,
            project=ms.project,
            how="bibliography",
            url=f"/manuscripts/{ms.pk}",
            detail=f"{ms.get_status_display()} · cited as {link.cite_key}",
        )

    for ev in Evidence.objects.filter(reference=reference).select_related("hypothesis__project"):
        add(
            "evidence",
            ev,
            title=ev.hypothesis.statement,
            project=ev.hypothesis.project,
            how=ev.direction,
            url=f"/projects/{ev.hypothesis.project.slug}/research",
            detail=ev.summary[:160],
        )

    order = ("manuscript", "evidence", "note", "decision", "experiment", "protocol", "capture")
    counts = {kind: sum(1 for r in rows if r["kind"] == kind) for kind in order}
    rows.sort(key=lambda r: (order.index(r["kind"]), r["title"].lower()))
    return {
        "reference": reference.pk,
        "key": key,
        "total": len(rows),
        "counts": counts,
        "rows": rows,
    }
