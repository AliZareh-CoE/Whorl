---
name: atlas-import-projects
description: Bring a folder of existing research projects into Atlas in one go — every subfolder becomes a project with its README, notes, PDFs and files. Use when the user has a projects folder on disk, wants to "add all my old projects", import a directory, or migrate from folders / Obsidian / Zotero-style piles of PDFs.
---

# Atlas: import a projects folder

One folder on the Atlas machine holds one subfolder per project. Atlas turns each subfolder
into a project: the README becomes the description (its first `# heading` the name),
Markdown files become notes, PDFs go into the library linked to the project, `.bib` / `.ris`
files are imported into the library, and every other file becomes a workspace document in
the same folder structure. Re-running never duplicates: an existing project is reused and
only what is missing is added.

## Steps

1. Get the folder path from the user (the folder that *contains* the projects, not one
   project). On the desktop the Projects page has "Import a folder…" with a picker; over
   MCP the path must be one the Atlas server can read.
2. **Preview first**: `import_projects_folder` with `dry_run=true`. Show the rows as a
   table — folder, name, whether it already exists, PDFs, notes, files, and any `skipped`
   reasons (too deep, too large, symlinks). Ask which folders to bring in; a folder that is
   not a project (e.g. `archive`, `misc`) is left out with `only`.
3. **Import one or a few folders per call**: `import_projects_folder` with `dry_run=false`
   and `only="Folder A,Folder B"`. Every PDF may fetch metadata from Crossref / OpenAlex, so
   a folder with many papers takes a while — report each result as it comes back
   (`documents`, `notes`, `references`, `needs_metadata`, `errors`) rather than waiting for
   all of them.
4. Afterwards, `get_project_overview` for each new project, and offer the next steps: a
   plan via `set_plan_outline` (with `dry_run` first), reading statuses through
   `set_reading_status`, and `take_snapshot` before any large clean-up.

## Options

- `pdfs="documents"` keeps PDFs as files in the project instead of library papers (for
  scans, forms, slides — anything that is not a paper).
- `markdown="documents"` keeps Markdown as files instead of notes (for a website or a
  README-heavy code project).

## Conventions

- Never import without showing the preview; never re-run with different options on a folder
  that already came in without saying what will be added.
- Junk is skipped on its own: hidden folders, .git, node_modules, virtual environments,
  build output, files over 50 MB, more than 2000 files in one project.
