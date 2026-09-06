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
