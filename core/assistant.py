"""Assistant panel backend: page context, quick actions, command index, recents."""

from django.urls import Resolver404, resolve, reverse

from documents.models import Document
from literature.models import ProjectReference, Reference
from notes.models import Note
from plans.models import Milestone
from projects.models import Project
from prompts.models import Prompt
from writing.models import Manuscript

COMMANDS_CAP = 400
RECENT_LIMIT = 8

STATIC_PAGES = [
    ("Dashboard", "/"),
    ("Library", "/library/"),
    ("Writing", "/writing/"),
    ("Inbox", "/inbox/"),
    ("Automations", "/automations/"),
    ("Pet", "/pet/"),
]


def assistant_context(path: str) -> dict:
    """Everything the assistant panel needs for the page at ``path``."""
    context, project = _page_context(path)
    return {
        "context": context,
        "actions": _actions(project),
        "commands": _commands(),
        "claude_prompt": _claude_prompt(context, project),
        "recent": _recent(project),
    }


def _page_context(path: str) -> tuple[dict, Project | None]:
    """Best-effort description of where the user is. Never raises."""
    try:
        match = resolve(path or "/")
    except Resolver404:
        return {"page": None}, None
    page = f"{match.namespace}:{match.url_name}" if match.namespace else match.url_name
    context: dict = {"page": page}
    project = None
    slug = match.kwargs.get("slug")
    if slug:
        project = Project.objects.filter(slug=slug).first()
        if project:
            context["project"] = {
                "name": project.name,
                "slug": project.slug,
                "url": project.get_absolute_url(),
            }
    return context, project


def _actions(project: Project | None) -> list[dict]:
    """Page-aware quick actions. GET links only — simple and safe."""

    def action(label, url):
        return {"label": label, "url": url, "method": "get"}

    actions = [
        action("New project", reverse("projects:create")),
        action("Quick capture", reverse("notes:inbox")),
        action("Search", reverse("core:search")),
    ]
    if project:
        slug = {"slug": project.slug}
        actions += [
            action("Open plan", reverse("plans:plan", kwargs=slug)),
            action("Literature", reverse("literature:project", kwargs=slug)),
            action("Reading queue", reverse("literature:queue", kwargs=slug)),
            action("Bib report", reverse("literature:report", kwargs=slug)),
            action("New note", reverse("notes:create", kwargs=slug)),
        ]
    return actions


def _commands() -> list[dict]:
    """Flat index for client-side fuzzy search: static pages, projects, then
    the most-recently-updated notes/references/prompts/manuscripts."""
    commands = [{"title": title, "type": "page", "url": url} for title, url in STATIC_PAGES]
    for name, slug in Project.objects.values_list("name", "slug")[:COMMANDS_CAP]:
        commands.append(
            {
                "title": name,
                "type": "project",
                "url": reverse("projects:overview", kwargs={"slug": slug}),
            }
        )

    remaining = max(COMMANDS_CAP - len(commands), 0)
    if not remaining:
        return commands[:COMMANDS_CAP]

    dated: list[tuple] = []
    note_rows = Note.objects.values_list("title", "pk", "project__slug", "updated_at")
    for title, pk, slug, updated in note_rows[:remaining]:
        url = reverse("notes:detail", kwargs={"slug": slug, "pk": pk})
        dated.append((updated, {"title": title, "type": "note", "url": url}))
    ref_rows = Reference.objects.values_list("pk", "bibtex_key", "title", "updated_at")
    for pk, key, title, updated in ref_rows[:remaining]:
        url = reverse("literature:detail", kwargs={"pk": pk})
        dated.append((updated, {"title": f"{key} — {title}", "type": "reference", "url": url}))
    gallery_url = reverse("prompts:gallery")
    for title, updated in Prompt.objects.values_list("title", "updated_at")[:remaining]:
        dated.append((updated, {"title": title, "type": "prompt", "url": gallery_url}))
    manuscript_rows = Manuscript.objects.values_list("title", "pk", "project__slug", "updated_at")
    for title, pk, slug, updated in manuscript_rows[:remaining]:
        url = reverse("writing:detail", kwargs={"slug": slug, "pk": pk})
        dated.append((updated, {"title": title, "type": "manuscript", "url": url}))

    dated.sort(key=lambda pair: pair[0], reverse=True)
    commands += [item for _, item in dated[:remaining]]
    return commands


def _claude_prompt(context: dict, project: Project | None) -> str:
    """A paste-ready prompt for a Claude session with the Atlas MCP server."""
    page = context.get("page") or "unknown"
    if project:
        slug = project.slug
        prompt = (
            f"Using the atlas MCP tools, help me with the project '{project.name}' "
            f"(slug: {slug}). Current page: {page}. Useful tools: "
            f"get_project_overview('{slug}'), get_plan('{slug}'), "
            f"get_reading_queue('{slug}'), run_bib_check('{slug}'). "
            "Start with an overview and suggest what to work on next."
        )
    else:
        prompt = (
            f"Using the atlas MCP tools, help me organize my research. Current page: {page}. "
            "Useful tools: list_projects(), search(query), get_reading_queue(slug), "
            "quick_capture(text). Start by listing my projects and suggest what to "
            "work on next."
        )
    return prompt[:600]


def _recent(project: Project | None) -> list[dict]:
    """Last few activity items, scoped to the project if there is one."""
    notes = Note.objects.select_related("project")
    milestones = Milestone.objects.filter(completed_at__isnull=False).select_related(
        "phase__project"
    )
    refs = ProjectReference.objects.filter(reading_status__in=["read", "annotated"]).select_related(
        "reference"
    )
    docs = Document.objects.select_related("project")
    if project:
        notes = notes.filter(project=project)
        milestones = milestones.filter(phase__project=project)
        refs = refs.filter(project=project)
        docs = docs.filter(project=project)

    items: list[tuple] = []
    for note in notes.order_by("-updated_at")[:RECENT_LIMIT]:
        items.append((note.updated_at, note.title, note.get_absolute_url(), "note"))
    for milestone in milestones.order_by("-completed_at")[:RECENT_LIMIT]:
        url = reverse("plans:plan", kwargs={"slug": milestone.phase.project.slug})
        items.append((milestone.completed_at, milestone.title, url, "milestone"))
    for link in refs.order_by("-updated_at")[:RECENT_LIMIT]:
        items.append(
            (link.updated_at, link.reference.title, link.reference.get_absolute_url(), "reference")
        )
    for doc in docs.order_by("-created_at")[:RECENT_LIMIT]:
        url = reverse("documents:download", kwargs={"slug": doc.project.slug, "pk": doc.pk})
        items.append((doc.created_at, doc.title, url, "document"))

    items.sort(key=lambda row: row[0], reverse=True)
    return [
        {"title": title, "when": when.date().isoformat(), "url": url, "type": kind}
        for when, title, url, kind in items[:RECENT_LIMIT]
    ]
