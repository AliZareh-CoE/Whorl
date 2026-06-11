# Overleaf-redesign UI parity for the LaTeX editor (Owner idea #26) — plan of record

Parallel planning agent (cycle 118→119). Match Overleaf's redesigned editor *structure*
(not its exact look — Atlas stays calm/editorial/near-white), then go beyond.

## Gap matrix (Overleaf-redesign element → Atlas status → sketch)
- Top menu bar (File/Edit/View/Help) → MISSING; buttons scattered in title row → consolidate into Alpine dropdowns (M)
- Left vertical icon rail (files/search/review/settings) → MISSING; file tree is always-open w-48 → ~44px rail switching one drawer (L)
- Collapsible panels via divider drag-handles → MISSING; fixed widths, only hide/show → flex + draggable dividers writing px to localStorage; call editor.refresh()+pdf re-render on resize (L)
- Layout menu (split/editor-only/PDF-only/PDF-in-tab) → PARTIAL (binary Preview toggle) → Layout dropdown, CSS classes on the flex row (M)
- Review/track-changes mode → PARTIAL (line comments exist) → UI shell M; true tracked changes needs a backend change model = later epic (L+)
- Top-right History/Share cluster → PARTIAL (History in left sidebar) → move History trigger top-right (reuse revision modal) + Share (M)
- Error-log pane next to Recompile → PARTIAL (diagnostics at page bottom) → relocate beside/under a renamed "Recompile" at top of PDF pane (S) — HIGHEST value/effort
- Overall visual polish → PARTIAL (calm look strong; chrome button/glyph-heavy) → inline-SVG icon set, 8px rhythm, unify accent (M)

## Sequenced UI/UX cycles (each shippable+tested)
1. Error-log pane relocation + compile bar to top of PDF pane (CSS/template, tiny JS move) — reads as "Overleaf" instantly
2. Top toolbar consolidating scattered buttons into File/Edit/Insert/View menus (KEEP element IDs so latex-editor.js is untouched)
3. Top-right History/Share/Layout cluster (layout modes = CSS classes, localStorage atlas-editor-layout)
4. Collapsible panels with divider drag-handles (the real work; MUST editor.refresh()+pdf re-render on resize-end, debounced)
5. Left vertical icon rail (Files/Outline/Research/History/Comments/Settings; one drawer at a time)
6. Visual polish: inline-SVG icon set replacing Ω/⚙/⇄ glyphs, spacing rhythm, single accent
7. (later epic) Review/track-changes mode — UI shell first, then a change model
MVP parity order: 1→2→3→4 reads as the redesign. Then 5,6. Then 7.

## Beyond-Overleaf interface ideas (fit Atlas's data)
- Research rail as a first-class pane peer to Files (the bib/notes/hypotheses panel)
- Hypothesis-aware margin cues (gutter status dot when a para references a hypothesis)
- The pet as an ambient compile/writing companion in the editor chrome
- MCP "explain this error / find a citation" in the error-log pane (route to the project's OWN library, beats a generic AI assistant)
- Layout presets named by research TASK: Drafting / Reviewing / Submitting (not geometry)
- Outline↔PDF↔hypotheses tri-sync

## Risks
- CM5 needs editor.refresh() after ANY container resize; viewportMargin:Infinity renders whole doc → throttle resize redraws; pdf.js canvas must re-render on width change too.
- No Node build beyond Vite; CDN CM5+Alpine+vanilla JS; hand-roll drag-resize (small), no splitter lib, no CM6, no React island for the editor.
- Calm not cluttered: match STRUCTURE not chrome weight — thin rail, text-light menus, monochrome SVG icons, single accent, near-white.
- Preserve Owner idea #25 full-width density (main_class=max-w-none); rail eats ~44px, keep editor max width in editor-only mode; pane min-widths so the editor never collapses.
- Modal/state coupling: History/comments bind by hard-coded getElementById; relocate DOM but KEEP IDs → JS untouched, cycles stay small/testable. Namespace new localStorage keys; absent = current default.

Critical files: templates/writing/latex_editor.html, static/js/latex-editor.js, templates/base.html, templates/core/pet.html
