"""Toolsets: the Atlas MCP server offers 150-odd tools, Claude needs about twenty of them on a
normal day (#540, owner: "154 tools is too much — it should be simpler for Claude").

Every tool belongs to exactly one *area*; **core** is a curated cross-cut of the areas that is
loaded by default. The rest stay registered but hidden until asked for — by the
``ATLAS_MCP_TOOLSETS`` environment variable at launch (``core`` (default), ``all``, or a
comma/space list such as ``core,library,writing``) or mid-conversation through the
``enable_toolset`` tool, which adds the area's tools and tells the client the list changed.

Django-free, like the rest of ``mcp_server`` (``core/mcp_connect.py`` imports it to show the
Connect page what is on by default).
"""

from __future__ import annotations

import os

ENV = "ATLAS_MCP_TOOLSETS"
DEFAULT = "core"
CORE_LIMIT = 26

# name → (one-line "use when", tools). Order = the order they are shown.
AREAS: dict[str, tuple[str, tuple[str, ...]]] = {
    "plan": (
        "phases, milestones, roadmap, plan reviews, drift, status updates, new projects",
        (
            "list_projects",
            "get_project_overview",
            "get_plan",
            "complete_milestone",
            "get_status_update",
            "get_plan_drift",
            "get_plan_calibration",
            "get_plan_review",
            "finish_plan_review",
            "fix_plan_conflicts",
            "move_milestone",
            "set_milestone_dependencies",
            "get_plan_outline",
            "set_plan_outline",
            "get_roadmap",
            "get_phase_report",
            "close_phase",
            "set_phase_dates",
            "get_week_focus",
            "get_timeline",
            "get_weekly_review",
            "list_project_templates",
            "create_project",
            "import_projects_folder",
        ),
    ),
    "library": (
        "papers: add, read, tag, export, cite, watches (retractions, preprints, citations, feeds), the review matrix",
        (
            "add_reference_by_doi",
            "browse_library",
            "get_reading_queue",
            "set_reading_status",
            "check_retractions",
            "check_preprints",
            "upgrade_preprint",
            "get_new_citations",
            "check_citations",
            "dismiss_citations",
            "list_feeds",
            "add_feed",
            "update_feed",
            "remove_feed",
            "refresh_feeds",
            "get_feed_items",
            "add_feed_item",
            "dismiss_feed_items",
            "get_reading_progress",
            "set_reading_position",
            "run_bib_check",
            "import_references",
            "import_from_zotero",
            "discover_related",
            "export_bibtex",
            "export_references",
            "format_citations",
            "list_library_tags",
            "tag_references",
            "find_duplicates",
            "merge_references",
            "get_reference_tldr",
            "get_related_in_library",
            "get_reference_usage",
            "list_highlights",
            "add_highlight",
            "get_highlights_markdown",
            "get_reading_notes",
            "set_reading_notes",
            "fetch_pdf",
            "search_pdf_text",
            "search_in_pdf",
            "get_review_matrix",
            "set_review_mark",
            "add_review_theme",
            "suggest_review_themes",
            "get_synthesis_scaffold",
        ),
    ),
    "notes": (
        "notes, wiki-links, tags, history, the knowledge graph, note templates, prompts",
        (
            "add_note",
            "list_notes",
            "get_note",
            "update_note",
            "list_note_tags",
            "get_note_links",
            "get_note_outline",
            "get_related_notes",
            "get_project_graph",
            "get_note_graph",
            "list_note_revisions",
            "get_note_revision",
            "restore_note_revision",
            "link_mentions",
            "create_note_from_template",
            "export_note",
            "list_prompts",
            "get_prompt",
        ),
    ),
    "writing": (
        "manuscripts: status, bibliography, cite check, submissions, reviews, pre-flight, venue limits",
        (
            "list_manuscripts",
            "get_manuscript",
            "get_writing_progress",
            "duplicate_manuscript",
            "draft_related_work",
            "get_manuscript_bibliography",
            "add_manuscript_reference",
            "remove_manuscript_reference",
            "manuscript_cite_check",
            "add_submission_event",
            "log_reviews",
            "get_response_progress",
            "submit_manuscript",
            "get_venue_turnaround",
            "preflight_manuscript",
            "get_manuscript_budget",
            "set_venue_limits",
        ),
    ),
    "studio": (
        "the LaTeX source tree: files, figures, compile, lint and fixes, find/replace, figure audit",
        (
            "list_manuscript_files",
            "read_manuscript_file",
            "write_manuscript_file",
            "attach_manuscript_figure",
            "set_main_file",
            "compile_manuscript",
            "get_compile_status",
            "get_compile_diagnostics",
            "compile_and_wait",
            "latex_word_count",
            "lint_manuscript",
            "fix_lint",
            "search_manuscript",
            "replace_in_manuscript",
            "audit_figures",
        ),
    ),
    "inbox": (
        "capture and triage, the Today list, the dashboard and the daily brief",
        (
            "quick_capture",
            "list_inbox",
            "enrich_capture",
            "triage_captures",
            "get_inbox_history",
            "snooze_capture",
            "convert_capture",
            "list_todos",
            "add_todo",
            "complete_todo",
            "snooze_todo",
            "reorder_todos",
            "get_dashboard",
            "get_daily_brief",
            "get_day_activity",
            "search",
        ),
    ),
    "research": (
        "hypotheses and evidence, the lab log, protocols",
        (
            "add_hypothesis",
            "set_hypothesis_status",
            "add_evidence",
            "log_experiment",
            "list_protocols",
            "add_protocol",
            "new_protocol_version",
        ),
    ),
    "files": (
        "documents and the project's file workspace",
        (
            "list_documents",
            "list_project_files",
            "read_project_file",
            "write_project_file",
        ),
    ),
    "ops": (
        "diagnostics, snapshots and the backup destination, automations, achievements, these toolsets",
        (
            "get_diagnostics",
            "take_snapshot",
            "get_backup_destination",
            "set_backup_destination",
            "list_bots",
            "run_bot",
            "toggle_bot",
            "get_achievements",
            "list_toolsets",
            "enable_toolset",
        ),
    ),
}

