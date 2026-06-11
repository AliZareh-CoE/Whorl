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


if __name__ == "__main__":
    mcp.run()
