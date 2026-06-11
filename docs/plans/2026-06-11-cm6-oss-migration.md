# CodeMirror 6 migration + OSS-vs-hand-rolled (Owner idea #28, Backlog #134) — plan of record

Parallel planning agent (cycle 121). The editor's island Vite build already exists
(frontend/vite.config.ts, emptyOutDir:false → static/js/), so CM6 bundling is not a new
pipeline — just one more vanilla-JS island entry. NOT React.

## Verdict: ONE high-value OSS target — the CM5 editor internals. Keep the rest.
- REPLACE: snippet bookmark-walker (~50 lines), 4 hint functions (~75), lint-config shim,
  search addons, vim/emacs/sublime CDN keymaps, stex mode, comment-gutter setGutterMarker,
  swapDoc multi-buffer → CM6 + @codemirror/{autocomplete,search,lint,commands,language},
  @replit/codemirror-vim, codemirror-lang-latex (all MIT). Deletes ~200-260 of 1086 lines,
  removes 11 cdnjs tags, CLOSES #114 (editor dies offline). Native snippetCompletion +
  Lezer folding for free.
- KEEP hand-rolled (correctly): detex word count (small/tested; OSS=Perl texcount adds a
  runtime), difflib diff (already stdlib OSS), pet animation (bespoke product personality).
- Custom logic to PORT by hand (no OSS equiv): B1 library cite autocomplete w/ auto-link,
  B2 live cite-check squiggles, compile-diagnostics→lint bridge.

## CM6 = small multi-cycle sub-epic (3 vertical slices), NOT one [REV]
- Slice A: CM6 island at parity, single file (lang-latex, settings, autosave, find, vim,
  completion+snippets, outline, symbols, beforeunload). Closes #114. 11 CDN tags gone.
- Slice B: multi-file EditorState map (replaces swapDoc; re-prove autosave-after-switch),
  comment gutter as gutter()+StateField+domEventHandlers, diagnostics via linter()+StateEffect.
- Slice C: B1/B2 cite parity as a custom completion source + linter() merge; broken.tex
  fixture must flag the same keys; accept-unlinked still creates ManuscriptReference.
- RISK: CM6 vim is healthy but emacs/sublime are NOT first-class → likely drop to Default+Vim
  (the one capability the migration removes — call out at the gate). lang-latex is younger
  than stex; verify it doesn't fight the custom cite sources.

## Split.js (MIT, ~2KB, zero-dep, vanilla) for resizable/collapsible panels
- Overleaf-UI drag-resize slice. .collapse(i) + onDragEnd(sizes) hook → persist localStorage +
  call view.requestMeasure()/editor.refresh(). Bundle in the island if CM6 shipped, else
  vendor to static/vendor/ (per #114). Alt: split-grid (needs CSS Grid); Splitpanes/react-* rejected (wrong stack).

## SyncTeX: BORROW synctex-js (client-side), DEFER until after CM6
- Prereqs in code: compile.py runs the v1 CLI WITHOUT --synctex (line 104) → must add it
  (verify v1-flag support; pairs with #131 --keep-intermediates for the .bbl). pdf.js TextLayer
  (#116) needed for the reverse click. Parse client-side with synctex-js (vendor/pin; no
  maintained PyPI parser — don't add a C dep). Forward-jump is far cleaner on CM6.

## SEQUENCING (recommended): CM6 sub-epic (A→B→C) BEFORE the heavy Overleaf-UI cycles,
because (1) #114 offline is a real availability bug CM6 fixes as a side effect; (2) Split.js
wants the CM6 view API — doing CM6 first avoids wiring it to CM5 then rewiring; (3) SyncTeX is
cleanest on CM6 (sequences last). Fallback if CM6 deferred: ship #114 standalone (vendor CM5)
+ run visual cycles on CM5 with Split.js→editor.refresh(), CM6 later (more total work).
Note: the error-log relocation (cycle 121) is template-only and independent of CM6 — already shipped.

Critical files: static/js/latex-editor.js, templates/writing/latex_editor.html, frontend/vite.config.ts, writing/compile.py
