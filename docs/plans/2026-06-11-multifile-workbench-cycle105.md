# Multi-file Manuscript Workbench — plan of record for cycle 105 ([REV])

Produced by the parallel planning workflow (owner rule, cycle 100) during cycle 103.
Execute nearly verbatim in cycle 105. Owner idea #24, parity slice 6.

## (a) Model + migrations + alias

- `validate_manuscript_path(path)` in writing/models.py: non-empty; ≤200 chars; ASCII-only;
  no backslash; no leading `/`; no drive letter; split on `/`: no empty segments, ≤8 deep,
  each segment matches `^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$` (segments can't start with `.` →
  kills `..`, `.`, dotfiles in one rule).
- `ManuscriptFile(TimeStampedModel)`: manuscript FK related_name="files"; path (validators);
  kind tex/bib/asset (auto from extension via `kind_for_path`; .tex/.sty/.cls/.bst→tex,
  .bib→bib, else asset); content TextField (text kinds); asset FileField
  upload_to=`manuscripts/{id}/assets/{name}`; is_main bool. Constraints: unique
  (manuscript, path); unique main per manuscript (condition=Q(is_main=True)).
- `Manuscript.main_file` property; `ensure_main_file()` (bootstrap main.tex from
  latex_source on editor GET); `source_text()` (main content if files else latex_source).
- **Alias (latex_source kept one release):** Manuscript.save override — after super().save,
  if update_fields is None or contains "latex_source": push to main file via queryset
  .update() (no recursion), or create main row (with `_from_alias_sync` guard) if source
  non-empty. ManuscriptFile.save — if is_main and not _from_alias_sync: queryset-.update()
  latex_source back. API PATCH latex_source → writes main file; editor file-save of main →
  writes column.
- **Mandatory companion:** every save in compile.py gets explicit update_fields (else a
  3-minute compile's final full save pushes a stale latex_source over mid-compile edits).
- Migrations: 0006 schema; 0007 data (seed main.tex rows for non-empty latex_source;
  reverse: copy back + delete rows). Admin: ManuscriptFileInline. Factory:
  ManuscriptFileFactory.

## (b) Endpoints

Classic (all scoped project→manuscript→files, X-SPA JSON):
- GET/POST `projects/<slug>/writing/<pk>/files/` (list / create empty text file)
- POST `files/upload/` (multipart; validate_upload_size 50MB; asset whitelist; text
  extensions decode into content)
- GET `files/<file_pk>/` (content or asset url)
- POST `files/<file_pk>/save/` (content; 400 for assets; cite-check for tex; returns
  {"saved": true, "cite": {...}} same shape as current autosave)
- POST `files/<file_pk>/rename/`, POST `files/<file_pk>/delete/` (main undeletable v1)
- latex_editor GET: ensure_main_file(); editor_config += filesUrl, fileUrlBase, files,
  mainFileId, activeFileId. Legacy latex_source POST branch STAYS (alias handles it).

DRF: ManuscriptFileSerializer (kind read-only; validate_path shared validator;
validate_asset cap+whitelist; update(): setting is_main=True demotes siblings in a
transaction; reject demoting current main; reject manuscript change).
ManuscriptFileViewSet(AtlasViewSet) parser_classes [MultiPart, Form, JSON],
project_filter="manuscript__project__slug", extra ?manuscript= filter; router
"manuscript-files". ManuscriptSerializer += read-only files summary.
ManuscriptViewSet.compile: emptiness check → source_text().

## (c) compile.py

- files = list(manuscript.files.all()); no files → legacy synthesize main.tex from
  latex_source; files but no main → FAILED "No main file is set".
- Tree writer: per file, dest=(work/f.path); `dest.resolve().is_relative_to(work.resolve())`
  or FAIL LOUDLY (last line of defense vs hostile rows); mkdir parents; assets write_bytes
  from f.asset, text write_text(f.content).
- Bib no-clobber: after tree write, only write generated references.bib if not
  (work/"references.bib").exists().
- Command: `[TECTONIC, "--untrusted", "--chatter", "minimal", main_path]`;
  pdf = (work/main_path).with_suffix(".pdf") — never hardcode main.pdf.
- Stale-drop guard unchanged; final save with explicit update_fields (see (a)).

## (d) Editor UI

Template: file sidebar (w-56) before editor column — Files header with "+ file" and
"upload" buttons + hidden multiple file input; inline new-file form; #file-tree ul
(JS-rendered); dropzone overlay copied from templates/documents/index.html.

JS (extend latex-editor.js IIFE in place — do NOT split files):
- State: files Map, docs Map (id→CodeMirror.Doc), dirty Set, timers Map, inflight Map,
  editGen Map, activeId; seed docs with main from textarea.
- saveFile(id): reads docs.get(id).getValue() (NEVER editor.getValue()); editGen counter
  decides whether to clear dirty; per-file 4s retry.
- change handler: dirty.add(activeId), bump editGen, debounce 2s → saveFile(activeId).
- openFile(id): asset → preview img, no swap. Else flush current (clearTimeout + saveFile
  if dirty, fire-and-forget safe), lazy-load doc via fetch, editor.swapDoc, renderTree,
  performLint.
- Lint filter: diagnostics where (d.file || "main.tex") === active file's path; problems
  panel shows ALL with file prefix; clicking cross-file row opens that file then jumps.
- triggerCompile: flush all dirty saves (Promise.all), then POST compile with EMPTY body
  (server tree is authoritative; stop sending latex_source).
- Tree CRUD + upload via FormData to files/upload/; drag-drop overlay pattern.

## (e) Build order (vertical slices within cycle 105)

1 model+alias+migrations+admin+factory (suite must stay green) → 2 compile rewrite →
3 classic endpoints → 4 DRF → 5 UI → 6 security battery + docs.

## (f) Tests (writing/tests/test_workbench.py + api additions) — 37 named tests

Validator: hostile paths parametrized (../x.tex, a/../b.tex, /etc/passwd, C:\evil.tex,
a\b.tex, .., .hidden, figs/, a//b, "", 201-char, 9-deep, RTL-override ‮, non-ASCII,
NUL) · sane paths · kind inference · constraints. Alias: migration seeds + skips empty ·
save syncs both ways · API PATCH latex_source writes main · status-only save doesn't
clobber · ensure_main_file idempotent. Compile: tree+--untrusted (mock run) · user bib
not clobbered · generated bib when none · legacy no-files · hostile row fails safely ·
renamed main finds pdf · files-but-no-main fails · real-tectonic multifile with \input +
1px PNG (skipif). Views: list/create json · bad path/duplicate 400 · save cite counts ·
rename · delete main forbidden · delete asset removes file · 50MB cap · .exe/.html
rejected · uploaded .tex lands as text · cross-project 404 · editor GET bootstraps ·
legacy autosave still writes main. API: CRUD + ?manuscript= · traversal rejected ·
set-main demotes · multipart upload · files summary · compile uses source_text ·
schema includes routes.

## (g) Sharp edges (read before building)

Autosave race across switches (docs-map reads + editGen); alias-vs-compile race
(update_fields mandatory); bib clobber guard is filesystem-based; generation guard now
reads file content in-task (fresher is fine, _stale still drops older); empty manuscripts
bootstrap lazily (migration skips them); API compile 400 via source_text; main rename ok
(pdf name follows), main delete forbidden; hostile rows must FAIL compile loudly not skip;
diagnostics must filter by active file or markers paint wrong buffers.
