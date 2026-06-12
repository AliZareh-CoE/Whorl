/* Atlas LaTeX editor glue (Owner idea #24/#28).
   Drives the CodeMirror 6 island (latex-editor-cm6.js, Backlog #135) — the editor
   mechanics (language, autocomplete, snippets, search, vim, cite B1/B2, diagnostics
   lint) live in the island; this module is the app glue: file tree, autosave, outline,
   word count, history, research panel, symbols, comments, pdf.js preview, compile.
   The hand-rolled CM5 snippet walker, hint functions, and cite-check moved into the
   island (or its libraries) and were deleted from here. Zero CDN editor dependencies
   remain (closes Backlog #114). */
import { mountEditor, Split } from "./latex-editor-cm6.js";

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
  const loadedFiles = new Set([cfg.mainFileId]); // ids whose content is in the island
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

  const SETTINGS_KEY = "atlas-editor-settings";
  const settings = Object.assign(
    { keymap: "default", fontSize: "13", spellcheck: false },
    JSON.parse(localStorage.getItem(SETTINGS_KEY) || "{}")
  );

  // --- mount the CM6 island ----------------------------------------------------
  const textarea = document.getElementById("latex-source");
  const ad = mountEditor(document.getElementById("editor-host"), {
    citeKeys: CITE_KEYS,
    initialDoc: textarea.value || "% Start writing. \\cite{ } autocompletes from your library.\n",
    initialFileId: cfg.mainFileId,
    citeLibraryUrl: cfg.citeLibraryUrl,
    csrfToken: csrfToken(),
  });

  // a small CM5-shaped surface for the console and browser tests
  window.editor = {
    getValue: () => ad.getValue(),
    setValue: (s) => ad.setValue(s),
    getCursor: () => ({ line: ad.getCursorLine() - 1, ch: 0 }),
    setCursor: (p) => ad.gotoLine((p.line || 0) + 1),
    getLine: (n) => ad.lineText(n + 1),
    lineCount: () => ad.lineCount(),
    lastLine: () => ad.lineCount() - 1,
    replaceRange: (text) => ad.insertAtCursor(text),
    focus: () => ad.focus(),
  };

  // --- editor settings + find/replace (epic slice 5) ---------------------------
  function persistSettings() {
    localStorage.setItem(SETTINGS_KEY, JSON.stringify(settings));
  }
  function applySettings() {
    ad.setKeymap(settings.keymap);
    ad.setFontSize(settings.fontSize);
    ad.setSpellcheck(settings.spellcheck);
  }
  const keymapSel = document.getElementById("setting-keymap");
  const fontSel = document.getElementById("setting-fontsize");
  const spellChk = document.getElementById("setting-spellcheck");
  if (!["default", "vim"].includes(settings.keymap)) settings.keymap = "default"; // CM6: default+vim
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

  document.getElementById("find-btn").addEventListener("click", () => ad.openFind());

  // --- diagnostics panel -------------------------------------------------------
  const panel = document.getElementById("diagnostics-panel");
  const list = document.getElementById("diagnostics-list");
  const countEl = document.getElementById("diagnostics-count");
  const logsBadge = document.getElementById("logs-badge");
  function pushDiagnostics() {
    // the island lints with these (and merges its own live cite-check)
    ad.setDiagnostics(
      (DIAGNOSTICS || []).filter((d) => d.line && (d.file || "main.tex") === pathOf(activeId))
    );
  }
  function renderDiagnostics(diags) {
    DIAGNOSTICS = diags || [];
    pushDiagnostics();
    list.innerHTML = "";
    const errors = DIAGNOSTICS.filter((d) => d.level === "error").length;
    const warnings = DIAGNOSTICS.length - errors;
    if (logsBadge) {
      logsBadge.textContent = errors ? String(errors) : "";
      logsBadge.classList.toggle("hidden", errors === 0);
    }
    panel.classList.toggle("hidden", DIAGNOSTICS.length === 0);
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
          ad.gotoLine(d.line);
        });
      }
      list.appendChild(li);
    }
  }
  renderDiagnostics(DIAGNOSTICS);

  // --- autosave (epic slice 2, file-keyed in slice 6) ---------------------------
  const saveStatus = document.getElementById("save-status");

  async function saveFile(id) {
    // Reads the island's per-file state, never a shared live value — a debounce firing
    // after a buffer switch must still save the right file.
    const content = ad.fileValue(id);
    const gen = editGen.get(id) || 0;
    if (id === activeId) saveStatus.textContent = "Saving…";
    try {
      const res = await fetch(fileUrl(id, "save"), {
        method: "POST",
        headers: { "X-CSRFToken": csrfToken(), "X-SPA": "1" },
        body: new URLSearchParams({ content }),
      });
      if (!res.ok) throw new Error();
      const data = await res.json();
      if ((editGen.get(id) || 0) === gen) dirtySet.delete(id);
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
  ad.onChange(() => {
    dirtySet.add(activeId);
    editGen.set(activeId, (editGen.get(activeId) || 0) + 1);
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
    if (dirtySet.has(activeId)) saveFile(activeId); // fire-and-forget: island-state reads
    if (!loadedFiles.has(id)) {
      const data = await fetch(fileUrl(id, ""), { headers: { Accept: "application/json" } })
        .then((r) => r.json());
      ad.setFileValue(id, data.content || "");
      loadedFiles.add(id);
    }
    activeId = id;
    ad.switchFile(id);
    renderTree();
    renderOutline();
    pushDiagnostics();
    refreshCommentGutter();
    ad.focus();
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
          loadedFiles.delete(f.id);
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
    for (let i = 1; i <= ad.lineCount(); i++) {
      const m = HEADING_RE.exec(ad.lineText(i));
      if (!m) continue;
      const li = document.createElement("li");
      li.className = "cursor-pointer truncate py-0.5 text-stone-600 hover:text-indigo-700";
      li.style.paddingLeft = `${HEADING_DEPTH[m[1]] * 10}px`;
      li.textContent = m[2] || "(untitled)";
      li.title = m[2];
      const line = i;
      li.addEventListener("click", () => ad.gotoLine(line));
      outlineList.appendChild(li);
    }
    if (!outlineList.children.length) {
      outlineList.innerHTML = '<li class="py-0.5 text-stone-400">No sections yet.</li>';
    }
  }
  renderOutline();
  let outlineTimer = null;
  ad.onChange(() => {
    clearTimeout(outlineTimer);
    outlineTimer = setTimeout(renderOutline, 600);
  });

  // --- live cite-check bar (beyond-Overleaf B2; the island computes the keys) ---
  const citeBar = document.getElementById("cite-missing-bar");
  const citeKeysOut = document.getElementById("cite-missing-keys");
  const citeDoiInput = document.getElementById("cite-doi-input");
  const citeDoiStatus = document.getElementById("cite-doi-status");
  let missingCiteKeys = [];
  ad.onCiteCheck((keys) => {
    missingCiteKeys = keys;
    renderMissingCites();
  });
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
      setTimeout(() => {
        ad.reloadCiteLibrary();
        setTimeout(pushDiagnostics, 600); // re-lint with the refreshed library
      }, 200);
    } catch {
      citeDoiStatus.textContent = "couldn't add — check the DOI";
    }
  });

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
    ad.insertAtCursor(`\\cite{${key}}`);
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
          const brace = sym.indexOf("{}");
          ad.insertAtCursor(sym, brace !== -1 ? brace + 1 : undefined);
        });
        row.appendChild(btn);
      }
      symGrid.appendChild(row);
    }
  }

  // --- line-anchored comments (beyond-Overleaf B6) ------------------------------
  function commentUrl(fileId) {
    return `/api/v1/comments/manuscript_file/${fileId}/`;
  }
  let commentLine = null;
  const commentModal = document.getElementById("comment-modal");
  const commentThread = document.getElementById("comment-thread");
  const commentInput = document.getElementById("comment-input");
  const commentTitle = document.getElementById("comment-modal-title");

  async function refreshCommentGutter() {
    try {
      const data = await fetch(commentUrl(activeId)).then((r) => r.json());
      const lines = [...new Set((data.comments || []).filter((c) => c.line).map((c) => c.line))];
      ad.setCommentLines(lines);
    } catch { /* leave the gutter empty */ }
  }
  // clicking either gutter opens the thread for that line (the island reports 1-based)
  ad.onGutterClick((line) => openCommentThread(line));

  async function openCommentThread(line) {
    commentLine = line;
    commentTitle.textContent = `Line ${line} — ${pathOf(activeId)}`;
    commentThread.innerHTML = '<p class="text-sm text-stone-400">Loading…</p>';
    commentModal.classList.remove("hidden");
    commentModal.classList.add("flex");
    commentInput.value = "";
    const data = await fetch(commentUrl(activeId)).then((r) => r.json());
    const here = (data.comments || []).filter((c) => c.line === line);
    commentThread.innerHTML = "";
    if (!here.length) commentThread.innerHTML = '<p class="text-sm text-stone-400">No comments on this line yet.</p>';
    for (const c of here) {
      const div = document.createElement("div");
      div.className = "rounded border border-stone-100 bg-stone-50 px-3 py-2";
      div.innerHTML = `<p class="whitespace-pre-wrap text-sm text-stone-700"></p><p class="mt-1 text-xs text-stone-400">${c.created_at.slice(0, 10)}</p>`;
      div.querySelector("p").textContent = c.body;
      commentThread.appendChild(div);
    }
    commentInput.focus();
  }
  function closeCommentThread() {
    commentModal.classList.add("hidden");
    commentModal.classList.remove("flex");
    commentLine = null;
  }
  async function postComment() {
    const body = commentInput.value.trim();
    if (!body || commentLine == null) return;
    await fetch(commentUrl(activeId), {
      method: "POST",
      headers: { "Content-Type": "application/json", "X-CSRFToken": csrfToken() },
      body: JSON.stringify({ body, line: commentLine }),
    });
    const line = commentLine;
    await refreshCommentGutter();
    openCommentThread(line);
  }
  document.getElementById("comment-post").addEventListener("click", postComment);
  document.getElementById("comment-cancel").addEventListener("click", closeCommentThread);
  document.getElementById("comment-modal-close").addEventListener("click", closeCommentThread);
  document.getElementById("comment-modal-bg").addEventListener("click", closeCommentThread);
  commentInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter" && (e.metaKey || e.ctrlKey)) postComment();
  });
  refreshCommentGutter();

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

  // --- Split.js resizable panels (Owner idea #26/#28: borrowed, not hand-rolled) ---
  const SPLIT_KEY = "atlas-editor-split";
  const sidebar = document.getElementById("file-sidebar");
  let split = null;

  // thin restore strips at the edges (Overleaf's "thin panel" affordance, #138)
  function makeStrip(label, title, onClick) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.textContent = label;
    btn.title = title;
    btn.className =
      "hidden shrink-0 self-stretch rounded border border-stone-200 bg-stone-50 px-0.5 " +
      "text-[10px] text-stone-400 hover:bg-stone-100 hover:text-indigo-700";
    btn.addEventListener("click", onClick);
    return btn;
  }
  const sidebarRestore = makeStrip("»", "Show the file sidebar", () => setSidebar(true));
  const previewRestore = makeStrip("«", "Show the PDF preview", () => setPreview(true));
  sidebar.parentElement.insertBefore(sidebarRestore, sidebar);
  previewPane.parentElement.insertBefore(previewRestore, previewPane.nextSibling);

  function addChevron(g, label, title, onClick) {
    const chev = document.createElement("button");
    chev.type = "button";
    chev.textContent = label;
    chev.title = title;
    chev.className =
      "absolute left-1/2 top-8 z-10 -translate-x-1/2 rounded-full border border-stone-200 " +
      "bg-white px-1 text-[9px] leading-4 text-stone-400 shadow-sm hover:text-indigo-700";
    chev.addEventListener("mousedown", (e) => e.stopPropagation());
    chev.addEventListener("click", onClick);
    g.style.position = "relative";
    g.appendChild(chev);
  }
  function decorateGutters(sidebarOpen, previewOpen) {
    // gutters appear in pane order; hidden modals in the container break sibling checks,
    // so decorate by position: first gutter = sidebar|editor when the sidebar is open,
    // last gutter = editor|preview when the preview is open.
    const gutters = [...sidebar.parentElement.querySelectorAll(".gutter")];
    if (!gutters.length) return;
    if (sidebarOpen) addChevron(gutters[0], "«", "Collapse the file sidebar", () => setSidebar(false));
    if (previewOpen) {
      const last = gutters[gutters.length - 1];
      if (!sidebarOpen || gutters.length > 1) {
        addChevron(last, "»", "Collapse the PDF preview", () => setPreview(false));
      }
    }
  }

  function makeSplit() {
    if (split) { split.destroy(); split = null; }
    const previewOpen = !previewPane.classList.contains("hidden");
    const sidebarOpen = !sidebar.classList.contains("hidden");
    sidebarRestore.classList.toggle("hidden", sidebarOpen);
    previewRestore.classList.toggle("hidden", previewOpen);
    const panes = [];
    if (sidebarOpen) panes.push("#file-sidebar");
    panes.push("#editor-column");
    if (previewOpen) panes.push("#preview-pane");
    const key = SPLIT_KEY + (sidebarOpen ? "s" : "") + (previewOpen ? "p" : "");
    const editorColumn = document.getElementById("editor-column");
    if (panes.length < 2) {
      // no split: the editor is the only pane, so let it grow (Split.js isn't
      // managing widths and the column has no flex-grow of its own)
      editorColumn.style.width = "";
      editorColumn.style.flexGrow = "1";
      ad.view.requestMeasure();
      return;
    }
    editorColumn.style.flexGrow = "";
    const saved = JSON.parse(localStorage.getItem(key) || "null");
    const defaults =
      sidebarOpen && previewOpen ? [14, 44, 42] :
      sidebarOpen ? [16, 84] :
      [55, 45];
    const minSizes =
      sidebarOpen && previewOpen ? [120, 280, 220] :
      sidebarOpen ? [120, 320] :
      [320, 220];
    split = Split(panes, {
      sizes: saved && saved.length === panes.length ? saved : defaults,
      minSize: minSizes,
      gutterSize: 6,
      onDragEnd: (sizes) => {
        localStorage.setItem(key, JSON.stringify(sizes));
        ad.view.requestMeasure(); // CM6 re-measures after a container resize
        if (pdfDoc && lastPdfUrl) renderPdf(lastPdfUrl);
        else if (pdfDoc && cfg.pdfUrl) renderPdf(cfg.pdfUrl);
      },
    });
    decorateGutters(sidebarOpen, previewOpen);
    ad.view.requestMeasure();
  }
  function setSidebar(open) {
    sidebar.classList.toggle("hidden", !open);
    localStorage.setItem("atlas-editor-sidebar", open ? "1" : "0");
    makeSplit();
  }
  function setPreview(open) {
    previewPane.classList.toggle("hidden", !open);
    localStorage.setItem("atlas-editor-preview", open ? "1" : "0");
    makeSplit();
    if (open && cfg.pdfUrl && !pdfDoc) renderPdf(cfg.pdfUrl);
  }
  toggleBtn.addEventListener("click", () => setPreview(previewPane.classList.contains("hidden")));
  if (localStorage.getItem("atlas-editor-sidebar") === "0") sidebar.classList.add("hidden");
  // the PDF pane hosts Recompile, so it's shown by default unless explicitly collapsed
  // (setPreview(false) here too — the pane starts visible in the markup, so a bare
  // makeSplit() would silently undo a persisted collapse)
  setPreview(localStorage.getItem("atlas-editor-preview") !== "0");

  // Layout presets (#140): one-shot research-task arrangements on the View menu.
  // Each preset seeds the matching per-layout split key, then drives the same
  // setSidebar/setPreview machinery a manual toggle uses.
  const LAYOUT_PRESETS = {
    drafting: { sidebar: false, preview: false },
    reviewing: { sidebar: false, preview: true, sizes: [50, 50] },
    submitting: { sidebar: true, preview: true, sizes: [14, 44, 42] },
  };
  function applyLayout(name) {
    const preset = LAYOUT_PRESETS[name];
    if (!preset) return;
    if (preset.sizes) {
      const key = SPLIT_KEY + (preset.sidebar ? "s" : "") + (preset.preview ? "p" : "");
      localStorage.setItem(key, JSON.stringify(preset.sizes));
    }
    sidebar.classList.toggle("hidden", !preset.sidebar);
    localStorage.setItem("atlas-editor-sidebar", preset.sidebar ? "1" : "0");
    setPreview(preset.preview); // rebuilds the split with the seeded sizes
    if (preset.preview && pdfDoc && (lastPdfUrl || cfg.pdfUrl)) renderPdf(lastPdfUrl || cfg.pdfUrl);
    ad.focus();
  }
  for (const btn of document.querySelectorAll("[data-layout]")) {
    btn.addEventListener("click", () => applyLayout(btn.dataset.layout));
  }

  // Logs button toggles the diagnostics/error-log pane (Overleaf's "Logs and output files")
  document.getElementById("logs-toggle")?.addEventListener("click", () => {
    const panelEl = document.getElementById("diagnostics-panel");
    if (panelEl) panelEl.classList.toggle("hidden");
  });

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
      clearTimeout(timers.get(activeId));
      saveFile(activeId);
    }
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
      event.preventDefault();
      triggerCompile(); // Overleaf's recompile binding (#139)
    }
  });
})();
