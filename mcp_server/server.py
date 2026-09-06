"""Atlas MCP server: exposes the Atlas API as tools for Claude.

Run with:  ATLAS_API_URL=http://127.0.0.1:8000 ATLAS_API_KEY=... python -m mcp_server.server
"""

from mcp.server.fastmcp import FastMCP

from . import client

mcp = FastMCP("atlas")


@mcp.tool()
def list_projects() -> dict:
    """List every project with name, slug, status, and description."""
    return client.list_projects()


@mcp.tool()
def get_project_overview(slug: str) -> dict:
    """One-glance overview of a project: current phase, progress, next milestones, counts."""
    return client.get_project_overview(slug)


@mcp.tool()
def get_plan(slug: str) -> dict:
    """The project's full plan: ordered phases with milestones (ids, due dates, overdue flags) and tasks."""
    return client.get_plan(slug)


@mcp.tool()
def complete_milestone(milestone_id: int) -> dict:
    """Mark a milestone complete (find ids via get_plan). Progress rolls up automatically."""
    return client.complete_milestone(milestone_id)


@mcp.tool()
def list_documents(project: str) -> dict:
    """List a project's documents with title, folder, size, and file URL."""
    return client.list_documents(project)


@mcp.tool()
def search(query: str) -> dict:
    """Full-text search across projects, references, notes, documents, decisions, and plans."""
    return client.search(query)


@mcp.tool()
def add_reference_by_doi(doi: str, project: str = "") -> dict:
    """Add a reference to the library by DOI or arXiv ID; optionally link it to a project (slug)."""
    return client.add_reference_by_doi(doi, project or None)


@mcp.tool()
def get_reading_queue(project: str) -> list:
    """The project's reading queue: unread/skimmed references, highest priority first."""
    return client.get_reading_queue(project)


@mcp.tool()
def set_reading_status(project_reference_id: int, status: str) -> dict:
    """Set reading status for a queue item (ids from get_reading_queue).

    Status is one of: to_read, skimmed, read, annotated.
    """
    return client.set_reading_status(project_reference_id, status)


@mcp.tool()
def add_note(project: str, title: str, body: str = "") -> dict:
    """Create a markdown note in a project. [[Wiki-links]] to other note titles become links."""
    return client.add_note(project, title, body)


@mcp.tool()
def quick_capture(text: str) -> dict:
    """Drop a thought into the global inbox for later triage."""
    return client.quick_capture(text)


@mcp.tool()
def run_bib_check(project: str, network: bool = False) -> dict:
    """Run bibliography checks for a project: duplicates, missing fields, and (with network=True) DOI resolution + retractions."""
    return client.run_bib_check(project, network)


@mcp.tool()
def list_prompts(query: str = "") -> dict:
    """The owner's saved prompt gallery; optionally filter by a search query."""
    return client.list_prompts(query)


@mcp.tool()
def get_prompt(prompt_id: int) -> dict:
    """Fetch one saved prompt (full body) by id from list_prompts."""
    return client.get_prompt(prompt_id)


@mcp.tool()
def get_review_matrix(project: str) -> dict:
    """The project's literature review matrix: themes, papers, and which paper covers which theme."""
    return client.get_review_matrix(project)


@mcp.tool()
def get_synthesis_scaffold(project: str) -> dict:
    """A theme-organized literature-review scaffold for the project — each review theme with
    its marked papers, plus a synthesis prompt. Use it as a skeleton to draft a review section.
    Read-only: does not create a note."""
    return client.get_synthesis_scaffold(project)


@mcp.tool()
def get_timeline(project: str) -> dict:
    """The project's full research timeline: every dated event (milestones completed, papers
    added/read, notes, decisions, experiments, hypotheses, documents, manuscript submissions)
    newest first, plus a paste-ready oldest-first markdown chronology for a paper's
    methods/history section."""
    return client.get_timeline(project)


@mcp.tool()
def get_weekly_review(project: str = "", weeks_back: int = 0) -> dict:
    """What happened in a research week — papers read, notes written, milestones completed,
    decisions, and experiments. Pass a project slug to scope it, or leave blank for everything;
    weeks_back=0 is this week, 1 is last week, etc."""
    return client.get_weekly_review(project or None, weeks_back)


@mcp.tool()
def list_manuscripts(project: str = "") -> dict:
    """List the owner's manuscripts (LaTeX papers), optionally scoped to one project slug.
    Each includes its title, status, and file summary."""
    return client.list_manuscripts(project or None)


@mcp.tool()
def get_manuscript(manuscript_id: int) -> dict:
    """Full detail for one manuscript, including its source file tree (paths, kinds, which is
    the main file) and current compile status."""
    return client.get_manuscript(manuscript_id)


@mcp.tool()
def list_manuscript_files(manuscript_id: int) -> dict:
    """The source files of a manuscript (main.tex, sections, .bib, figures): id, path, kind."""
    return client.list_manuscript_files(manuscript_id)


