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
    """One-glance overview of a project: current phase, progress, next milestones, counts,
    and the manuscripts glance — each live paper with its status clock ("41 d revising"),
    whether a nudge to the editor is fair while it waits on a venue, and the pre-flight
    verdict (ready / fails / warns / summary) while it is being worked on (#479); and the
    literature glance — to-read count, high-priority unread, read this month, the next
    paper up (top of the reading queue) and the last one added (#480); and the notebook
    glance — notes (edited this week, unlinked, the three last touched), the lab log (last
    entry, quiet after two weeks) and the dataset count (#481); and the pulse — twelve weeks
    of activity binned per week with counts by kind, the busiest week, the trailing quiet
    weeks and the last activity date (#483)."""
    return client.get_project_overview(slug)


@mcp.tool()
def get_status_update(slug: str, days: int = 7) -> dict:
    """A paste-ready status update for a project as markdown (#482): the current phase and
    its health, each manuscript's state (status clock, pre-flight readiness, deadline), what
    got done in the last `days` days grouped by kind (milestones, papers read, notes,
    decisions, lab entries…), what is next (overdue first, then due this week, then next
    up), open research questions, and blockers. Use it to draft the weekly note to an
    advisor or to answer "how is project X going?" in one call; `markdown` is the text."""
    return client.get_status_update(slug, days)


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
    """Full-text search across projects, references (title, abstract, PDF text), notes,
    documents, decisions, plans, hypotheses, experiments, protocols, datasets and inbox
    captures — each hit with a snippet and the route to open it."""
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
def attach_manuscript_figure(manuscript_id: int, path: str, file_path: str) -> dict:
    """Put a figure (or any binary: PNG, PDF, JPG, data) from this machine into the manuscript's
    source tree — `file_path` is a local path, `path` where it lands in the manuscript (e.g.
    figures/pilot.png). Replaces an existing asset at that path. Returns the file row plus an
    `include` snippet (\\includegraphics) to paste into the .tex. Text files go through
    write_manuscript_file instead."""
    row = client.attach_manuscript_asset(manuscript_id, path, file_path)
    stem = path.rsplit("/", 1)[-1]
    row = dict(row) if isinstance(row, dict) else {"result": row}
    row["include"] = (
        "\\begin{figure}[t]\n  \\centering\n  \\includegraphics[width=\\linewidth]{"
        + path
        + "}\n  \\caption{"
        + stem.rsplit(".", 1)[0].replace("-", " ").replace("_", " ")
        + "}\n  \\label{fig:"
        + stem.rsplit(".", 1)[0]
        + "}\n\\end{figure}"
    )
    return row


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
def compile_manuscript(manuscript_id: int, force: bool = False) -> dict:
    """Queue a LaTeX compile of the manuscript's current source. Returns immediately; then
    poll get_compile_status until status is 'ok' or 'failed' to read diagnostics and the PDF.
    Identical source is not compiled twice: {"status": "ok", "unchanged": true} means the last
    PDF already matches, {"deduped": true} that a compile of this exact tree is running. Pass
    force=True to compile anyway (e.g. after installing the engine)."""
    return client.compile_manuscript(manuscript_id, force)


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
def add_todo(text: str, project: str = "", due_at: str = "") -> dict:
    """Put something on the owner's Today list (optionally tagged with a project slug).
    `due_at` is an optional ISO-8601 datetime with offset (e.g. 2026-09-07T15:00:00+02:00) —
    the sidebar nudges the owner when it comes within two hours."""
    return client.add_todo(text, project or None, due_at or None)


@mcp.tool()
def complete_todo(todo_id: int, done: bool = True) -> dict:
    """Tick (or untick) an item on the Today list. Find ids with list_todos."""
    return client.complete_todo(todo_id, done)


@mcp.tool()
def get_reference_tldr(reference_id: int) -> dict:
    """tl;dr of a paper section by section: the headings found in its PDF text, each with
    two key sentences and the page it starts on (falls back to the abstract). Local and
    instant — read it before deciding whether to read the paper."""
    return client.get_reference_tldr(reference_id)


@mcp.tool()
def get_related_in_library(reference_id: int) -> list:
    """Papers already in the library that are most similar to this one (TF-IDF cosine over
    title and abstract, computed locally — no network). Each row: id, bibtex_key, title, year,
    score. Use it to suggest what else to read or cite before reaching for discover_related,
    which goes to OpenAlex for papers the library does not have."""
    return client.get_related_in_library(reference_id)


