/* Atlas LaTeX editor (Owner idea #24).
   Extracted from latex_editor.html in epic slice 2: debounced autosave, in-place
   compile (no page reloads), auto-compile toggle, compile diagnostics rendering. */
/* global CodeMirror */

(function () {
  const cfg = JSON.parse(document.getElementById("editor-config").textContent);
  const CITE_KEYS = JSON.parse(document.getElementById("cite-keys-data").textContent);
  let DIAGNOSTICS = JSON.parse(document.getElementById("diagnostics-data").textContent) || [];

  function csrfToken() {
    const match = document.cookie.match(/(?:^|;\s*)csrftoken=([^;]+)/);
    return match ? decodeURIComponent(match[1]) : "";
  }

  // --- workbench file state ([REV] slice 6) ------------------------------------
  const files = new Map((cfg.files || []).map((f) => [f.id, f]));
  const docs = new Map();
  const dirtySet = new Set();
  const timers = new Map();
  const editGen = new Map();
  let activeId = cfg.mainFileId;

  function fileUrl(id, action) {
    return `${cfg.fileUrlBase}${id}/${action ? action + "/" : ""}`;
  }
  function pathOf(id) {
    return (files.get(id) || { path: "main.tex" }).path;
  }

  // cite state (hoisted above the editor: lint runs during construction — B1/B2)
  let citeLibrary = []; // [{reference_id, key, title, authors, year, linked}]
  let missingCiteKeys = [];
  let editorReady = false; // cite-check helpers are declared below the editor; gate them

  const SETTINGS_KEY = "atlas-editor-settings";
  const settings = Object.assign(
    { keymap: "default", fontSize: "13", spellcheck: false },
    JSON.parse(localStorage.getItem(SETTINGS_KEY) || "{}")
  );

  const textarea = document.getElementById("latex-source");
  const editor = CodeMirror(document.getElementById("editor-host"), {
    value: textarea.value || "% Start writing. \\cite{ } autocompletes from this manuscript's bibliography.\n",
    mode: "stex",
    lineNumbers: true,
    lineWrapping: true,
    viewportMargin: Infinity,
    inputStyle: "contenteditable",  // required for native spellcheck (CM5: construction-time only)
    spellcheck: settings.spellcheck,
    gutters: ["CodeMirror-linenumbers", "CodeMirror-lint-markers"],
    lint: {
      getAnnotations: (text, opts, cm) => {
        const compileAnns = (DIAGNOSTICS || [])
          .filter((d) => d.line && (d.file || "main.tex") === pathOf(activeId))
          .map((d) => ({
            from: CodeMirror.Pos(d.line - 1, 0),
            to: CodeMirror.Pos(d.line - 1, (cm.getLine(d.line - 1) || " ").length),
            severity: d.level === "error" ? "error" : "warning",
            message: d.message,
          }));
        return editorReady ? compileAnns.concat(citeCheckAnnotations(cm)) : compileAnns; // B2
      },
      lintOnChange: false,
    },
  });
  editor.getWrapperElement().style.minHeight = "55vh";
  window.editor = editor; // console + test access
  docs.set(cfg.mainFileId, editor.getDoc());
  editorReady = true; // const/let cite-check helpers below are now initialized

  // --- editor settings + find/replace (epic slice 5) ---------------------------
  function persistSettings() {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
  }
  function applySettings() {
    editor.setOption("keyMap", settings.keymap);
    editor.getWrapperElement().style.fontSize = `${settings.fontSize}px`;
    editor.setOption("spellcheck", settings.spellcheck); // contenteditable honors this live
    editor.refresh();
  }
  const keymapSel = document.getElementById("setting-keymap");
  const fontSel = document.getElementById("setting-fontsize");
  const spellChk = document.getElementById("setting-spellcheck");
  keymapSel.value = settings.keymap;
  fontSel.value = settings.fontSize;
  spellChk.checked = settings.spellcheck;
  keymapSel.addEventListener("change", () => {
    settings.keymap = keymapSel.value;
    persistSettings();
    applySettings();
  });
  fontSel.addEventListener("change", () => {
    settings.fontSize = fontSel.value;
    persistSettings();
    applySettings();
  });
  spellChk.addEventListener("change", () => {
    settings.spellcheck = spellChk.checked;
    persistSettings();
    applySettings();
  });
  applySettings();

  document.getElementById("find-btn").addEventListener("click", () => {
    editor.execCommand("find"); // CM5 search addon dialog (Ctrl/Cmd-F also bound)
  });

  // --- autocomplete v2 + snippets (epic slice 4) -------------------------------
  // Researched: Overleaf completes from a frequency-ranked command table PLUS the
  // commands already used in the document, and expands snippets like \fig with
  // Tab-hoppable placeholders.
  const COMMANDS = (
    "section subsection subsubsection paragraph chapter title author date maketitle " +
    "label ref eqref autoref pageref footnote emph textbf textit texttt textsc underline " +
    "item begin end usepackage documentclass input include includegraphics caption " +
    "centering frac sqrt sum int prod lim infty alpha beta gamma delta epsilon theta " +
    "lambda mu pi sigma phi psi omega Gamma Delta Theta Lambda Sigma Phi Psi Omega " +
    "mathbb mathcal mathrm mathbf text left right cdot times pm mp leq geq neq approx " +
    "partial nabla hat bar tilde vec dot ddot newcommand renewcommand newenvironment " +
    "bibliography bibliographystyle cite citep citet parencite textcite autocite " +
    "tableofcontents listoffigures listoftables appendix hline toprule midrule bottomrule " +
    "multicolumn multirow vspace hspace newpage clearpage linebreak noindent quad qquad " +
    "small large Large huge tiny normalsize itshape bfseries url href verb"
  ).split(" ");
  const ENVIRONMENTS = (
    "document figure table tabular itemize enumerate description equation align " +
    "align* eqnarray gather matrix pmatrix bmatrix cases abstract center quote " +
    "verbatim minipage theorem lemma proof definition algorithm subfigure"
  ).split(" ");
  const SNIPPETS = {
    fig: "\\begin{figure}[ht]\n  \\centering\n  \\includegraphics[width=0.8\\linewidth]{$1}\n  \\caption{$2}\n  \\label{fig:$3}\n\\end{figure}",
    tab: "\\begin{table}[ht]\n  \\centering\n  \\caption{$1}\n  \\label{tab:$2}\n  \\begin{tabular}{lll}\n    \\toprule\n    $3 \\\\\n    \\bottomrule\n  \\end{tabular}\n\\end{table}",
    enum: "\\begin{enumerate}\n  \\item $1\n\\end{enumerate}",
    itemz: "\\begin{itemize}\n  \\item $1\n\\end{itemize}",
    eq: "\\begin{equation}\n  $1\n  \\label{eq:$2}\n\\end{equation}",
  };

  function usedCommands(cm) {
    const found = new Set();
    const re = /\\([a-zA-Z]{2,})/g;
    let m;
    const text = cm.getValue();
    while ((m = re.exec(text)) !== null) found.add(m[1]);
    return found;
  }
  function usedLabels(cm) {
    const labels = [];
    const re = /\\label\{([^}]+)\}/g;
    let m;
    const text = cm.getValue();
    while ((m = re.exec(text)) !== null) labels.push(m[1]);
    return labels;
  }

  // Snippet placeholders: insert, mark each $n, Tab hops through the marks.
  let snippetMarks = [];
  function insertSnippet(cm, from, to, template) {
    const positions = [];
    let text = "";
    let line = from.line;
    let ch = from.ch;
    for (const piece of template.split(/(\$\d)/)) {
      if (/^\$\d$/.test(piece)) {
        positions.push({ line, ch });
        continue;
      }
      text += piece;
      const parts = piece.split("\n");
      if (parts.length > 1) {
        line += parts.length - 1;
        ch = parts[parts.length - 1].length;
      } else {
        ch += piece.length;
      }
    }
    cm.replaceRange(text, from, to);
    snippetMarks = positions.map((pos) =>
      cm.setBookmark(pos, { insertLeft: true })
    );
    hopSnippet(cm);
  }
  function hopSnippet(cm) {
    while (snippetMarks.length) {
      const mark = snippetMarks.shift();
      const pos = mark.find();
      mark.clear();
      if (pos) {
        cm.setCursor(pos);
        return true;
      }
    }
    return false;
  }
  editor.addKeyMap({
    Tab: (cm) => {
      if (snippetMarks.length && hopSnippet(cm)) return;
      return CodeMirror.Pass;
    },
  });

  // Beyond-Overleaf B1: \cite{} completes from the whole project library, not just the
  // already-linked bib. Accepting an unlinked paper auto-creates the ManuscriptReference.
  function loadCiteLibrary() {
    if (!cfg.citeLibraryUrl) return;
    fetch(cfg.citeLibraryUrl)
      .then((r) => r.json())
      .then((d) => { citeLibrary = d.candidates || []; })
      .catch(() => {});
  }
  loadCiteLibrary();

  async function linkReference(referenceId) {
    try {
      await fetch(cfg.citeLibraryUrl, {
        method: "POST",
        headers: { "X-CSRFToken": csrfToken() },
        body: new URLSearchParams({ reference: String(referenceId) }),
      });
      const row = citeLibrary.find((c) => c.reference_id === referenceId);
      if (row) row.linked = true;
    } catch {
      /* the key is inserted regardless; the link can be added from the bibliography UI */
    }
  }

  // Beyond-Overleaf B2: live cite-check. Complete \cite{key} tokens whose key isn't in
  // the library (or already linked) get a calm amber squiggle; a bar offers add-by-DOI.
  const CITE_TOKEN = /\\\w*cite\w*\*?(?:\[[^\]]*\])*\{([^}]+)\}/g;
  function knownCiteKeys() {
    const keys = new Set(CITE_KEYS);
    for (const c of citeLibrary) keys.add(c.key);
    return keys;
  }
  function citeCheckAnnotations(cm) {
    const known = knownCiteKeys();
    if (!known.size && !citeLibrary.length) return []; // library not loaded yet — don't nag
    const anns = [];
    const missing = new Set();
    for (let i = 0; i < cm.lineCount(); i++) {
      const line = cm.getLine(i);
      let m;
      CITE_TOKEN.lastIndex = 0;
      while ((m = CITE_TOKEN.exec(line)) !== null) {
        const inner = m[1];
        const keysStart = m.index + m[0].indexOf("{", 0) + 1;
        let offset = keysStart;
        for (const raw of inner.split(",")) {
          const key = raw.trim();
          const at = line.indexOf(key, offset);
          offset = at + key.length;
          if (key && !known.has(key)) {
            missing.add(key);
            anns.push({
              from: CodeMirror.Pos(i, at),
              to: CodeMirror.Pos(i, at + key.length),
              severity: "warning",
              message: `Citation “${key}” isn't in your library. Add it from the library or by DOI.`,
            });
          }
        }
      }
    }
    missingCiteKeys = [...missing];
    return anns;
  }

  function citeHint(cm) {
    const cursor = cm.getCursor();
    const lineStart = cm.getLine(cursor.line).slice(0, cursor.ch);
    const match = lineStart.match(/\\\w*cite\w*\*?(?:\[[^\]]*\])*\{([^}]*)$/);
    if (!match) return null;
    const fragment = match[1].split(",").pop().trim();
    const from = { line: cursor.line, ch: cursor.ch - fragment.length };
    const f = fragment.toLowerCase();
    const pool = citeLibrary.length
      ? citeLibrary
      : CITE_KEYS.map((k) => ({ key: k, title: "", authors: "", year: null, linked: true }));
    const matches = pool.filter(
      (c) =>
        c.key.toLowerCase().includes(f) ||
        (c.title || "").toLowerCase().includes(f) ||
        (c.authors || "").toLowerCase().includes(f),
    );
    const list = (matches.length ? matches : pool).map((c) => ({
      text: c.key,
      displayText: `${c.linked ? "" : "+ "}${c.key}${c.year ? " (" + c.year + ")" : ""}${
        c.authors ? " · " + c.authors : ""
      }${c.title ? " — " + c.title.slice(0, 60) : ""}`,
      hint: (cmInner, data, completion) => {
        cmInner.replaceRange(completion.text, from, cmInner.getCursor());
        if (c.reference_id && !c.linked) linkReference(c.reference_id);
      },
    }));
    return { list, from, to: cursor };
  }

  function refHint(cm) {
    const cursor = cm.getCursor();
    const lineStart = cm.getLine(cursor.line).slice(0, cursor.ch);
    const match = lineStart.match(/\\(?:ref|eqref|autoref|pageref)\{([^}]*)$/);
    if (!match) return null;
    const fragment = match[1];
    const from = { line: cursor.line, ch: cursor.ch - fragment.length };
    const list = usedLabels(cm).filter((l) => l.startsWith(fragment));
    return list.length ? { list, from, to: cursor } : null;
  }

  function envHint(cm) {
    const cursor = cm.getCursor();
    const lineStart = cm.getLine(cursor.line).slice(0, cursor.ch);
    const match = lineStart.match(/\\(begin|end)\{([^}]*)$/);
    if (!match) return null;
    const [, kind, fragment] = match;
    const from = { line: cursor.line, ch: cursor.ch - fragment.length };
    const list = ENVIRONMENTS.filter((e) => e.startsWith(fragment)).map((env) => ({
      text: env,
      hint: (cmInner, data, completion) => {
        cmInner.replaceRange(completion.text + "}", from, cmInner.getCursor());
        if (kind === "begin") {
          const after = cmInner.getCursor();
          cmInner.replaceRange("\n  \n\\end{" + env + "}", after, after);
          cmInner.setCursor({ line: after.line + 1, ch: 2 });
        }
      },
    }));
    return list.length ? { list, from, to: cursor } : null;
  }

  function commandHint(cm) {
    const cursor = cm.getCursor();
    const lineStart = cm.getLine(cursor.line).slice(0, cursor.ch);
    const match = lineStart.match(/\\([a-zA-Z]{2,})$/);
    if (!match) return null;
    const fragment = match[1];
    const from = { line: cursor.line, ch: cursor.ch - fragment.length - 1 };
    const seen = new Set();
    const list = [];
    for (const key of Object.keys(SNIPPETS)) {
      if (key.startsWith(fragment)) {
        seen.add(key);
        list.push({
          text: "\\" + key,
          displayText: "\\" + key + " → snippet",
          hint: (cmInner) => insertSnippet(cmInner, from, cmInner.getCursor(), SNIPPETS[key]),
        });
      }
    }
    for (const word of [...COMMANDS, ...usedCommands(cm)]) {
      if (!seen.has(word) && word.startsWith(fragment) && word !== fragment) {
        seen.add(word);
        list.push("\\" + word);
      }
    }
    return list.length ? { list, from, to: cursor } : null;
  }

  function latexHint(cm) {
    return citeHint(cm) || refHint(cm) || envHint(cm) || commandHint(cm);
  }
  editor.on("inputRead", (cm, change) => {
    if (!/[\w{,\\]/.test(change.text[0] || "")) return;
    if (latexHint(cm)) cm.showHint({ hint: latexHint, completeSingle: false });
  });

  // --- diagnostics panel -----------------------------------------------------
  const panel = document.getElementById("diagnostics-panel");
  const list = document.getElementById("diagnostics-list");
  const countEl = document.getElementById("diagnostics-count");
  function renderDiagnostics(diags) {
    DIAGNOSTICS = diags || [];
    editor.performLint();
    list.innerHTML = "";
    panel.classList.toggle("hidden", DIAGNOSTICS.length === 0);
    const errors = DIAGNOSTICS.filter((d) => d.level === "error").length;
    const warnings = DIAGNOSTICS.length - errors;
    countEl.textContent = `· ${errors} error${errors === 1 ? "" : "s"}, ${warnings} warning${warnings === 1 ? "" : "s"}`;
    for (const d of DIAGNOSTICS) {
      const li = document.createElement("li");
      li.className = "flex cursor-pointer items-baseline gap-2 px-3 py-1.5 hover:bg-stone-50";
      li.innerHTML =
        `<span class="${d.level === "error" ? "text-red-600" : "text-amber-600"} text-xs font-medium">${d.level}</span>` +
        (d.line ? `<span class="font-mono text-xs text-stone-400">${d.file && d.file !== pathOf(activeId) ? d.file + " " : ""}L${d.line}</span>` : "") +
        '<span class="min-w-0 flex-1 truncate text-xs text-stone-700"></span>';
      li.lastChild.textContent = d.message;
      if (d.line) {
        li.addEventListener("click", async () => {
          const target = [...files.values()].find((f) => f.path === (d.file || "main.tex"));
          if (target && target.id !== activeId) await openFile(target.id);
          editor.setCursor({ line: d.line - 1, ch: 0 });
          editor.focus();
          editor.scrollIntoView({ line: d.line - 1, ch: 0 }, 120);
        });
      }
      list.appendChild(li);
    }
  }
  renderDiagnostics(DIAGNOSTICS);

  // --- autosave (epic slice 2, file-keyed in slice 6) ---------------------------
  const saveStatus = document.getElementById("save-status");
  let dirty = false; // legacy flag for beforeunload

  async function saveFile(id) {
    // Reads from the doc map, never editor.getValue() — a debounce firing after a
    // buffer switch must still save the right file.
    const doc = docs.get(id);
    if (!doc) return;
    const gen = editGen.get(id) || 0;
    if (id === activeId) saveStatus.textContent = "Saving…";
    try {
      const res = await fetch(fileUrl(id, "save"), {
        method: "POST",
        headers: { "X-CSRFToken": csrfToken(), "X-SPA": "1" },
        body: new URLSearchParams({ content: doc.getValue() }),
      });
      if (!res.ok) throw new Error();
      const data = await res.json();
      if ((editGen.get(id) || 0) === gen) dirtySet.delete(id);
      dirty = dirtySet.size > 0;
      if (id === activeId) {
        const t = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
        const cite = data.cite && data.cite.missing_from_bib
          ? ` · ${data.cite.missing_from_bib} missing cite${data.cite.missing_from_bib === 1 ? "" : "s"}`
          : "";
        saveStatus.textContent = `Saved ${t}${cite}`;
        if (autoCompile.checked) triggerCompile();
      }
    } catch {
      if (id === activeId) saveStatus.textContent = "⚠ not saved — retrying";
      setTimeout(() => saveFile(id), 4000);
    }
  }
  function save() { return saveFile(activeId); } // Ctrl-S path
  editor.on("change", (cm, change) => {
    if (change.origin === "setValue") return;
    dirtySet.add(activeId);
    editGen.set(activeId, (editGen.get(activeId) || 0) + 1);
    dirty = true;
    saveStatus.textContent = "…";
    clearTimeout(timers.get(activeId));
    timers.set(activeId, setTimeout(() => saveFile(activeId), 2000));
  });
  window.addEventListener("beforeunload", (e) => {
    if (dirtySet.size) { e.preventDefault(); e.returnValue = ""; }
  });

  // --- file tree ----------------------------------------------------------------
  const tree = document.getElementById("file-tree");
  async function openFile(id) {
    const f = files.get(id);
    if (!f) return;
    if (f.kind === "asset") {
      window.open(f.url, "_blank");
      return;
    }
    clearTimeout(timers.get(activeId));
    if (dirtySet.has(activeId)) saveFile(activeId); // fire-and-forget: doc-map reads
    let doc = docs.get(id);
    if (!doc) {
      const data = await fetch(fileUrl(id, ""), { headers: { Accept: "application/json" } })
        .then((r) => r.json());
      doc = CodeMirror.Doc(data.content || "", "stex");
      docs.set(id, doc);
    }
    activeId = id;
    editor.swapDoc(doc);
    renderTree();
    renderOutline();
    editor.performLint();
    editor.focus();
  }
  function renderTree() {
    tree.innerHTML = "";
    const sorted = [...files.values()].sort((a, b) => a.path.localeCompare(b.path));
    for (const f of sorted) {
      const li = document.createElement("li");
      li.className = `group flex items-center gap-1 px-3 py-1 text-xs ${
        f.id === activeId ? "bg-indigo-50 font-medium text-indigo-800" : "cursor-pointer hover:bg-stone-50"
      }`;
      const name = document.createElement("span");
      name.className = "min-w-0 flex-1 truncate";
      name.textContent = f.path;
      name.title = f.path;
      li.appendChild(name);
      if (f.is_main) {
        const badge = document.createElement("span");
        badge.className = "rounded bg-stone-100 px-1 text-[10px] text-stone-500";
        badge.textContent = "main";
        li.appendChild(badge);
      }
      if (dirtySet.has(f.id)) {
        const dot = document.createElement("span");
        dot.className = "text-amber-500";
        dot.textContent = "●";
        li.appendChild(dot);
      }
      if (!f.is_main) {
        const del = document.createElement("button");
        del.className = "hidden text-stone-400 hover:text-red-600 group-hover:inline";
        del.textContent = "✕";
        del.title = "Delete";
        del.addEventListener("click", async (e) => {
          e.stopPropagation();
          if (!confirm(`Delete ${f.path}?`)) return;
          await fetch(fileUrl(f.id, "delete"), {
            method: "POST", headers: { "X-CSRFToken": csrfToken() },
          });
          files.delete(f.id);
          docs.delete(f.id);
          if (activeId === f.id) openFile(cfg.mainFileId);
          renderTree();
        });
        li.appendChild(del);
      }
      li.addEventListener("click", () => openFile(f.id));
      tree.appendChild(li);
    }
  }
  renderTree();

  // --- outline panel + word count (epic slice 8) ------------------------------
  const outlineList = document.getElementById("outline-list");
  const HEADING_RE = /\\(part|chapter|section|subsection|subsubsection|paragraph)\*?\{([^}]*)\}/;
  const HEADING_DEPTH = {
    part: 0, chapter: 0, section: 0, subsection: 1, subsubsection: 2, paragraph: 3,
  };
  function renderOutline() {
    outlineList.innerHTML = "";
    const doc = editor.getDoc();
    for (let i = 0; i < doc.lineCount(); i++) {
      const m = HEADING_RE.exec(doc.getLine(i));
      if (!m) continue;
      const li = document.createElement("li");
      li.className = "cursor-pointer truncate py-0.5 text-stone-600 hover:text-indigo-700";
      li.style.paddingLeft = `${HEADING_DEPTH[m[1]] * 10}px`;
      li.textContent = m[2] || "(untitled)";
      li.title = m[2];
      const line = i;
      li.addEventListener("click", () => {
        editor.setCursor({ line, ch: 0 });
        editor.focus();
        editor.scrollIntoView({ line, ch: 0 }, 120);
      });
      outlineList.appendChild(li);
    }
    if (!outlineList.children.length) {
      outlineList.innerHTML = '<li class="py-0.5 text-stone-400">No sections yet.</li>';
    }
  }
  renderOutline();
  let outlineTimer = null;
  editor.on("change", () => {
    clearTimeout(outlineTimer);
    outlineTimer = setTimeout(() => {
      renderOutline();
      editor.performLint(); // re-run cite-check (B2)
      renderMissingCites();
    }, 600);
  });

  // --- live cite-check bar (beyond-Overleaf B2) --------------------------------
  const citeBar = document.getElementById("cite-missing-bar");
  const citeKeysOut = document.getElementById("cite-missing-keys");
  const citeDoiInput = document.getElementById("cite-doi-input");
  const citeDoiStatus = document.getElementById("cite-doi-status");
  function renderMissingCites() {
    if (!citeBar) return;
    if (!missingCiteKeys.length) {
      citeBar.classList.add("hidden");
      return;
    }
    citeBar.classList.remove("hidden");
    citeKeysOut.textContent = missingCiteKeys.join(", ");
  }
  document.getElementById("cite-doi-add")?.addEventListener("click", async () => {
    const doi = citeDoiInput.value.trim();
    if (!doi) return;
    citeDoiStatus.textContent = "adding…";
    try {
      const res = await fetch("/api/v1/references/by-doi/", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
        body: JSON.stringify({ doi, project: cfg.projectSlug }),
      });
      if (!res.ok) throw new Error();
      const ref = await res.json();
      citeDoiStatus.textContent = `added ${ref.bibtex_key}`;
      citeDoiInput.value = "";
      await new Promise((r) => setTimeout(() => { loadCiteLibrary(); r(); }, 200));
      setTimeout(() => { editor.performLint(); renderMissingCites(); }, 500);
    } catch {
      citeDoiStatus.textContent = "couldn't add — check the DOI";
    }
  });
  // initial check once the library has loaded
  setTimeout(() => { editor.performLint(); renderMissingCites(); }, 1000);

  // --- research side panel (beyond-Overleaf B3) -------------------------------
  const researchPanel = document.getElementById("research-panel");
  const rpBib = document.getElementById("rp-bib");
  const rpNotes = document.getElementById("rp-notes");
  const rpHyps = document.getElementById("rp-hyps");
  const rpNotesQ = document.getElementById("rp-notes-q");
  const HYP_COLOR = {
    supported: "text-green-700", contradicted: "text-red-700",
    testing: "text-indigo-700", proposed: "text-stone-500",
    inconclusive: "text-amber-700", abandoned: "text-stone-400",
  };
  function insertCite(key) {
    const cur = editor.getCursor();
    editor.replaceRange(`\\cite{${key}}`, cur);
    editor.focus();
  }
  function renderContext(data) {
    rpBib.innerHTML = "";
    if (!data.bib.length) rpBib.innerHTML = '<li class="text-xs text-stone-400">No linked references yet.</li>';
    for (const r of data.bib) {
      const li = document.createElement("li");
      li.className = "group rounded px-1.5 py-1 hover:bg-stone-50";
      const meta = `${r.authors || ""}${r.year ? " · " + r.year : ""}`;
      li.innerHTML =
        `<div class="flex items-baseline gap-1"><button class="rp-cite font-mono text-xs text-indigo-700 hover:underline" title="Insert \\cite">${r.key}</button></div>` +
        `<div class="truncate text-xs text-stone-500" title="${r.title.replace(/"/g, "&quot;")}">${r.title}</div>` +
        (meta ? `<div class="text-[10px] text-stone-400">${meta}</div>` : "");
      li.querySelector(".rp-cite").addEventListener("click", () => insertCite(r.key));
      rpBib.appendChild(li);
    }
    renderNotes(data.notes);
    rpHyps.innerHTML = "";
    if (!data.hypotheses.length) rpHyps.innerHTML = '<li class="text-xs text-stone-400">No hypotheses.</li>';
    for (const h of data.hypotheses) {
      const li = document.createElement("li");
      li.className = "rounded px-1.5 py-1 text-xs";
      li.innerHTML = `<span class="${HYP_COLOR[h.status] || "text-stone-500"} font-medium">${h.status}</span> <span class="text-stone-600">${h.statement}</span>`;
      rpHyps.appendChild(li);
    }
  }
  function renderNotes(notes) {
    rpNotes.innerHTML = "";
    if (!notes.length) { rpNotes.innerHTML = '<li class="text-xs text-stone-400">No notes.</li>'; return; }
    for (const n of notes) {
      const li = document.createElement("li");
      li.className = "truncate text-xs";
      li.innerHTML = `<a href="${n.url}" target="_blank" class="text-stone-600 hover:text-indigo-700 hover:underline">${n.title}</a>`;
      rpNotes.appendChild(li);
    }
  }
  let contextLoaded = false;
  async function loadContext(q) {
    const url = cfg.contextUrl + (q ? `?q=${encodeURIComponent(q)}` : "");
    try {
      const data = await fetch(url).then((r) => r.json());
      if (q !== undefined) renderNotes(data.notes); else renderContext(data);
    } catch { /* panel stays as-is */ }
  }
  let notesTimer = null;
  rpNotesQ?.addEventListener("input", () => {
    clearTimeout(notesTimer);
    notesTimer = setTimeout(() => loadContext(rpNotesQ.value.trim()), 300);
  });
  function setResearch(open) {
    researchPanel.classList.toggle("hidden", !open);
    localStorage.setItem("atlas-editor-research", open ? "1" : "0");
    if (open && !contextLoaded) { contextLoaded = true; loadContext(); }
  }
  document.getElementById("research-toggle")?.addEventListener("click", () =>
    setResearch(researchPanel.classList.contains("hidden"))
  );
  if (localStorage.getItem("atlas-editor-research") === "1") setResearch(true);

  // --- symbol palette (epic slice 10): insert LaTeX symbols at the cursor ------
  const SYMBOLS = {
    Greek: ["\\alpha", "\\beta", "\\gamma", "\\delta", "\\epsilon", "\\theta",
            "\\lambda", "\\mu", "\\pi", "\\sigma", "\\phi", "\\psi", "\\omega",
            "\\Gamma", "\\Delta", "\\Theta", "\\Lambda", "\\Sigma", "\\Phi", "\\Omega"],
    Operators: ["\\sum", "\\prod", "\\int", "\\partial", "\\nabla", "\\infty",
                "\\sqrt{}", "\\frac{}{}", "\\cdot", "\\times", "\\pm", "\\mp"],
    Relations: ["\\leq", "\\geq", "\\neq", "\\approx", "\\equiv", "\\propto",
                "\\sim", "\\in", "\\subset", "\\forall", "\\exists"],
    Arrows: ["\\to", "\\rightarrow", "\\leftarrow", "\\Rightarrow", "\\Leftarrow",
             "\\leftrightarrow", "\\mapsto", "\\uparrow", "\\downarrow"],
  };
  const symGrid = document.getElementById("symbol-grid");
  if (symGrid) {
    for (const [cat, syms] of Object.entries(SYMBOLS)) {
      const h = document.createElement("p");
      h.className = "mb-1 mt-1 text-[10px] font-medium uppercase tracking-wide text-stone-400";
      h.textContent = cat;
      symGrid.appendChild(h);
      const row = document.createElement("div");
      row.className = "mb-1 grid grid-cols-6 gap-0.5";
      for (const sym of syms) {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "rounded px-1 py-0.5 text-center font-mono text-xs text-stone-600 hover:bg-stone-100";
        btn.textContent = sym.replace(/\\/g, "").replace(/\{\}/g, "").replace(/\{\}\{\}/g, "") || sym;
        btn.title = sym;
        btn.addEventListener("click", () => {
          const cur = editor.getCursor();
          editor.replaceRange(sym, cur);
          // place cursor inside the first {} if present
          const brace = sym.indexOf("{}");
          if (brace !== -1) editor.setCursor({ line: cur.line, ch: cur.ch + brace + 1 });
          editor.focus();
        });
        row.appendChild(btn);
      }
      symGrid.appendChild(row);
    }
  }

  const wcBtn = document.getElementById("wordcount-btn");
  const wcOut = document.getElementById("wordcount-out");
  wcBtn.addEventListener("click", async () => {
    wcOut.textContent = "…";
    await saveFile(activeId); // count what's on screen, not the last autosave
    try {
      const data = await fetch(cfg.wordCountUrl).then((r) => r.json());
      wcOut.textContent = `~${data.words} words · ${data.headers} headings`;
      wcOut.title = `approx ${data.words} words, ${data.headers} headings, ${data.captions} captions, ${data.math_inlines} inline math`;
    } catch {
      wcOut.textContent = "—";
    }
  });

  // --- version history (epic slice 9) -----------------------------------------
  const revisionsList = document.getElementById("revisions-list");
  const revModal = document.getElementById("revision-modal");
  const revDiff = document.getElementById("revision-diff");
  let activeRevisionId = null;
  function relTime(iso) {
    const secs = Math.round((Date.now() - new Date(iso)) / 1000);
    if (secs < 60) return "just now";
    if (secs < 3600) return `${Math.floor(secs / 60)}m ago`;
    if (secs < 86400) return `${Math.floor(secs / 3600)}h ago`;
    return new Date(iso).toLocaleDateString();
  }
  async function loadRevisions() {
    try {
      const data = await fetch(cfg.revisionsUrl).then((r) => r.json());
      revisionsList.innerHTML = "";
      if (!data.revisions.length) {
        revisionsList.innerHTML = '<li class="py-0.5 text-stone-400">Compile to start history.</li>';
        return;
      }
      for (const r of data.revisions) {
        const li = document.createElement("li");
        li.className = "cursor-pointer truncate py-0.5 text-stone-600 hover:text-indigo-700";
        li.textContent = (r.labeled ? `★ ${r.label}` : relTime(r.created_at));
        li.title = r.labeled ? `${r.label} · ${relTime(r.created_at)}` : "automatic snapshot";
        li.addEventListener("click", () => openRevision(r));
        revisionsList.appendChild(li);
      }
    } catch {
      revisionsList.innerHTML = '<li class="py-0.5 text-stone-400">—</li>';
    }
  }
  function renderDiff(diffs, unchanged) {
    revDiff.innerHTML = "";
    if (unchanged) {
      revDiff.innerHTML = '<p class="font-sans text-sm text-stone-400">Identical to the current files.</p>';
      return;
    }
    for (const d of diffs) {
      const h = document.createElement("p");
      h.className = "mb-1 font-sans font-medium text-stone-600";
      h.textContent = d.path;
      revDiff.appendChild(h);
      const pre = document.createElement("pre");
      pre.className = "mb-3 whitespace-pre-wrap";
      for (const line of d.diff.split("\n")) {
        const span = document.createElement("span");
        span.className = "block " + (line.startsWith("+") && !line.startsWith("+++") ? "text-green-700 bg-green-50" :
          line.startsWith("-") && !line.startsWith("---") ? "text-red-700 bg-red-50" :
          line.startsWith("@@") ? "text-indigo-600" : "text-stone-500");
        span.textContent = line;
        pre.appendChild(span);
      }
      revDiff.appendChild(pre);
    }
  }
  async function openRevision(r) {
    activeRevisionId = r.id;
    document.getElementById("revision-modal-title").textContent =
      r.labeled ? r.label : `Snapshot · ${relTime(r.created_at)}`;
    revDiff.innerHTML = '<p class="font-sans text-sm text-stone-400">Loading diff…</p>';
    revModal.classList.remove("hidden");
    revModal.classList.add("flex");
    const data = await fetch(`${cfg.revisionsUrl}${r.id}/diff/`).then((x) => x.json());
    renderDiff(data.diffs, data.unchanged);
  }
  function closeRevision() {
    revModal.classList.add("hidden");
    revModal.classList.remove("flex");
    activeRevisionId = null;
  }
  document.getElementById("revision-modal-close").addEventListener("click", closeRevision);
  document.getElementById("revision-cancel").addEventListener("click", closeRevision);
  document.getElementById("revision-modal-bg").addEventListener("click", closeRevision);
  document.getElementById("revision-restore-btn").addEventListener("click", async () => {
    if (activeRevisionId == null) return;
    await fetch(`${cfg.revisionsUrl}${activeRevisionId}/restore/`, {
      method: "POST", headers: { "X-CSRFToken": csrfToken() },
    });
    closeRevision();
    location.reload(); // restored files: reload to repopulate buffers cleanly
  });
  document.getElementById("label-version-btn").addEventListener("click", async () => {
    const label = prompt("Label this version:");
    if (!label) return;
    if (dirtySet.has(activeId)) await saveFile(activeId);
    await fetch(cfg.revisionsUrl, {
      method: "POST", headers: { "X-CSRFToken": csrfToken() },
      body: new URLSearchParams({ label }),
    });
    loadRevisions();
  });
  loadRevisions();

  const newFileForm = document.getElementById("new-file-form");
  const newFilePath = document.getElementById("new-file-path");
  document.getElementById("new-file-btn").addEventListener("click", () => {
    newFileForm.classList.toggle("hidden");
    newFilePath.focus();
  });
  newFileForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const res = await fetch(cfg.filesUrl, {
      method: "POST",
      headers: { "X-CSRFToken": csrfToken() },
      body: new URLSearchParams({ path: newFilePath.value.trim() }),
    });
    const data = await res.json();
    if (!res.ok) { alert(data.error || "Could not create file."); return; }
    files.set(data.id, data);
    newFilePath.value = "";
    newFileForm.classList.add("hidden");
    openFile(data.id);
  });

  const assetInput = document.getElementById("asset-input");
  document.getElementById("upload-btn").addEventListener("click", () => assetInput.click());
  assetInput.addEventListener("change", async () => {
    for (const file of assetInput.files) {
      const form = new FormData();
      form.append("file", file);
      const res = await fetch(`${cfg.filesUrl}upload/`, {
        method: "POST", headers: { "X-CSRFToken": csrfToken() }, body: form,
      });
      const data = await res.json();
      if (!res.ok) { alert(data.error || `Could not upload ${file.name}.`); continue; }
      files.set(data.id, data);
    }
    assetInput.value = "";
    renderTree();
  });

  // --- pdf.js preview pane (epic slice 3) --------------------------------------
  const previewPane = document.getElementById("preview-pane");
  const previewEmpty = document.getElementById("preview-empty");
  const previewStatus = document.getElementById("preview-status");
  const toggleBtn = document.getElementById("toggle-preview");
  const autoCompile = document.getElementById("auto-compile");
  const pdfScroll = document.getElementById("pdf-scroll");
  const pdfPages = document.getElementById("pdf-pages");
  const pageIndicator = document.getElementById("page-indicator");
  const zoomLabel = document.getElementById("zoom-label");

  const PDFJS = "https://cdn.jsdelivr.net/npm/pdfjs-dist@4.10.38/build/";
  let pdfjsLib = null;
  let pdfDoc = null;
  let fitWidth = localStorage.getItem("atlas-editor-zoom") !== "manual";
  let zoom = parseFloat(localStorage.getItem("atlas-editor-zoom-value") || "1");

  async function ensurePdfjs() {
    if (!pdfjsLib) {
      pdfjsLib = await import(`${PDFJS}pdf.min.mjs`);
      pdfjsLib.GlobalWorkerOptions.workerSrc = `${PDFJS}pdf.worker.min.mjs`;
    }
    return pdfjsLib;
  }

  async function renderPdf(url) {
    // Overleaf-parity behaviors (researched): fit-width default, scroll position
    // preserved across recompiles, old pages stay visible (dimmed) while loading.
    const lib = await ensurePdfjs();
    const keepScroll = pdfScroll.scrollTop;
    pdfDoc = await lib.getDocument(url).promise;
    const fresh = document.createDocumentFragment();
    const paneWidth = pdfScroll.clientWidth - 24;
    for (let n = 1; n <= pdfDoc.numPages; n++) {
      const page = await pdfDoc.getPage(n);
      const base = page.getViewport({ scale: 1 });
      const scale = fitWidth ? paneWidth / base.width : zoom * 1.5;
      const viewport = page.getViewport({ scale: scale * (window.devicePixelRatio || 1) });
      const canvas = document.createElement("canvas");
      canvas.width = viewport.width;
      canvas.height = viewport.height;
      canvas.style.width = `${viewport.width / (window.devicePixelRatio || 1)}px`;
      canvas.className = "bg-white shadow-sm";
      canvas.dataset.page = n;
      await page.render({ canvasContext: canvas.getContext("2d"), viewport }).promise;
      fresh.appendChild(canvas);
    }
    pdfPages.replaceChildren(fresh);
    previewEmpty.classList.add("hidden");
    pdfScroll.scrollTop = keepScroll;
    zoomLabel.textContent = fitWidth ? "fit" : `${Math.round(zoom * 100)}%`;
    pageIndicator.classList.remove("hidden");
    updatePageIndicator();
  }

  function updatePageIndicator() {
    if (!pdfDoc) return;
    const mid = pdfScroll.scrollTop + pdfScroll.clientHeight / 3;
    let current = 1;
    for (const canvas of pdfPages.children) {
      if (canvas.offsetTop <= mid) current = Number(canvas.dataset.page);
    }
    pageIndicator.textContent = `p. ${current}/${pdfDoc.numPages}`;
  }
  pdfScroll.addEventListener("scroll", updatePageIndicator, { passive: true });

  function setZoom(mode, value) {
    fitWidth = mode === "fit";
    if (!fitWidth) zoom = Math.min(3, Math.max(0.4, value));
    localStorage.setItem("atlas-editor-zoom", fitWidth ? "fit" : "manual");
    localStorage.setItem("atlas-editor-zoom-value", String(zoom));
    if (cfg.pdfUrl || lastPdfUrl) renderPdf(lastPdfUrl || cfg.pdfUrl);
  }
  document.getElementById("zoom-in").addEventListener("click", () => setZoom("manual", (fitWidth ? 1 : zoom) + 0.2));
  document.getElementById("zoom-out").addEventListener("click", () => setZoom("manual", (fitWidth ? 1 : zoom) - 0.2));
  document.getElementById("zoom-fit").addEventListener("click", () => setZoom("fit"));

  function setPreview(open) {
    previewPane.classList.toggle("hidden", !open);
    localStorage.setItem("atlas-editor-preview", open ? "1" : "0");
    if (open && cfg.pdfUrl && !pdfDoc) renderPdf(cfg.pdfUrl);
  }
  toggleBtn.addEventListener("click", () => setPreview(previewPane.classList.contains("hidden")));
  if (localStorage.getItem("atlas-editor-preview") === "1" || cfg.hasPdf) setPreview(true);

  autoCompile.checked = localStorage.getItem("atlas-editor-autocompile") === "1";
  autoCompile.addEventListener("change", () => {
    localStorage.setItem("atlas-editor-autocompile", autoCompile.checked ? "1" : "0");
  });

  // --- compile without reload (epic slice 2) ----------------------------------
  let polling = null;
  let lastPdfUrl = "";
  function poll() {
    fetch(cfg.statusUrl)
      .then((r) => r.json())
      .then((data) => {
        if (data.status === "running") {
          previewStatus.textContent = "⏳ compiling…";
          return;
        }
        clearInterval(polling);
        polling = null;
        pdfScroll.classList.remove("opacity-50");
        renderDiagnostics(data.diagnostics || []);
        if (data.status === "ok" && data.pdf_url) {
          previewStatus.textContent = `✓ compiled ${new Date(data.compiled_at).toLocaleTimeString()}`;
          lastPdfUrl = `${data.pdf_url}?t=${Date.parse(data.compiled_at)}`;
          renderPdf(lastPdfUrl);
          loadRevisions(); // a successful compile created a snapshot
        } else if (data.status === "failed") {
          previewStatus.textContent = "✕ compile failed — see problems below";
          if (!pdfDoc) previewEmpty.classList.remove("hidden");
        }
      })
      .catch(() => {});
  }
  async function triggerCompile() {
    setPreview(true);
    previewStatus.textContent = "⏳ compiling…";
    pdfScroll.classList.add("opacity-50"); // old PDF stays visible, dimmed
    try {
      for (const id of [...dirtySet]) clearTimeout(timers.get(id));
      await Promise.all([...dirtySet].map((id) => saveFile(id)));
      await fetch(cfg.compileUrl, {
        method: "POST",
        headers: { "X-CSRFToken": csrfToken(), "X-SPA": "1" },
      });
      if (!polling) polling = setInterval(poll, 1500);
    } catch {
      previewStatus.textContent = "⚠ could not start compile";
      pdfScroll.classList.remove("opacity-50");
    }
  }
  document.getElementById("compile-btn").addEventListener("click", triggerCompile);
  window.triggerCompile = triggerCompile;
  if (cfg.compileRunning && !polling) polling = setInterval(poll, 1500);

  // --- keyboard ---------------------------------------------------------------
  document.addEventListener("keydown", (event) => {
    if ((event.ctrlKey || event.metaKey) && event.key === "s") {
      event.preventDefault();
      clearTimeout(saveTimer);
      save();
    }
  });
})();