@mcp.tool()
def read_manuscript_file(file_id: int) -> dict:
    """Read one manuscript source file's content by its id (from list_manuscript_files)."""
    return client.read_manuscript_file(file_id)


@mcp.tool()
def write_manuscript_file(manuscript_id: int, path: str, content: str) -> dict:
    """Create or overwrite a manuscript source file at `path` (e.g. 'main.tex' or
    'sections/intro.tex') with `content`. Use this to edit the owner's LaTeX, then call
    compile_manuscript and poll get_compile_status to see errors and the PDF."""
    return client.write_manuscript_file(manuscript_id, path, content)


@mcp.tool()
def set_main_file(file_id: int) -> dict:
    """Mark a manuscript file as the main file that the compiler builds."""
    return client.set_main_file(file_id)


@mcp.tool()
def compile_manuscript(manuscript_id: int) -> dict:
    """Queue a LaTeX compile of the manuscript's current source. Returns immediately; then
    poll get_compile_status until status is 'ok' or 'failed' to read diagnostics and the PDF."""
    return client.compile_manuscript(manuscript_id)


@mcp.tool()
def get_compile_status(manuscript_id: int) -> dict:
    """The latest compile result: status ('running'/'ok'/'failed'), parsed diagnostics
    [{level, file, line, message}], the compiled PDF url, and the log tail on failure.
    Poll this after compile_manuscript to drive an edit -> compile -> fix loop."""
    return client.get_compile_status(manuscript_id)


@mcp.tool()
def get_compile_diagnostics(manuscript_id: int) -> list:
    """Just the parsed diagnostics [{level, file, line, message}] from the manuscript's last
    compile — a tight list to reason over when fixing LaTeX errors."""
    return client.get_compile_diagnostics(manuscript_id)


@mcp.tool()
def compile_and_wait(manuscript_id: int, timeout_seconds: int = 120) -> dict:
    """Compile the manuscript and block until it finishes (ok/failed) or the timeout, then
    return the final status (diagnostics + pdf url). The one-shot edit->compile->result tool."""
    return client.compile_and_wait(manuscript_id, timeout_seconds)


@mcp.tool()
def latex_word_count(manuscript_id: int) -> dict:
    """Approximate word/header/caption/inline-math counts across the manuscript's text files."""
    return client.latex_word_count(manuscript_id)


if __name__ == "__main__":
    mcp.run()


@mcp.tool()
def list_project_templates() -> list:
    """Available project scaffolds — built-in and user-saved — for create_project."""
    return client.list_project_templates()


@mcp.tool()
def create_project(name: str, slug: str = "", template: str = "") -> dict:
    """Create a project. Pass a template key/name to scaffold organized folders + files."""
    return client.create_project(name, slug, template)


@mcp.tool()
def list_project_files(project: str) -> dict:
    """The project's whole file tree: folders + files (general docs and manuscript sources)."""
    return client.list_project_files(project)


@mcp.tool()
def read_project_file(document_id: int) -> dict:
    """Read a file node's text content by its id (from list_project_files)."""
    return client.read_project_file(document_id)


@mcp.tool()
def write_project_file(project: str, path: str, content: str) -> dict:
    """Create or overwrite a general text file at `path` in the project's file tree."""
    return client.write_project_file(project, path, content)


@mcp.tool()
def list_protocols(project: str = "") -> dict:
    """List versioned lab/analysis protocols, optionally scoped to one project slug. Each
    carries its title, version, and is_current flag (the head of its revision chain)."""
    return client.list_protocols(project or None)


@mcp.tool()
def add_protocol(project: str, title: str, body: str = "") -> dict:
    """Create a new protocol (version 1) in a project. `body` is markdown — the steps."""
    return client.add_protocol(project, title, body)


@mcp.tool()
def new_protocol_version(protocol_id: int, body: str = "", title: str = "") -> dict:
    """Revise a protocol by creating its next version (immutable history): pass the updated
    body and/or title; anything omitted carries over from the current version."""
    return client.new_protocol_version(protocol_id, body or None, title or None)


@mcp.tool()
def import_references(text: str, format: str = "auto", project: str = "") -> dict:
    """Import references from pasted BibTeX, CSL-JSON, or RIS text (format 'auto' sniffs it).
    Deduplicated by DOI / arXiv id / title+year; returns created/existing/failed counts and
    per-item results. Optional project slug links every imported paper to that project."""
    return client.import_references(text, format, project or None)


@mcp.tool()
def import_from_zotero(project: str = "") -> dict:
    """Pull the entire library from a Zotero 7 running on this computer (its local API on
    port 23119 must be enabled: Settings → Advanced → allow other applications). Deduplicated;
    optional project slug links everything to that project."""
    return client.import_from_zotero(project or None)


@mcp.tool()
def discover_related(reference_id: int, kind: str = "similar", limit: int = 12) -> dict:
    """Grow the library from one paper: OpenAlex rows for kind='similar' (related work),
    'references' (what it cites), or 'cited_by' (what cites it, most-cited first). Each row
    carries in_library / library_id; addable rows have a DOI — add them with add_reference_by_doi."""
    return client.discover_related(reference_id, kind, limit)