@mcp.tool()
def get_reference_usage(reference_id: int) -> dict:
    """Where this paper appears in Atlas: notes that link or cite it, decisions, experiment
    entries, protocols and captures that mention @key, manuscripts whose bibliography carries
    it, and evidence rows that point at it — grouped, with the route to each. Ask before
    removing a paper, or to find where an argument was used."""
    return client.get_reference_usage(reference_id)


@mcp.tool()
def duplicate_manuscript(
    manuscript_id: int, title: str = "", project: str = "", bibliography: bool = True
) -> dict:
    """Start a new paper from an existing one: copies every source file and asset, the venue
    limits and (by default) the bibliography links into a fresh manuscript in idea status —
    the way researchers reuse their LaTeX skeleton. `project` (a slug) puts the copy in another
    project. Compile state, revisions, comments and submission events stay with the original."""
    return client.duplicate_manuscript(manuscript_id, title or None, project or None, bibliography)


@mcp.tool()
def draft_related_work(manuscript_id: int, path: str = "", overwrite: bool = False) -> dict:
    """Draft a LaTeX `Related work` section from the project's review matrix and save it as
    `sections/related-work.tex` (or `path`) in the manuscript's source tree: one subsection per
    theme, each matrix cell finding a sentence ending in \\citep{key}, papers without a finding
    gathered into one citation, gaps left as comments. Every cited paper is added to the
    manuscript's bibliography, so the cite checker passes. Returns the \\input line to paste
    into main.tex and the LaTeX itself. Set overwrite=True to replace an existing draft."""
    return client.draft_related_work(manuscript_id, path or None, overwrite)


@mcp.tool()
def get_writing_progress(manuscript_id: int, days: int = 30) -> dict:
    """Writing progress for a manuscript: words per day over the last `days`, today's delta,
    this week's total, the streak of consecutive writing days and the best day. Use it to
    answer "how is the paper going?" with numbers."""
    return client.get_writing_progress(manuscript_id, days)


@mcp.tool()
def list_bots() -> dict:
    """The automations (deadline reminders, retraction watch, citation sync, …) with their
    enabled state, last result and the last runs. Bots report to the Inbox."""
    return client.list_bots()


@mcp.tool()
def run_bot(slug: str) -> dict:
    """Run one automation right now (slug from list_bots) and return its result line —
    e.g. run the deadline reminder before a planning conversation."""
    return client.run_bot(slug)


@mcp.tool()
def toggle_bot(slug: str) -> dict:
    """Enable or disable an automation (it flips); returns {"enabled": bool}."""
    return client.toggle_bot(slug)


@mcp.tool()
def reorder_todos(ids: list[int]) -> dict:
    """Put the Today list in this order: the given item ids take the top positions in the
    order given; anything not listed keeps its relative order below them."""
    return client.reorder_todos(ids)


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


@mcp.tool()
def get_roadmap(slug: str) -> dict:
    """The plan as a timeline: each phase's window (real or inferred from milestones), its
    milestones with due dates, a health state (behind / on_track / ahead / blocked / overdue /
    upcoming / done) with a one-line reason, and a finish forecast from the completion pace."""
    return client.get_roadmap(slug)


@mcp.tool()
def set_phase_dates(phase_id: int, start: str = "", end: str = "") -> dict:
    """Reschedule a phase: ISO dates for its target start and/or end (empty = unchanged)."""
    return client.set_phase_dates(phase_id, start or None, end or None)


@mcp.tool()
def get_week_focus(slug: str) -> dict:
    """What to do on this project this week: overdue milestones/tasks first (with days late),
    then everything due within seven days, then the next milestones of the current phase."""
    return client.get_week_focus(slug)


@mcp.tool()
def list_notes(project: str, q: str = "", tag: str = "") -> dict:
    """Notes of a project, newest edited first; `q` filters by text, `tag` by a #tag written
    in the body (#504; notes carry `tags`)."""
    return client.list_notes(project, q, tag)


@mcp.tool()
def list_note_tags(project: str) -> dict:
    """Every #tag used in the project's notes with a count, most used first (#504) — the
    project's own vocabulary; pass one to list_notes(tag=…)."""
    return client.list_note_tags(project)


