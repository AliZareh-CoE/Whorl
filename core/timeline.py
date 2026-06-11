"""Research timeline ([REV] cycle 95, Backlog #95/#104).

One chronological event stream for a project — milestones, papers, notes, decisions,
experiments, documents, manuscript events, hypotheses — so a project's history reads
like the methods/history section of a paper.
"""


def project_timeline(project) -> list[dict]:
    """Every dated event in the project's life, newest first.

    Each event: {date, kind, label, detail, url}. URLs are SPA paths so the
    timeline page can deep-link every object.
    """
    events: list[dict] = []
    slug = project.slug

    for phase in project.phases.prefetch_related("milestones").all():
        for milestone in phase.milestones.all():
            if milestone.completed_at:
                events.append(
                    {
                        "date": milestone.completed_at.date().isoformat(),
                        "kind": "milestone",
                        "label": milestone.title,
                        "detail": phase.name,
                        "url": f"/projects/{slug}/plan",
                    }
                )

    for link in project.project_references.select_related("reference"):
        ref = link.reference
        events.append(
            {
                "date": link.created_at.date().isoformat(),
                "kind": "paper_added",
                "label": ref.title,
                "detail": ref.bibtex_key,
                "url": f"/references/{ref.pk}",
            }
        )
        # Reading isn't separately timestamped; the link's last update is the best
        # available proxy, so a same-day add+read collapses into the add event.
        if (
            link.reading_status in ("read", "annotated")
            and link.updated_at.date() > link.created_at.date()
        ):
            events.append(
                {
                    "date": link.updated_at.date().isoformat(),
                    "kind": "paper_read",
                    "label": ref.title,
                    "detail": ref.bibtex_key,
                    "url": f"/references/{ref.pk}",
                }
            )

    for note in project.notes.all():
        events.append(
            {
                "date": note.created_at.date().isoformat(),
                "kind": "note",
                "label": note.title,
                "detail": "",
                "url": f"/projects/{slug}/notes/{note.pk}",
            }
        )

    for decision in project.decisions.all():
        events.append(
            {
                "date": decision.decided_on.isoformat(),
                "kind": "decision",
                "label": decision.title,
                "detail": "",
                "url": f"/projects/{slug}/decisions",
            }
        )

    for entry in project.experiment_entries.all():
        events.append(
            {
                "date": entry.date.isoformat(),
                "kind": "experiment",
                "label": entry.title,
                "detail": "",
                "url": f"/projects/{slug}/research",
            }
        )

    for hypothesis in project.hypotheses.all():
        events.append(
            {
                "date": hypothesis.created_at.date().isoformat(),
                "kind": "hypothesis",
                "label": hypothesis.statement,
                "detail": hypothesis.get_status_display(),
                "url": f"/projects/{slug}/research",
            }
        )

    for document in project.documents.all():
        events.append(
            {
                "date": document.created_at.date().isoformat(),
                "kind": "document",
                "label": document.title,
                "detail": "",
                "url": f"/projects/{slug}/documents",
            }
        )

    for manuscript in project.manuscripts.prefetch_related("events", "revisions"):
        for event in manuscript.events.all():
            events.append(
                {
                    "date": event.date.isoformat(),
                    "kind": "manuscript",
                    "label": f"{manuscript.title} — {event.get_kind_display()}",
                    "detail": event.notes[:120],
                    "url": f"/manuscripts/{manuscript.pk}",
                }
            )
        # writing history (beyond-Overleaf B5): the latest successful compile + labeled
        # versions, not the 50 automatic snapshots — keep the timeline calm.
        if manuscript.compiled_at:
            events.append(
                {
                    "date": manuscript.compiled_at.date().isoformat(),
                    "kind": "manuscript_compiled",
                    "label": f"{manuscript.title} — compiled",
                    "detail": "",
                    "url": f"/projects/{slug}/writing/{manuscript.pk}/editor/",
                }
            )
        for revision in manuscript.revisions.all():
            if revision.label and revision.label != "Before restore":
                events.append(
                    {
                        "date": revision.created_at.date().isoformat(),
                        "kind": "manuscript_compiled",
                        "label": f"{manuscript.title} — version “{revision.label}”",
                        "detail": "",
                        "url": f"/projects/{slug}/writing/{manuscript.pk}/editor/",
                    }
                )

    events.sort(key=lambda e: e["date"], reverse=True)
    return events


def timeline_markdown(project, events: list[dict]) -> str:
    """The timeline as chronological (oldest-first) markdown — paste-ready for a
    paper's methods/history section."""
    lines = [f"# Timeline — {project.name}", ""]
    for event in reversed(events):
        kind = event["kind"].replace("_", " ")
        detail = f" ({event['detail']})" if event["detail"] else ""
        lines.append(f"- **{event['date']}** · {kind}: {event['label']}{detail}")
    return "\n".join(lines)