@mcp.tool()
def export_bibtex(reference_ids: list[int] | None = None, project: str = "") -> str:
    """BibTeX for a list of reference ids, or for every reference linked to a project (slug)."""
    return client.export_bibtex(reference_ids, project or None)


@mcp.tool()
def format_citations(reference_ids: list[int], style: str = "apa") -> dict:
    """Formatted citations for reference ids in apa, mla, chicago, harvard, vancouver, or ieee:
    a full bibliography (text + html) and each entry's in-text form. Find ids via search or
    get_reading_queue."""
    return client.format_citations(reference_ids, style)


@mcp.tool()
def list_todos(include_done: bool = False) -> dict:
    """The owner's personal Today list (plain to-dos, not plan tasks). Open items by default."""
    return client.list_todos(include_done)


@mcp.tool()
def add_todo(text: str, project: str = "") -> dict:
    """Put something on the owner's Today list (optionally tagged with a project slug)."""
    return client.add_todo(text, project or None)


@mcp.tool()
def complete_todo(todo_id: int, done: bool = True) -> dict:
    """Tick (or untick) an item on the Today list. Find ids with list_todos."""
    return client.complete_todo(todo_id, done)


@mcp.tool()
def list_library_tags() -> dict:
    """Library tags (global labels on references) with how many papers carry each."""
    return client.list_library_tags()


@mcp.tool()
def tag_references(reference_ids: list[int], tag: str, remove: bool = False) -> dict:
    """Put a tag on (or take it off) many references at once; missing tags are created."""
    return client.tag_references(reference_ids, tag, remove)


@mcp.tool()
def find_duplicates() -> dict:
    """Probable duplicate papers in the library (same DOI/arXiv id or near-identical titles),
    grouped, each with the most complete record suggested as `keep`."""
    return client.find_duplicates()


@mcp.tool()
def merge_references(keep: int, merge: list[int]) -> dict:
    """Merge duplicate references into `keep`: project links, tags, notes, manuscript
    bibliographies, evidence, citations, comments, and the PDF move over; the others are deleted."""
    return client.merge_references(keep, merge)


@mcp.tool()
def list_highlights(reference_id: int) -> dict:
    """Passages highlighted while reading a paper: page, text, comment, colour, project."""
    return client.list_highlights(reference_id)


@mcp.tool()
def add_highlight(
    reference_id: int, text: str, page: int | None = None, project: str = "", comment: str = ""
) -> dict:
    """Save a highlight on a paper (optionally at a page, with a comment). With a project slug it
    is also mirrored into that project's "Highlights — <key>" note and the paper is marked skimmed."""
    return client.add_highlight(reference_id, text, page=page, project=project, comment=comment)


@mcp.tool()
def get_highlights_markdown(reference_id: int) -> dict:
    """Every highlight of a paper as one Markdown block of quotes with page numbers — paste-ready."""
    return client.get_highlights_markdown(reference_id)


@mcp.tool()
def get_reading_notes(reference_id: int) -> list:
    """Reading notes for a paper in each project it is filed in (with project_reference_id)."""
    return client.get_reading_notes(reference_id)


@mcp.tool()
def set_reading_notes(project_reference_id: int, notes: str) -> dict:
    """Replace the reading notes on one project link (see get_reading_notes for the id)."""
    return client.set_reading_notes(project_reference_id, notes)


@mcp.tool()
def fetch_pdf(reference_id: int) -> dict:
    """Try to attach an open-access PDF to a paper (arXiv first, then Unpaywall by DOI)."""
    return client.fetch_pdf(reference_id)


@mcp.tool()
def search_pdf_text(query: str, project: str = "", limit: int = 30) -> list:
    """Search inside the full text of every attached PDF (optionally one project). Each hit gives
    the paper, the first page containing the query, a snippet, and up to three matching pages."""
    return client.search_pdf_text(query, project=project, limit=limit)


@mcp.tool()
def search_in_pdf(reference_id: int, query: str) -> list:
    """Pages of one paper's PDF that contain the query, each with a snippet — cite the page."""
    return client.search_in_pdf(reference_id, query)


@mcp.tool()
def get_plan_outline(slug: str) -> dict:
    """The project's plan as a Markdown outline: '# phase [status] (start → end)', '> objective',
    '- [ ] milestone (due YYYY-MM-DD)', indented '- [ ] task', each with a {#id} token. Edit and
    send it back with set_plan_outline; keep the ids to rename without losing history."""
    return client.get_plan_outline(slug)


@mcp.tool()
def set_plan_outline(slug: str, markdown: str, dry_run: bool = False) -> dict:
    """Rewrite the plan from an outline (same grammar as get_plan_outline). Lines without {#id}
    create objects, missing ids delete them, checkboxes set completion. Use dry_run=True first to
    see what would be created, renamed and deleted; parse errors name the line."""
    return client.set_plan_outline(slug, markdown, dry_run=dry_run)