@mcp.tool()
def get_note(note_id: int) -> dict:
    """A note's title, Markdown body, cited references and backlinks."""
    return client.get_note(note_id)


@mcp.tool()
def update_note(note_id: int, body: str = "", title: str = "") -> dict:
    """Rewrite a note's body and/or title (empty = unchanged). [[Note Title]] links other notes;
    @bibtex_key cites a paper from the library and attaches it to the note. A new title
    rewrites every [[old title]] across the project's notes, decisions, lab entries and
    captures (#502) — the reply's `relinked` counts them."""
    return client.update_note(note_id, body or None, title or None)


@mcp.tool()
def list_note_revisions(note_id: int) -> dict:
    """The note's history (#505), newest first: every state a save replaced, with when, the
    word count and the delta. Read one with get_note_revision, put it back with
    restore_note_revision."""
    return client.list_note_revisions(note_id)


@mcp.tool()
def get_note_revision(note_id: int, revision_id: int) -> dict:
    """One revision of a note: its title, body and a unified diff from it to the note as it
    is now (#505)."""
    return client.get_note_revision(note_id, revision_id)


@mcp.tool()
def restore_note_revision(note_id: int, revision_id: int) -> dict:
    """Put a revision's title and body back on the note (#505). The current state is filed
    as a revision first, so this is undoable; links, citations and tags are re-synced."""
    return client.restore_note_revision(note_id, revision_id)


@mcp.tool()
def get_note_graph(note_id: int, depth: int = 2) -> dict:
    """ "Around this note" (#503): the notes it links to and from, the papers it cites, and
    their neighbours up to `depth` hops (1–3) — nodes carry `hops` and the same facts as the
    project graph (reading status, citations, words); `stats` counts notes, papers, links."""
    return client.get_note_graph(note_id, depth)


@mcp.tool()
def link_mentions(note_id: int, sources: list[int] | None = None) -> dict:
    """Turn unlinked mentions of a note into [[links]] (#502): the first plain occurrence of
    its title in each mentioning note (get_note_links → `mentions`; or only `sources`) is
    wrapped in [[ ]]. Returns the notes that were linked."""
    return client.link_mentions(note_id, sources)


@mcp.tool()
def get_note_links(note_id: int) -> dict:
    """The note's link panel: outgoing [[links]], backlinks, cited references, unresolved
    titles/keys, and notes that mention this title without linking it."""
    return client.get_note_links(note_id)


@mcp.tool()
def create_note_from_template(project: str, kind: str, reference_id: int = 0) -> dict:
    """Start a note from a template: 'literature' (give reference_id — the paper's metadata, @key
    and highlights are filled in), 'daily' (this week's focus as checkboxes; returns today's note if
    it exists), 'meeting', 'experiment', or 'blank'."""
    return client.create_note_from_template(project, kind, reference_id or None)


@mcp.tool()
def export_note(note_id: int, style: str = "apa") -> dict:
    """The note as portable Markdown with a References section formatted in apa / mla / chicago /
    harvard / vancouver / ieee — paste it into a manuscript or send it to a colleague."""
    return client.export_note(note_id, style)


@mcp.tool()
def get_manuscript_bibliography(manuscript_id: int) -> list:
    """The manuscript's bibliography: cite key, title, year, authors for each paper."""
    return client.get_manuscript_bibliography(manuscript_id)


@mcp.tool()
def add_manuscript_reference(
    manuscript_id: int, reference_id: int, cite_key_override: str = ""
) -> list:
    """Add a library paper to a manuscript's bibliography (optionally under a custom cite key).
    Returns the updated bibliography."""
    return client.add_manuscript_reference(manuscript_id, reference_id, cite_key_override)


@mcp.tool()
def remove_manuscript_reference(manuscript_id: int, reference_id: int) -> dict:
    """Remove a paper from a manuscript's bibliography (it stays in the library)."""
    return client.remove_manuscript_reference(manuscript_id, reference_id)


@mcp.tool()
def manuscript_cite_check(manuscript_id: int) -> dict:
    """Check every \\cite key in the manuscript's .tex files against its bibliography: keys
    missing from the bib (with `resolvable` ids when the library knows them), entries never cited,
    and the matched ones."""
    return client.manuscript_cite_check(manuscript_id)