# What a normal day needs. Everything else is one enable_toolset away.
CORE: tuple[str, ...] = (
    "list_toolsets",
    "enable_toolset",
    "list_projects",
    "get_project_overview",
    "get_plan",
    "complete_milestone",
    "get_dashboard",
    "get_daily_brief",
    "search",
    "quick_capture",
    "list_inbox",
    "list_todos",
    "add_todo",
    "complete_todo",
    "add_reference_by_doi",
    "browse_library",
    "get_reading_queue",
    "set_reading_status",
    "add_note",
    "list_notes",
    "get_note",
    "update_note",
    "list_manuscripts",
    "get_manuscript",
    "get_diagnostics",
)

NAMES = ("core", *AREAS)


def all_tools() -> set[str]:
    return {t for _, tools in AREAS.values() for t in tools}


def tools_for(name: str) -> tuple[str, ...]:
    if name == "core":
        return CORE
    return AREAS[name][1]


def parse(raw: str | None) -> list[str]:
    """``"core, library"`` → ``["core", "library"]``; ``"all"`` → every area; unset or empty →
    core; unknown names are dropped (reported by ``apply``); nothing left → core."""
    text = (raw or "").strip().lower()
    if not text:
        return [DEFAULT]
    wanted: list[str] = []
    for piece in text.replace(",", " ").split():
        if piece == "all":
            return list(AREAS)
        if piece in NAMES and piece not in wanted:
            wanted.append(piece)
    return wanted or [DEFAULT]


def unknown(raw: str | None) -> list[str]:
    text = (raw or "").strip().lower()
    return [p for p in text.replace(",", " ").split() if p not in NAMES and p != "all"]


def resolve(names: list[str]) -> set[str]:
    out: set[str] = set(CORE)  # the meta tools and the daily set are always present
    for name in names:
        out.update(tools_for(name))
    return out


def describe(enabled: set[str] | None = None) -> list[dict]:
    """One row per toolset for the Connect page and the ``list_toolsets`` tool."""
    rows = [
        {
            "name": "core",
            "use_when": "the daily set — projects, plan, inbox, to-dos, papers, notes, manuscripts, diagnostics",
            "tools": list(CORE),
            "count": len(CORE),
            "default": True,
        }
    ]
    for name, (use_when, tools) in AREAS.items():
        rows.append(
            {
                "name": name,
                "use_when": use_when,
                "tools": list(tools),
                "count": len(tools),
                "default": False,
            }
        )
    if enabled is not None:
        for row in rows:
            row["enabled"] = all(t in enabled for t in row["tools"])
            row["loaded"] = sum(t in enabled for t in row["tools"])
    return rows


def from_env(environ=None) -> list[str]:
    env = os.environ if environ is None else environ
    return parse(env.get(ENV))
