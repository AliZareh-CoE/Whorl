---
name: atlas-writing
description: Drive a manuscript in Atlas from draft to submission — files, bibliography, cite check, compile, venue budget, reviewer responses and the submission timeline. Use when the user mentions a manuscript, paper draft, LaTeX, bibliography, a venue or deadline, reviews, or a resubmission.
---

# Atlas: writing

Manuscripts have LaTeX files, a bibliography drawn from the library, and a submission
timeline. The Atlas studio (the in-app editor) and these tools edit the same files.

**Toolsets.** Only the core tools are loaded by default; this playbook uses the writing and studio toolsets. If a tool named below is missing, call `enable_toolset` with "writing" then "studio" first (`list_toolsets` shows what is loaded).

## Orient

`list_manuscripts` (per project or everywhere) → `get_manuscript` for status, venue,
deadline, compile state and files → `get_manuscript_budget` for the venue limits.

## Edit source

- `list_manuscript_files`, `read_manuscript_file`, `write_manuscript_file` (whole-file
  writes; read first, change the smallest region, write back). `set_main_file` when the
  entry point moves.
- `manuscript_cite_check` after editing citations: it lists keys cited but missing from
  the bibliography and bibliography entries never cited. Fix with
  `add_manuscript_reference` / `remove_manuscript_reference`; the keys come from the
  library (`search`), never invented.
- `compile_and_wait` (or `compile_manuscript` + `get_compile_status`) and then
  `get_compile_diagnostics`; report errors with file and line, propose the fix, apply it
  only when asked. `latex_word_count` for length questions.

## Submit and respond

- `add_submission_event` for submitted / desk reject / reviews received / revision
  submitted / accepted / rejected / published, with the date.
- When reviews arrive: `log_reviews` with the pasted review text → Atlas creates a
  point-by-point response note; `get_response_progress` tracks answered points.
- `set_venue_limits` when the user names a venue's word, page, figure or reference caps.

## Conventions

- Never rewrite prose the user did not ask you to touch; LaTeX files are theirs.
- Keep `\cite{}` keys exactly as the bibliography spells them.
- Say what you compiled and whether it produced a PDF; do not claim success on warnings.