@mcp.tool()
def add_submission_event(manuscript_id: int, kind: str, date: str, notes: str = "") -> dict:
    """Log a submission event: submitted / desk_reject / reviews_received / revision_submitted /
    accepted / rejected / published / note, with an ISO date."""
    return client.add_submission_event(manuscript_id, kind, date, notes)


@mcp.tool()
def log_reviews(manuscript_id: int, text: str, date: str = "", notes: str = "") -> dict:
    """Paste the reviews a manuscript received: Atlas logs a reviews_received event and writes a
    'Response to reviewers' note with one checkbox per reviewer point (R1.1, R1.2, …) and a
    Response slot under each. Returns the event, the note and the point count."""
    return client.log_reviews(manuscript_id, text, date, notes)


@mcp.tool()
def get_response_progress(manuscript_id: int) -> dict | None:
    """How many reviewer points have a final (ticked) response in the newest response note."""
    return client.get_response_progress(manuscript_id)


@mcp.tool()
def submit_manuscript(
    manuscript_id: int, force: bool = False, date: str = "", notes: str = ""
) -> dict:
    """Mark a paper as submitted the careful way: runs the pre-flight first and refuses (HTTP 409
    with the full report) while a blocking check fails — a stale or missing PDF, compile errors,
    undefined references, cite keys missing from the bibliography, a venue limit exceeded, a
    figure file that does not exist. A passed deadline never blocks. With force=true it submits
    anyway and says so in the event. On success the status becomes submitted (from revision:
    under_review, logging revision_submitted), a submission event dated today (or `date`,
    YYYY-MM-DD) is written with the readiness note plus your `notes`, and the manuscript, the
    event and the report come back. Ask the user before forcing."""
    return client.submit_manuscript(manuscript_id, force=force, date=date, notes=notes)


@mcp.tool()
def lint_manuscript(manuscript_id: int) -> dict:
    r"""Static LaTeX style lint over the manuscript's .tex files — the mistakes a compile never
    reports: an unescaped % after a number (comments out the rest of the line), \label before
    \caption (numbers the wrong float), duplicate and undefined labels, a plain space before
    \ref or between a number and its unit (the number wraps), straight "quotes", three dots,
    $$ display math, \begin{center} inside a float, \\ used as a paragraph break, a captioned
    float without a label, e.g./i.e. without a comma, plus the structural pair — an environment
    opened and never closed (or closed without a begin) and unbalanced braces. Each finding has
    file, line, col, rule,
    level (error/warning), message and a suggested fix where one is obvious. Fix the errors
    first; they change what prints."""
    return client.lint_manuscript(manuscript_id)


@mcp.tool()
def search_manuscript(manuscript_id: int, q: str, regex: bool = False, case: bool = False) -> dict:
    """Find in project: every match of q across the manuscript's .tex and .bib files, with
    file, line, column and the whole line for context (500-hit cap, `truncated` says so).
    Plain text by default, case-insensitive unless case=true; regex=true treats q as a
    regular expression. Use it to see where a term, a label or a citation key is used
    before you rename it with replace_in_manuscript."""
    return client.search_manuscript(manuscript_id, q, regex=regex, case=case)


@mcp.tool()
def replace_in_manuscript(
    manuscript_id: int,
    q: str,
    replacement: str,
    regex: bool = False,
    case: bool = False,
    files: list[str] | None = None,
) -> dict:
    r"""Replace every match of q with `replacement` across the manuscript's text files (or
    only the `files` listed), saved like an editor save so the history and the compile
    see the change. In regex mode the replacement may use  / \g<name> groups. Run
    search_manuscript first: the hit list is exactly what this will change. Returns the
    number of replacements and the files touched."""
    return client.replace_in_manuscript(
        manuscript_id, q, replacement, regex=regex, case=case, files=files
    )


@mcp.tool()
def get_venue_turnaround(venue: str, exclude: int | None = None) -> dict:
    """How long does this venue take, going by the owner's own submissions? Pairs every
    submitted / revision_submitted event with the next decision (reviews received, desk
    reject, accepted, rejected) across all manuscripts whose target venue matches
    (case-insensitive) and returns the manuscripts and rounds counted, the median days per
    round, the median for first decisions, and the fastest and slowest. Every manuscript
    also carries a `clock` (since, days, label such as "42 d under review") in
    list_manuscripts / get_manuscript — use both to answer "should I nudge the editor?"."""
    return client.get_venue_turnaround(venue, exclude=exclude)


