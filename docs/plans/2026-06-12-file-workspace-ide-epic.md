# File-workspace / IDE epic — projects open like a workspace (Owner idea #30) — plan of record

Parallel planner, cycle 147→. Executes in slices like the LaTeX epic (#24). **Four OWNER
DECISIONS (2026-06-12) override the open questions in idea #30 and make this plan
load-bearing on all of them:**

1. **UNIFY INTO ONE TREE.** Documents AND manuscript/LaTeX sources become ONE per-project
   file tree — "all the files and folders I have," literally. One `ProjectFile`/`Folder`
   hierarchy holds general documents AND compile-aware manuscript sources; manuscript-ness
   is a **role/attribute on a node**, not a separate table. Migration is a dedicated early
   slice, reversible, tested. Preserve compile, `validate_manuscript_path`, revisions, and
   the API + MCP contracts (migrate, don't break).
2. **FULL DESKTOP COMMITMENT NOW.** A desktop app is a first-class target from the start.
   **Tauri** (Rust shell, tiny binary, no Node-bloat — fits §2's "no Node project beyond
   Vite" constraint) wraps the **same Django+SPA**. Real local-filesystem access, OS file
   associations, app window/menu, packaging. A working Tauri shell ships **early-mid** (right
   after the explorer-tree slice) and matures across the epic; the web app stays fully
   functional in parallel. New disk access shifts the threat model — sandboxing is per-slice.
3. **BUILT-IN TERMINAL.** *"because I would like to have terminal in it as well!"* — this
   REVERSES the earlier "no integrated terminal in v1" exclusion. An integrated terminal is
   part of the IDE story, shipped as its own slice **right after the Tauri shell exists**
   (Slice 5 below). Least-effort, proven-OSS route: **xterm.js** (MIT — the emulator VS Code
   itself uses) for the UI + a **real PTY in the Rust shell** (`portable-pty`, MIT — used by
   WezTerm) talking over **Tauri IPC events**. This needs NO Django websockets and keeps the
   web app untouched; desktop-IPC only (see the security note in Slice 5 and §D).
4. **OSS-FIRST, LEAST EFFORT (standing Owner #28, re-emphasized).** *"try your best to use
   open source projects so we can seriously get this done with the least effort"* — EVERY
   slice names its specific open-source building block instead of hand-rolling; we write
   thin glue only. Licenses **MIT/BSD/ISC/Apache only**, pinned, **bundled locally (no
   CDN)**. The Build-vs-adopt table in §0bis is normative; each adoption gets a
   DECISIONS.md entry on landing.

---

## 0. Where the code is today (verified, not sketched)

- **`documents/`** — `Folder(project, parent→self, name)` recursive tree (`path` prop,
  `descendant_ids()` cycle-safe), `Tag(project,name,color)`, `Document(project, folder→null=root,
  file=FileField upload_to=`projects/{slug}/documents/{filename}`, title, description, tags M2M,
  file_size, content_type)`. Explorer is server-rendered (`templates/documents/index.html`,
  `_folder_nodes.html`) + a `documents-table` React island + a `Documents.tsx` SPA page.
  Ops: upload, bulk-upload, rename, **move** (`document_move`), bulk-action, download, folder CRUD.
- **`writing/`** — `Manuscript(project, …, latex_source col)`, `ManuscriptFile(manuscript,
  path[validate_manuscript_path], kind tex/bib/asset[kind_for_path], content, asset FileField
  upload_to=`manuscripts/{id}/assets/{name}`, is_main)` with unique `(manuscript,path)` +
  one-main constraints. **Bidirectional alias** latex_source↔main-file (Manuscript.save /
  ManuscriptFile.save, `_from_alias_sync` guard, mandatory `update_fields`). `ensure_main_file()`,
  `source_text()`. `ManuscriptRevision(files=JSON {path:content})` + `snapshot_manuscript()`
  (auto on compile, keep labeled + last 50). `compile.py`: `_write_tree()` writes the tree to a
  tempdir with a `resolve().is_relative_to()` traversal guard, runs vendored
  `bin/tectonic --untrusted`, bib no-clobber, stale-generation drop.
- **API** (`/api/v1/`, X-API-Key + session): registered `folders`, `tags`, `documents`,
  `manuscript-files` (basename `manuscript-files`, `?manuscript=`), `manuscripts`
  (`compile`/`compile-status`/`word-count` actions). `AtlasViewSet.project_filter` gives
  `?project=<slug>` on every resource.
- **MCP** (`mcp_server/`, pure httpx over the API): `list_documents`, `search`,
  `list_manuscript_files`, `read_manuscript_file`, `write_manuscript_file` (create-or-update by
  path), `set_main_file`, `compile_manuscript`, etc. AST test forbids Django/SDK imports in
  `client.py`.
- **Frontend** — Vite islands + a React-Router/TanStack-Query SPA at `/` (`spa_shell`, catch-all),
  CM6 editor island (`codemirror-lang-latex`, vim, lint, autocomplete — already bundled),
  pdf.js reader (`templates/literature/read.html`), `split.js`. Manuscript starter gallery is
  **code-defined** (`writing/templates_gallery.py`, no DB) — the model for project templates.

**Implication:** the unified tree is mostly a **merge of two existing trees**, reusing the
document `Folder` as the survivor and folding `ManuscriptFile` semantics onto file nodes. The
editor, compile, pdf.js, and CM6 are all already in hand — this epic is plumbing + UX, not new
core tech. The hard part is the migration's correctness and not breaking 2 live contracts.

---

## 0bis. Build vs adopt (Owner #28 — normative; thin glue only)

| Capability | Adopt (OSS project) | License | What we write ourselves |
|---|---|---|---|
| Code/text editing | CodeMirror 6 (already bundled in `frontend/`) | MIT | language wiring + autosave glue |
| Per-file language modes | `@codemirror/language-data` (lazy-loads modes on open) | MIT | extension→mode map only |
| Explorer tree | **react-arborist** (virtualized, drag-drop, inline rename, multi-select, keyboard/aria) | MIT | a data adapter over the `tree/` endpoint |
| PDF preview | `pdfjs-dist` — **moved off the CDN into the Vite bundle** (literature reader + editor preview relinked to the same local copy) | Apache-2.0 | viewer mount glue (exists; relink) |
| CSV/TSV preview | **papaparse** | MIT | a `<table>` renderer over parsed rows |
| Markdown preview | existing server pipeline (`markdown` + `nh3`) | BSD-3 / MIT | nothing new |
| Image preview | `<img>` (browser-native) | — | nothing |
| File-type icons | **lucide** static stroke SVGs, tree-shaken imports (matches the editor's stroke-SVG icon language; feeds Backlog #148) | ISC | extension→icon map |
| Resizable panes | split.js (already bundled) | MIT | none |
| Desktop shell | **Tauri 2** + official plugins **`fs`, `dialog`, `shell`** | MIT/Apache-2.0 | thin `desktop/` crate + config + menu wiring |
| Terminal UI | **xterm.js** (`@xterm/xterm`) + **`@xterm/addon-fit`**, bundled locally like CM6 | MIT | mount + resize + panel chrome |
| PTY | **`portable-pty`** crate (MIT, WezTerm's) in the Rust shell; first evaluate an existing community **tauri-pty / tauri-plugin-pty** and use it only if actively maintained | MIT | ~100 lines: spawn shell, pump bytes over IPC events, resize, kill |
| Project templates | none needed | — | data + glue: declarative definitions + scaffold service (cookiecutter would be overkill) |

Rules: every dependency **pinned** (`frontend/package.json` / `desktop/src-tauri/Cargo.toml`),
license MIT/BSD/ISC/Apache only, **zero CDN tags** — this epic also retires the last pdf.js
CDN usage, finishing what the CM6 migration (#114) started. `npm audit` + `cargo audit` join
the audit-cycle checklist.

**Explorer: adopt react-arborist (evaluated vs growing our hand-rolled trees).** We currently
have three hand-rolled trees (`templates/documents/_folder_nodes.html` HTMX, the manuscript
file sidebar in `latex-editor.js`, and the SPA `Documents.tsx` list). The Workspace explorer
needs virtualization (data/ folders get big), drag-drop move, inline rename, multi-select, and
full keyboard/aria nav — react-arborist ships all five out of the box, is MIT, actively
maintained, React-18 compatible, and we already ship React in the islands build; hand-rolling
that feature set is weeks of pointer math and a11y debt for zero product value. **Recommendation:
adopt react-arborist for `Workspace.tsx`**; the existing hand-rolled trees are not migrated in
this epic (they get *retired* by Slice 8's unification, which is cheaper than porting them).

---

## A. UNIFIED DATA MODEL (the load-bearing decision)

### Chosen shape: ONE tree, manuscript = a view over nodes

- **Survivor folder:** keep `documents.Folder` (recursive, project-scoped, cycle-safe). Add
  nothing structural; it becomes THE project folder tree.
- **`ProjectFile`** = grow `documents.Document` into the single file node (rename in code to
  `ProjectFile`; keep `documents.Document` as a thin alias/`proxy=` for one release so imports
  don't break, mirroring the latex_source pattern). Fields added to the node:
  - `content = TextField(blank=True)` — inline text for editable files (tex/bib/md/code/csv…);
    `file = FileField` stays for binary/large assets. Exactly one is authoritative per node:
    `is_text` derived from extension (`kind_for_path` generalized, see below). Text nodes store
    in `content`; binary nodes store in `file`. (Migration backfills.)
  - `rel_path = CharField` — the node's path **relative to project root**, derived from
    folder chain + name, stored denormalized for fast tree writes/compile and uniqueness.
    Maintained on save/move (reuse `Folder.path` logic). Unique `(project, rel_path)`.
  - `role = CharField(choices: GENERAL/MANUSCRIPT_SOURCE, default GENERAL)` — manuscript-ness
    is an attribute, not a table. A node with role=MANUSCRIPT_SOURCE belongs to a manuscript's
    compile set.
  - `kind = CharField(tex/bib/asset/other)` — generalize `kind_for_path` into
    `documents.paths.kind_for_path` (tex/sty/cls/bst→tex, bib→bib, known-binary→asset,
    text-ish→other-text). The strict `validate_manuscript_path` moves to
    `documents/paths.py` and applies to **rel_path of any node inside a manuscript scope**
    (general docs keep the looser existing filename rules; manuscript-source nodes are strict).
- **Manuscript → tree linkage:** Manuscript gains `root_folder = FK(Folder, null)` (the folder
  whose subtree is the manuscript's source, e.g. `manuscript/paper/`) and `main_file = FK(
  ProjectFile, null)`. The compile set = `ProjectFile`s under `root_folder`'s subtree with
  role=MANUSCRIPT_SOURCE. `is_main` collapses into `Manuscript.main_file` (one-main invariant
  becomes a single FK, simpler than the partial-unique constraint). `Manuscript.source_text()`,
  `ensure_main_file()`, `main_file` property all re-expressed over the FK + tree.
- **What dies:** the separate `ManuscriptFile` table and `manuscript_asset_path` storage. Its
  rows migrate into `ProjectFile` nodes under each manuscript's `root_folder`.
- **What stays byte-identical:** `validate_manuscript_path` rules (8 deep, ASCII, segment regex,
  no traversal — moved file, same function + tests), `ManuscriptRevision`/`snapshot_manuscript`
  (still `{rel_path: content}` over the manuscript's text nodes), compile's
  `_write_tree` traversal guard (now iterates `ProjectFile`s, same resolve() check), the
  latex_source alias (now: latex_source ↔ `manuscript.main_file.content`).

### Migration — its own slice, reversible, heavily tested (Slice 1)

- **Migration 00xx (schema):** add `ProjectFile.content/rel_path/role/kind`, `Manuscript.
  root_folder/main_file`; create indexes/uniques. No data yet.
- **Migration 00xx+1 (data, reversible):**
  - **Forward:** (a) backfill `rel_path`+`kind`+`is_text` for every existing `Document`; text
    files with a real `file` get their bytes decoded into `content` only if a known text
    extension (else stay binary). (b) For each `Manuscript`: ensure a `root_folder` (create
    `manuscript/<slug-or-id>/` under project root if absent); for each `ManuscriptFile`, create
    a `ProjectFile` at `root_folder + path` with role=MANUSCRIPT_SOURCE, copying content
    (text) or the asset file (binary) and kind; set `Manuscript.main_file` from the old
    `is_main` row. (c) Drop nothing yet — keep `ManuscriptFile` rows for one release as a
    read-only shadow (like latex_source) so a rollback is data-lossless.
  - **Reverse:** delete the created MANUSCRIPT_SOURCE `ProjectFile`s, null `main_file/
    root_folder`, re-decode `content`→`file` is **not** attempted (text stays in content; the
    shadow `ManuscriptFile` rows are the rollback source of truth). Documented as
    "reverse restores the pre-merge manuscript table; general-doc content-inlining is
    forward-only and harmless."
  - **Idempotent + guarded:** re-runnable; skips manuscripts already linked; logs counts.
- **Contract bridge (kept one release, like the latex_source alias):**
  - `manuscript-files` API + the 6 MCP file tools keep working by re-pointing their
    serializer/viewset at `ProjectFile` filtered to the manuscript's subtree+role. Same JSON
    shape (id, path, kind, content, is_main): `path` = rel_path minus the root_folder prefix;
    `is_main` = (node == manuscript.main_file); create-or-update-by-path lands a node in the
    subtree. **No MCP client change** (the AST/Django-free constraint holds).
  - A **contract test** module asserts every documented `manuscript-files` request/response and
    every MCP file tool returns byte-identical shapes pre/post migration (snapshot fixtures).
- **Tests (Slice 1):** migration forward creates correct nodes + main_file (per-manuscript);
  reverse restores; idempotent re-run; hostile/odd old paths survive (`figs/a.png`, deep
  nesting, the main file); latex_source alias still round-trips through the new main_file FK;
  `manuscript-files` CRUD + `?manuscript=` unchanged; all 6 MCP file tools unchanged (replayed
  against the test server); compile still finds main + writes the tree; revisions snapshot the
  same `{path:content}`. **Suite stays green is the gate.**

---

## B. SLICE SEQUENCE (vertical, each shippable + tested, like #24)

> Re-sequenced so the **unified model+migration is Slice 1**, a **working Tauri shell is
> Slice 4** (right after the explorer tree), and the **built-in terminal is Slice 5 —
> immediately after the shell exists** (owner directive #3). Web app fully functional at
> every slice. Every slice names its OSS building block (owner directive #4).

**Slice 1 — Unified model + migration + contract bridge** (§A). The whole epic's foundation.
Reversible data migration; `manuscript-files` API + MCP file tools re-pointed, contract tests
prove byte-identity; compile/revisions/alias preserved. **OSS:** none new — Django migration +
model glue (the validator and `kind_for_path` move, they aren't rewritten). *Gate: full suite
green, contract tests green, a real manuscript still compiles end-to-end.*

**Slice 2 — Explorer tree (read + open-anything preview).** One project **Workspace** page
(SPA `Workspace.tsx` + classic fallback): the full `Folder`/`ProjectFile` tree in a left pane
(keyboard nav: ↑↓ move, →/← expand/collapse, Enter open — free from arborist), a content pane
that **opens ANY file type in-app** reusing what's already bundled:
- text/code/tex/bib/md → CM6 editor island (read+edit; tex/bib in a manuscript subtree get the
  full LaTeX affordances already built; other languages via lazy `@codemirror/language-data`),
- PDF → the existing pdf.js reader, **relinked to a locally bundled `pdfjs-dist`** (the last
  CDN tag dies here),
- images → `<img>`, CSV/TSV → **papaparse** parse + a plain `<table>` (first 500 rows, row/col
  counts), markdown → the existing sanitized server render,
- unknown → download + metadata card.
**OSS:** **react-arborist** (tree, per §0bis recommendation), `@codemirror/language-data`,
`pdfjs-dist` (bundled), **papaparse**, **lucide** stroke SVGs for file-type icons (one
`iconFor(ext)` map). All pinned, bundled, no CDN.
`GET /api/v1/projects/{slug}/tree/` returns `{nodes:[{id,name,rel_path,kind,role,is_text,
folder_id,size}], folders:[{id,name,parent_id}]}` (one fetch, drives both shells). Empty-state
explains the workspace + offers "new file / upload / apply template." *Gate: open a tex, a PDF,
an image, a CSV from one tree; keyboard nav; both shells; `grep` finds zero CDN script tags.*

**Slice 3 — Explorer write ops (IDE affordances).** Inline create-file/create-folder,
rename, **move (drag-drop + cut/paste)**, delete, duplicate, multi-select; upload (single +
drag-drop, reuse `bulk_upload`); reuses existing `document_move`/folder-CRUD endpoints,
generalized to `ProjectFile`. Save-on-edit for text nodes (debounced autosave, the editor's
existing pattern). rel_path + uniqueness maintained on every move/rename (cycle guard via
`descendant_ids()`). Per-slice security: every op re-checks project scope + the strict path
validator for manuscript-subtree nodes. **OSS:** react-arborist's built-in drag-drop, inline
rename, and multi-select — the server stays authoritative; we write only the op→endpoint
adapter. *Gate: create/rename/move/delete across folders; move a tex within a manuscript
subtree keeps it compilable; drag-drop upload.*

**Slice 4 — Tauri shell v1 (the desktop app ships).** `desktop/` Tauri project (Rust shell,
`tauri.conf.json`), thin wrapper that loads the **same Django+SPA**:
- **Bundled mode:** the desktop binary launches a local Django (or points at a configured
  local server) and the Tauri webview loads it; native app window + menu (File/Edit/View/Help
  mapped to existing SPA actions), single-instance, deep-link `atlas://`.
- **Build/packaging:** `make desktop` / `cargo tauri build` → tiny per-OS binary; CI job builds
  the shell (no Node project beyond the existing Vite — Tauri uses the prebuilt `static/`).
- **Security shift (FLAGGED, first appearance):** the desktop changes the threat model from the
  single-login web app. v1 keeps the **same API-key + session auth**, binds Django to
  **localhost only**, and the webview is allowlisted to the local origin (Tauri CSP +
  `dangerousRemoteDomainIpcAccess` off). No raw disk access yet (that's Slice 7). DECISIONS
  entry: reachable surface = the local app only; key still required.
**OSS:** **Tauri 2** + official plugins **`shell`** (open external links) and **`dialog`**
(native dialogs from Slice 7); we write only the thin crate, config, and menu wiring.
*Gate: `cargo tauri build` produces a launchable binary on Linux that shows the full workspace;
web app unchanged.*

**Slice 5 — Built-in terminal (xterm.js + portable-pty) — lands immediately after the shell
exists** (owner directive #3 — *"I would like to have terminal in it as well!"*).
- **UI:** a bottom panel in the Workspace (split.js divider, like the editor's panes), rendered
  **only when `window.__TAURI__` is present** — the web build ships no terminal UI.
  **`@xterm/xterm` + `@xterm/addon-fit`**, pinned and bundled locally exactly like CM6 — no
  CDN. **One terminal in v1; multiple tabs/splits later** (parked, §E).
- **PTY lives in the Rust shell, not Django.** First evaluate an existing community
  **tauri-pty / tauri-plugin-pty** and adopt it only if actively maintained; otherwise write
  the thin glue ourselves on **`portable-pty`** (MIT, WezTerm's crate — also abstracts ConPTY
  on Windows): spawn `$SHELL` (PowerShell on Windows), pump bytes both ways over Tauri IPC
  events (`term://data` / `term://input` / `term://resize` keyed by session id), resize on
  fit-addon callbacks, kill the child on panel close/window close. ~100 lines either way.
- **cwd = the project directory:** the terminal opens in the current project's local folder —
  default the project's documents directory under `MEDIA_ROOT` (the server is local in the
  desktop case by definition); a per-project local-path override lives in the Tauri store
  (shell-side), never in Django.
- **Architecture honesty:** this route needs **NO Django websockets** and keeps the web app
  untouched — the least-effort path. A **web-browser fallback** (Django Channels / websocket
  PTY) is recorded as a later, **separate** decision: CLAUDE.md non-goals exclude websockets,
  and nothing in this epic depends on it.
- **Security (FLAGGED):** a terminal is **arbitrary code execution by design**. That is
  acceptable in the local, single-user desktop context — the same trust model as VS Code's
  integrated terminal — because the PTY speaks only over Tauri IPC inside the user's own
  session. It must **NEVER** be exposed through the web API/server: no Django view, no DRF
  route, no MCP tool may reach a PTY — **desktop-IPC only**. A grep-guard test (the
  `test_glue_escapes.py` pattern) fails the build if any pty/terminal endpoint ever appears
  in `api/`, `config/urls.py`, or `mcp_server/`; audit cycles re-check it.
**OSS:** xterm.js + fit addon (MIT), portable-pty (MIT) or a maintained tauri-pty plugin; we
write mount/resize/panel chrome + the IPC pump only.
*Gate: in the desktop build, open the terminal in a project, run `ls` and see the project's
files; resize reflows; web build contains no terminal assets; the no-web-PTY guard test passes.*

**Slice 6 — Project templates that scaffold organized folders.** Generalize the manuscript
gallery (`templates_gallery.py`, code-defined, versioned-with-code, `#128`-paired and later
user-extensible) into **project templates**: a template = a declarative folder/file tree
(e.g. `literature/`, `data/`, `analysis/`, `manuscript/main.tex` (role=MANUSCRIPT_SOURCE, set
as main), `protocols/`, `notes/README.md`). New-project flow + a "Apply template" action on an
existing project scaffold the tree (idempotent, never clobbers existing nodes). Definitions live
in `core/project_templates.py`; `GET /api/v1/project-templates/` lists them; `POST …/apply`.
seed_demo uses one. **OSS:** none needed — declarative data + a scaffold service is trivial
glue (cookiecutter evaluated and rejected: Jinja templating + a new dep for what is a dict→
nodes loop). *Gate: new project from a template shows the prebuilt organized tree; the
scaffolded `manuscript/main.tex` compiles.*

**Slice 7 — Tauri local-filesystem access ("contain/open any file from disk").** The owner's
"contain any file" ask: from the desktop app, open/import files **from the real filesystem**
(not only MEDIA_ROOT uploads) and reveal/open workspace files in the OS:
- Tauri `dialog` + `fs` (scoped) for "Open from disk → import into workspace" and "Reveal in
  Finder/Explorer"; optional "link in place" (store an absolute path on a `ProjectFile` with
  `storage=LINK`, read through Tauri's scoped fs) vs "copy into MEDIA_ROOT" (default, safe).
- **OS file associations:** register `.atlas`/project-open and (optional) open-`.tex`-with-Atlas
  via `tauri.conf.json` `fileAssociations`.
- **Security (the big one, FLAGGED):** disk access is the real threat-model change. Tauri `fs`
  **scope allowlist** = only user-chosen directories (no `$HOME/**` blanket); path **sandbox**:
  every imported/linked path is canonicalized and checked against the granted scope (reuse the
  `resolve().is_relative_to()` discipline from compile.py); linked-in-place reads never escape
  the granted roots; the webview still can't reach arbitrary disk (only the Rust side via
  explicit commands). API key + localhost binding still hold. DECISIONS entry enumerates
  reachable directories + the canonicalization guard. Tests: a Rust/integration test that a
  path outside scope is refused; a Django test that a LINK node outside its granted root 403s.
**OSS:** Tauri official plugins **`fs`** (scoped) + **`dialog`** — no hand-rolled native
dialogs or file IO; we write the scope checks and the import/link commands only.
*Gate: from the desktop app, open a PDF from disk into a project, reveal a file in the OS file
manager, and a link-in-place node renders — with an out-of-scope path refused.*

**Slice 8 — IDE polish + unify the old surfaces.** Command palette over files (the existing
`CommandBar` gains file-open), breadcrumb path bar, recent files, split view (existing
`split.js`), "open in editor" everywhere, find-in-file (CM6 search) + project-wide search
folded into the existing global search. Retire the standalone Documents page and the separate
manuscript file-sidebar in favor of the unified Workspace (redirects kept). Drop the
`ManuscriptFile` shadow table + the `Document` proxy alias (the "one release later" cleanup),
once contract tests have ridden a release. **OSS:** all already in hand (CM6 search, split.js,
lucide); evaluate porting the retired trees' last consumers onto react-arborist here rather
than maintaining two tree implementations. *Gate: Documents/manuscript-files redirect to
Workspace; shadow table dropped; all file tools/endpoints green on the unified model.*

**Slice 9 — Tauri maturation + release (incl. terminal polish: multiple tabs if cheap, else
parked).** Auto-update channel, code-signing notes (per-OS),
app icon/menu polish, offline-first behavior (the CM6/editor already works offline since #114),
crash/log surface, packaged installers in CI artifacts. **OSS:** Tauri's built-in updater +
bundler — nothing hand-rolled. *Gate: signed/notarized build notes documented; installer
artifact in CI; smoke battery passes inside the desktop webview (incl. the terminal).*

---

## C. Per-slice standing constraints (every slice, per loop rules)

- **Security:** project-scope re-checked on every file op; strict `validate_manuscript_path`
  for manuscript-subtree nodes; compile keeps its `resolve()` last-line guard; from Slice 4
  the desktop binds localhost + keeps API-key auth; from Slice 5 the PTY is desktop-IPC only
  (no-web-PTY grep-guard); from Slice 7 disk scope is allowlisted + canonicalized. Each slice
  adds its hostile-path / out-of-scope test.
- **OSS-first (owner directive #4):** before any non-trivial hand-roll inside a slice, check
  §0bis; deviations (a new adoption or a deliberate build) get a DECISIONS.md entry with the
  alternative considered. All deps pinned, MIT/BSD/ISC/Apache, bundled locally — no CDN.
- **Tests:** every new service/selector + computed property unit-tested; every page a logged-in
  smoke test; migration + contract tests in Slice 1; a desktop integration smoke from Slice 4.
- **Both shells stay functional:** the SPA Workspace and a classic fallback; same `tree/` API.
- **Efficiency:** one `tree/` fetch drives the explorer; rel_path denormalized for O(1) compile
  tree writes; revisions unchanged budget.

---

## D. Risks (read before building)

- **Migration correctness is the whole ballgame.** Two live contracts (`manuscript-files` API +
  6 MCP file tools) must not break. Mitigation: keep `ManuscriptFile` as a read-only shadow one
  release; contract tests assert byte-identical shapes pre/post; reverse migration restores the
  table; idempotent + counted. Don't drop the shadow until Slice 8 after a release.
- **rel_path drift.** Moves/renames must recompute `rel_path` for a whole subtree atomically and
  keep `(project, rel_path)` unique; a missed update silently breaks compile. Mitigation:
  recompute via the folder chain in one transaction, reuse `descendant_ids()` cycle guard, test
  deep moves.
- **Two path-strictness regimes in one tree.** General docs allow loose filenames; manuscript
  sources are ASCII/8-deep/segment-regex strict. Mitigation: strictness keys off `role`/subtree,
  not the whole tree; a general doc moved INTO a manuscript subtree is re-validated (reject or
  sanitize, decided + tested).
- **Tauri ≠ Node-bloat, but it IS a new toolchain (Rust).** Mitigation: the shell is thin
  (loads the existing SPA, no React rewrite); Rust touches only window/menu/fs commands; CI adds
  one Tauri build job; §2's "no Node project beyond Vite" is honored (Tauri consumes prebuilt
  `static/`).
- **Desktop threat-model shift (Slice 7).** Real disk access is the genuinely new risk surface.
  Mitigation (above): scoped fs allowlist, canonicalized path sandbox, webview can't touch disk
  directly, localhost binding, API key retained, explicit Rust commands only, out-of-scope
  refusal tests. Default to copy-into-MEDIA_ROOT; link-in-place is opt-in.
- **The terminal is arbitrary code execution by design (Slice 5).** Acceptable in the local
  single-user desktop context — the VS Code trust model — but ONLY because it never leaves
  Tauri IPC. The catastrophic failure mode is a future "convenience" that bridges the PTY
  through Django (an endpoint, a websocket, an MCP tool): a remote-shell-as-a-feature.
  Mitigation: the no-web-PTY grep-guard test fails the build on any pty/terminal route in
  `api/`, `config/urls.py`, or `mcp_server/`; the web bundle ships no xterm assets; every
  audit cycle re-verifies; the web-terminal fallback stays a separate, owner-gated decision.
- **tauri-pty plugin maintenance.** A community plugin may be stale. Mitigation: decide at
  Slice 5 start; the fallback (portable-pty + ~100 lines of our own IPC glue) is small,
  fully under our control, and portable-pty itself is battle-tested (WezTerm) incl. ConPTY
  on Windows.
- **New frontend deps must not bloat first paint.** react-arborist/papaparse/xterm land only
  in the Workspace island chunk (code-split like vim-keymap, #137); pdfjs-dist is already
  paid for today via CDN — bundling moves it, not adds it. Mitigation: track gz sizes in the
  slice gates.
- **Text-vs-binary authority on one node.** `content` xor `file` must be unambiguous.
  Mitigation: `is_text` derived from extension at save, exactly one populated, migration
  backfills, a model check + test enforces it.
- **CM6/pdf.js reuse, not rebuild.** Preview must reuse the bundled editor + reader, not add a
  competing viewer lib. Mitigation: Slice 2 wires the existing islands; the only new frontend
  deps are the §0bis adoptions (react-arborist, papaparse, lucide, language-data, xterm) —
  anything beyond that list needs a DECISIONS entry first.
- **Manuscript "view over tree" vs the old `Manuscript.files` related set.** Code that did
  `manuscript.files.all()` (compile, snapshot, serializer) must move to the subtree query.
  Mitigation: one `manuscript.source_files()` selector is the single chokepoint; everything
  routes through it; grep-guard test that nothing else queries the dropped relation.

---

## E. What we do NOT build in v1 (parked → Backlog)

> Updated for owner directive #3: ~~integrated terminal~~ **moves IN** (Slice 5, desktop-only).
> Still out: git client UI, collaborative editing, remote workspaces.

- Real-time multi-cursor / collaborative editing in the workspace (§1 non-goal) — still out.
- A full general-purpose code IDE (LSP, language servers, debuggers) — CM6 syntax + the
  edit/compile loop + **the integrated terminal (now IN, Slice 5)**; no per-language tooling
  beyond LaTeX.
- **Web-browser terminal** (Django Channels / websocket PTY) — a later, SEPARATE decision:
  CLAUDE.md non-goals exclude websockets, the desktop terminal needs none, and exposing a PTY
  over HTTP changes the security story entirely (owner-gated if ever raised).
- **Multiple terminal tabs / split terminals** — Slice 5 ships one; tabs land in Slice 9 only
  if cheap, else parked here.
- Git client UI (stage/commit/diff panes) / version control of the workspace beyond the
  existing `ManuscriptRevision` snapshots (GitHub commit↔experiment linking already parked in
  §5 Backlog) — still out; the terminal gives CLI git for free.
- Remote workspaces / remote file systems (SSH/containers, VS Code-style) — still out.
- User-authored project templates UI (definitions stay code-defined in v1; user-extensible is
  noted, deferred — pairs with #128).
- Mobile/native iOS-Android apps (Tauri targets desktop; responsive web covers mobile, §1).
- Tauri **mobile** targets, plugin marketplace, multi-window MDI.
- Cloud sync / multi-device file sync (single-user, single login — §1).
- In-browser PDF highlight-to-note, lit-review matrix, embedding-based suggestions (already in
  the §5 Backlog; unchanged by this epic).
- Arbitrary whole-disk browsing in the desktop app (only user-granted scoped directories).

---

## F. Critical files

`documents/models.py` (Folder, Document→ProjectFile), `documents/paths.py` (new — moved
validator + generalized kind_for_path), `documents/views.py` + `documents/urls.py`,
`writing/models.py` (Manuscript root_folder/main_file; drop ManuscriptFile), `writing/compile.py`
(source_files() chokepoint, same traversal guard), `writing/templates_gallery.py` →
`core/project_templates.py`, `api/views.py` + `api/serializers.py` + `api/urls.py`
(manuscript-files bridge over ProjectFile, new `tree/` + `project-templates/` endpoints),
`mcp_server/server.py` + `client.py` (unchanged shapes — contract held),
`frontend/src/app/pages/Workspace.tsx` (new; react-arborist tree + viewer pane + terminal
panel) + `Documents.tsx` (retire), `frontend/vite.config.ts` (workspace chunk + local
pdfjs-dist worker), `frontend/package.json` (pinned: react-arborist, papaparse, lucide,
@codemirror/language-data, @xterm/xterm, @xterm/addon-fit), the CM6 editor island + pdf.js
reader (reused), a new `desktop/` Tauri project (`tauri.conf.json`, Rust `src-tauri/` with
`pty.rs` on portable-pty, `make desktop`), and the no-web-PTY grep-guard test (e.g.
`api/tests/test_no_pty_surface.py`).
