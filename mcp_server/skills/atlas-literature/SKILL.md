---
name: atlas-literature
description: Run a literature workflow in Atlas — add papers by DOI or arXiv id, manage the reading queue and reading status, pull highlights and PDF text, build the review matrix and draft a synthesis note. Use when the user mentions papers, references, citations, a reading list, a literature review, or asks "what does the literature say".
---

# Atlas: literature

## Add papers

- `add_reference_by_doi` (accepts DOIs and arXiv ids) with the project slug. Metadata
  comes from Crossref/OpenAlex; the reference joins the global library and is linked to
  the project with reading status *to read*.
- Many at once: `import_references` (BibTeX text) or `import_from_zotero`.
- After adding, run `find_duplicates` if the user pasted a list; `merge_references`
  only on the user's say-so.

## Read

- `get_reading_queue` (sorted by priority) → suggest the next paper.
- `fetch_pdf` when a paper has no PDF; `search_pdf_text` / `search_in_pdf` to find a
  passage across the project's PDFs or inside one.
- `set_reading_status` as the user reports progress: to_read → skimmed → read → annotated.
- `browse_library` for "what do I have by X?", "unread papers tagged Y", "papers with no PDF" —
  every filter the Library rail offers (author, q, year range, venue, tag, project + status,
  has_pdf, untagged / unfiled / needs_metadata, sort); rows are compact and carry `progress`.
- `get_reading_progress` for "where was I?" (a paper's remembered page, or with no id the papers
  the user is in the middle of); `set_reading_position` when they tell you the page they reached.
- `list_highlights` / `get_highlights_markdown` to quote what the user marked;
  `add_highlight` to record a passage the user dictates (with page and comment).
- `get_reading_notes` / `set_reading_notes` for the per-project notes on a paper.

## Synthesise

1. `get_review_matrix` — papers × themes. `suggest_review_themes` proposes columns from the
   papers themselves; add the good ones with `add_review_theme`;
   mark cells with `set_review_mark` (marked + a one-line finding).
2. `get_synthesis_scaffold` → draft the synthesis; write it with `add_note` (Markdown,
   cite papers as `@bibtex_key` so Atlas links them) and offer `export_note`.
3. `discover_related` to suggest papers the library is missing; `run_bib_check` before
   any export; `export_bibtex` / `format_citations` for the user's writing tool.

## Conventions

- Cite by `bibtex_key` in notes; never invent keys — read them from the tools.
- Reading status is the user's judgement; only change it when they say so.