@mcp.tool()
def audit_figures(manuscript_id: int) -> dict:
    r"""Will every figure print well? One row per \includegraphics in the manuscript's .tex
    files: the asset it resolves to, format, pixel size (read from the PNG/JPEG/GIF header),
    the width it prints at (from width=0.8\textwidth, \columnwidth, cm/in/mm/pt — 6.5 in
    text width), the effective dpi, the file size, and a state: ok, warn (under 300 dpi, or
    over 10 MB), fail (under 150 dpi, or no such file). PDF/EPS/SVG are vector and pass.
    Also lists image assets no figure uses. Use it before a submission and after replacing
    a figure; the detail says how many pixels wide the export needs to be."""
    return client.audit_figures(manuscript_id)


@mcp.tool()
def fix_lint(manuscript_id: int, only: list[dict] | None = None) -> dict:
    r"""Apply the style lint's mechanical fixes to the manuscript's .tex files: Figure~\ref,
    5\,ms, ``quotes'', \ldots, 50\%, e.g., and \[ … \] for a one-line $$ pair. Pass `only`
    as a list of {file, line, rule, col} taken from lint_manuscript to fix a chosen subset;
    omit it to fix everything fixable. Every replacement is checked against the text actually
    there, so a stale finding is skipped, never mis-applied. Returns applied / skipped counts,
    the changed files and the fresh lint. Run lint_manuscript first to see what would change."""
    return client.fix_lint(manuscript_id, only=only)


@mcp.tool()
def preflight_manuscript(manuscript_id: int, network: bool = False) -> dict:
    r"""Is this paper ready to submit? Every readiness check from real data: the compiled PDF
    is up to date with the source, no compile errors, no undefined citations/references, every
    \cite key is in the bibliography (and nothing unused), bibliography hygiene (missing
    fields, duplicates), the venue limits, every \includegraphics path resolves to a file,
    no TODO/FIXME/\todo/?? left in the text, a .bbl kept for arXiv, and venue/deadline/abstract
    set. Each check answers ok / warn / fail / skip with a one-line detail and a fix pointer;
    `ready` is true when nothing fails. network=true also resolves DOIs and checks retractions
    (slow). Run it before "submit", then fix the fails in order."""
    return client.preflight_manuscript(manuscript_id, network=network)


@mcp.tool()
def get_manuscript_budget(manuscript_id: int) -> dict:
    """How the manuscript sits against its venue limits: words, abstract words, figures, tables,
    references and pages (after a compile), each as used / limit with an ok / near / over state."""
    return client.get_manuscript_budget(manuscript_id)


@mcp.tool()
def set_venue_limits(manuscript_id: int, limits: dict) -> dict:
    """Set the target venue's limits, e.g. {"words": 8000, "abstract_words": 250, "figures": 6,
    "tables": 4, "references": 60, "pages": 12}; unknown keys are ignored."""
    return client.set_venue_limits(manuscript_id, limits)


@mcp.tool()
def get_dashboard() -> dict:
    """What should I work on today, everywhere? Needs-attention (overdue milestones, deadlines
    inside two weeks, untriaged inbox), this week's items across every active project, projects
    with progress and phase health, monthly stats, upcoming milestones and deadlines, and
    `reading` — the head of the reading queue across every active project (highest priority,
    then longest waiting) with the unread and high-priority counts (#486); and `writing` —
    every live manuscript across those projects by urgency, each with its status clock, a
    nudge flag while a venue sits on it, the pre-flight readiness while it is being worked on,
    and the deadline (#487). Each active project carries its `pulse` (twelve weekly activity
    counts, total, quiet_weeks, last_activity) and `attention.quiet` lists active projects
    silent for three weeks or more (#489). `trends` carries six months per stat (papers read,
    notes, milestones, lab entries, words) and last month's value for a delta (#490)."""
    return client.get_dashboard()


@mcp.tool()
def get_daily_brief() -> dict:
    """The morning note, ready to paste (#491): what needs you across every project (overdue
    milestones, deadlines, papers a venue has sat on, quiet projects, the inbox, a stale
    backup), what is on your list, this week everywhere, the next papers to read, every live
    manuscript with its clock and readiness, each active project with its rhythm, and this
    month's numbers against last month. `markdown` is the text; use it to answer "what
    should I do today?" in one call, or to draft a daily journal entry."""
    return client.get_daily_brief()


@mcp.tool()
def get_day_activity(date: str = "") -> dict:
    """What happened on one day, across every project (#492): milestones done, papers added
    or read, notes, decisions, lab entries, hypotheses, documents, submission events and
    compiles, each with its project and a link. `date` is YYYY-MM-DD (blank = today). Use it
    for "what did I do on Tuesday?" or to fill in a lab notebook after the fact."""
    return client.get_day_activity(date or None)


@mcp.tool()
def list_inbox(snoozed: bool = False) -> dict:
    """Captures waiting for triage, each with a `hint` (suggested target, any DOI / arXiv id /
    URL found in the text, and since #494 `project` — the active project whose vocabulary the
    capture shares most, with the matching terms, or null; and since #500 `due` / `due_time`
    — a date or time read from the line). Snoozed captures (#495) are left
    out until their day comes; pass snoozed=True to list the sleeping ones with their
    `snoozed_until`."""
    return client.list_inbox(snoozed)


@mcp.tool()
def enrich_capture(capture_id: int, force: bool = False) -> dict:
    """Look up the page behind a link capture and remember its title (#499): the reply is the
    capture with `link_title` (and `link_error` when the fetch failed — private hosts, non-http
    links and timeouts are refused). force=True fetches again."""
    return client.enrich_capture(capture_id, force)


@mcp.tool()
def triage_captures(ids: list[int], action: str, project: str = "", until: str = "") -> dict:
    """Triage many captures in one call (#497): action 'file' (under project slug), 'dismiss',
    'snooze' (until: tomorrow / monday / next-week / weekend / YYYY-MM-DD), 'todo' (each
    becomes a Today item, project optional) or 'wake'. Only untriaged captures change; the
    reply lists the ids that did. Use list_inbox first to pick the ids."""
    return client.triage_captures(ids, action, project, until)


@mcp.tool()
def get_inbox_history(limit: int = 30) -> dict:
    """ "Where did that thought go?" — the last captures that left the inbox, newest first,
    each with its outcome: converted (with `became` — kind, id, title, app_url and whether the
    object still exists), filed under a project, or dismissed; plus when (#496)."""
    return client.get_inbox_history(limit)


@mcp.tool()
def snooze_capture(capture_id: int, until: str = "tomorrow") -> dict:
    """ "Not now": park a capture until `until` — tomorrow, monday, next-week, weekend or a
    YYYY-MM-DD after today. It leaves the inbox and every untriaged count and comes back on
    that day; an empty `until` wakes it immediately (#495)."""
    return client.snooze_capture(capture_id, until)


@mcp.tool()
def convert_capture(
    capture_id: int, target: str, project: str = "", phase_id: int = 0, due: str = "", tz: str = ""
) -> dict:
    """Triage a capture into a first-class object and mark it processed. target: 'paper' (adds
    the DOI/arXiv paper, filed into project), 'note', 'todo' (Today list), 'milestone' (into
    phase_id or the project's current phase; optional ISO due), or 'decision'. A date or time
    written in the capture ("by Friday 3pm", "Oct 1", "in 3 days" — see the hint's `due` /
    `due_time`) becomes the todo's due time or the milestone's due date (#500); `tz` is the
    owner's zone ("Europe/Berlin" or "+05:30"), this machine's offset when blank."""
    return client.convert_capture(capture_id, target, project, phase_id, due, tz)


@mcp.tool()
def set_review_mark(
    slug: str, reference: str, theme: str, marked: bool = True, note: str = ""
) -> dict:
    """Fill one cell of the project's literature review matrix: `reference` is an id or bibtex
    key, `theme` an id or name (a new name adds the column), `note` the extracted finding (≤300
    chars). marked=False clears the cell. Read the paper first (search_in_pdf, list_highlights)."""
    return client.set_review_mark(slug, reference, theme, marked, note)


@mcp.tool()
def add_review_theme(slug: str, name: str) -> dict:
    """Add a theme (column) to the project's review matrix, e.g. 'Sample size' or 'Load type'."""
    return client.add_review_theme(slug, name)


@mcp.tool()
def add_hypothesis(project: str, statement: str, status: str = "proposed") -> dict:
    """Propose a hypothesis in a project's ledger (status: proposed / testing / …)."""
    return client.add_hypothesis(project, statement, status)


@mcp.tool()
def set_hypothesis_status(hypothesis_id: int, status: str) -> dict:
    """Set a hypothesis to proposed / testing / supported / contradicted / inconclusive / abandoned.
    The ledger also suggests a status from the evidence balance (suggested_status)."""
    return client.set_hypothesis_status(hypothesis_id, status)


@mcp.tool()
def add_evidence(
    hypothesis_id: int, direction: str, summary: str, reference_id: int = 0, note_id: int = 0
) -> dict:
    """Attach evidence to a hypothesis: direction supports / contradicts / mixed, a one-line
    summary, and optionally the paper (reference_id) and/or note (note_id) it comes from."""
    return client.add_evidence(hypothesis_id, direction, summary, reference_id, note_id)


@mcp.tool()
def log_experiment(
    project: str,
    title: str,
    body: str = "",
    hypothesis_ids: list[int] | None = None,
    date: str = "",
) -> dict:
    """Write a lab-notebook entry (Markdown body: setup, what happened, outcome), dated today
    unless `date` is given, linked to the hypotheses it tests."""
    return client.log_experiment(project, title, body, hypothesis_ids, date)


@mcp.tool()
def suggest_review_themes(project: str) -> dict:
    """Theme candidates for a project's review matrix: keyword phrases that recur across its
    papers' titles and abstracts, ranked by how many papers mention them, minus the themes that
    already exist. Add the good ones with add_review_theme."""
    return client.suggest_review_themes(project)


@mcp.tool()
def get_diagnostics(network: bool = False) -> dict:
    """Why didn't it work? The same report as the app's Diagnostics page: version, platform,
    data folder, database, LaTeX engine path, background-job mode, API-key state, the updater
    endpoints (probed only when network=true), the last failed compile's log and the tail of
    the desktop server log — plus a plain-text `text` field to paste into a bug report."""
    return client.get_diagnostics(network=network)


@mcp.tool()
def take_snapshot(list_only: bool = False) -> dict:
    """Back Atlas up before a big change: writes a snapshot zip (database + every file) into
    the app's backups folder and rotates the old ones — the same daily automatic snapshot,
    on demand. Returns the file written, what was removed and the folder status. With
    list_only=true it only reports the status: folder, how many are kept, the newest one,
    whether the desktop scheduler runs, the last failure, and the files on disk. Do this
    first when a request will delete or rewrite many things (bulk status changes, a plan
    outline rewrite, a restore)."""
    return client.take_snapshot(list_only=list_only)


@mcp.tool()
def get_achievements() -> dict:
    """The research achievements ledger (fun / steady / hard / souls tiers): every achievement
    with progress toward it and when it unlocked, the score and rank, the five closest to
    unlocking, and the souls-mode counters (deaths, bonfires, bosses, souls). Good for
    "what should I go for next?" and for celebrating a fresh unlock."""
    return client.get_achievements()


# Keep this at the very end: `python -m mcp_server.server` runs the module as __main__, and
# any tool declared below the entry point would never be registered (29 of 88 tools were
# missing that way until 2026-09-06).
def self_check() -> dict:
    """Prove the wiring end to end without an MCP client: reach the API with the configured
    URL + key and count the tools this server offers. Used by `--check` (the Connect page's
    "Test the connection" runs the very command Claude Code will launch)."""
    import asyncio
    import os

    base = os.environ.get("ATLAS_API_URL", "http://127.0.0.1:8000").rstrip("/")
    try:
        projects = client.list_projects()
    except Exception as exc:  # noqa: BLE001 - every failure must be reported, not raised
        return {"ok": False, "api_url": base, "error": str(exc)}
    count = (
        projects.get("count", len(projects.get("results", [])))
        if isinstance(projects, dict)
        else len(projects)
    )
    tools = asyncio.run(mcp.list_tools())
    return {"ok": True, "api_url": base, "projects": count, "tools": len(tools)}


def main(argv: list[str] | None = None) -> int:
    import json
    import sys

    args = sys.argv[1:] if argv is None else argv
    if "--check" in args:
        result = self_check()
        print(json.dumps(result))
        return 0 if result["ok"] else 1
    mcp.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
