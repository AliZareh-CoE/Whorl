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

  const textarea = document.getElementById("latex-source");
  const editor = CodeMirror(document.getElementById("editor-host"), {
    value: textarea.value || "% Start writing. \\cite{ } autocompletes from this manuscript's bibliography.\n",
    mode: "stex",
    lineNumbers: true,
    lineWrapping: true,
    viewportMargin: Infinity,
    gutters: ["CodeMirror-linenumbers", "CodeMirror-lint-markers"],
    lint: {
      getAnnotations: (text, opts, cm) => (DIAGNOSTICS || [])
        .filter((d) => d.line)
        .map((d) => ({
          from: CodeMirror.Pos(d.line - 1, 0),
          to: CodeMirror.Pos(d.line - 1, (cm.getLine(d.line - 1) || " ").length),
          severity: d.level === "error" ? "error" : "warning",
          message: d.message,
        })),
      lintOnChange: false,
    },
  });
  editor.getWrapperElement().style.minHeight = "55vh";
  window.editor = editor; // console + test access

  // --- cite-key autocomplete -------------------------------------------------
  function citeHint(cm) {
    const cursor = cm.getCursor();
    const lineStart = cm.getLine(cursor.line).slice(0, cursor.ch);
    const match = lineStart.match(/\\\w*cite\w*\*?(?:\[[^\]]*\])*\{([^}]*)$/);
    if (!match) return null;
    const fragment = match[1].split(",").pop().trim();
    const from = { line: cursor.line, ch: cursor.ch - fragment.length };
    const list = CITE_KEYS.filter((k) => k.startsWith(fragment));
    return { list: list.length ? list : CITE_KEYS, from, to: cursor };
  }
  editor.on("inputRead", (cm, change) => {
    if (change.text[0] === "{" || /[\w,]/.test(change.text[0])) {
      const lineStart = cm.getLine(cm.getCursor().line).slice(0, cm.getCursor().ch);
      if (/\\\w*cite\w*\*?(?:\[[^\]]*\])*\{[^}]*$/.test(lineStart)) {
        cm.showHint({ hint: citeHint, completeSingle: false });
      }
    }
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
        (d.line ? `<span class="font-mono text-xs text-stone-400">L${d.line}</span>` : "") +
        '<span class="min-w-0 flex-1 truncate text-xs text-stone-700"></span>';
      li.lastChild.textContent = d.message;
      if (d.line) {
        li.addEventListener("click", () => {
          editor.setCursor({ line: d.line - 1, ch: 0 });
          editor.focus();
          editor.scrollIntoView({ line: d.line - 1, ch: 0 }, 120);
        });
      }
      list.appendChild(li);
    }
  }
  renderDiagnostics(DIAGNOSTICS);

  // --- autosave (epic slice 2) ------------------------------------------------
  const saveStatus = document.getElementById("save-status");
  let saveTimer = null;
  let dirty = false;

  async function save() {
    dirty = false;
    saveStatus.textContent = "Saving…";
    try {
      const res = await fetch(cfg.editorUrl, {
        method: "POST",
        headers: { "X-CSRFToken": csrfToken(), "X-SPA": "1" },
        body: new URLSearchParams({ latex_source: editor.getValue() }),
      });
      if (!res.ok) throw new Error();
      const data = await res.json();
      const t = new Date().toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
      const cite = data.cite && data.cite.missing_from_bib
        ? ` · ${data.cite.missing_from_bib} missing cite${data.cite.missing_from_bib === 1 ? "" : "s"}`
        : "";
      saveStatus.textContent = `Saved ${t}${cite}`;
      if (autoCompile.checked) triggerCompile();
    } catch {
      dirty = true;
      saveStatus.textContent = "⚠ not saved — retrying";
      setTimeout(save, 4000);
    }
  }
  editor.on("change", (cm, change) => {
    if (change.origin === "setValue") return;
    dirty = true;
    saveStatus.textContent = "…";
    clearTimeout(saveTimer);
    saveTimer = setTimeout(save, 2000);
  });
  window.addEventListener("beforeunload", (e) => {
    if (dirty) { e.preventDefault(); e.returnValue = ""; }
  });

  // --- compile without reload (epic slice 2) ----------------------------------
  const previewPane = document.getElementById("preview-pane");
  const previewFrame = document.getElementById("preview-frame");
  const previewEmpty = document.getElementById("preview-empty");
  const previewStatus = document.getElementById("preview-status");
  const toggleBtn = document.getElementById("toggle-preview");
  const autoCompile = document.getElementById("auto-compile");

  function setPreview(open) {
    previewPane.classList.toggle("hidden", !open);
    localStorage.setItem("atlas-editor-preview", open ? "1" : "0");
  }
  toggleBtn.addEventListener("click", () => setPreview(previewPane.classList.contains("hidden")));
  if (localStorage.getItem("atlas-editor-preview") === "1" || cfg.hasPdf) setPreview(true);

  autoCompile.checked = localStorage.getItem("atlas-editor-autocompile") === "1";
  autoCompile.addEventListener("change", () => {
    localStorage.setItem("atlas-editor-autocompile", autoCompile.checked ? "1" : "0");
  });

  let polling = null;
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
        renderDiagnostics(data.diagnostics || []);
        if (data.status === "ok" && data.pdf_url) {
          previewStatus.textContent = `✓ compiled ${new Date(data.compiled_at).toLocaleTimeString()}`;
          previewFrame.src = `${data.pdf_url}?t=${Date.parse(data.compiled_at)}#toolbar=0`;
          previewFrame.classList.remove("hidden");
          previewEmpty.classList.add("hidden");
        } else if (data.status === "failed") {
          previewStatus.textContent = "✕ compile failed — see problems below";
          previewEmpty.textContent = "Compile failed — the problems panel below has details.";
          previewEmpty.classList.remove("hidden");
          previewFrame.classList.add("hidden");
        }
      })
      .catch(() => {});
  }
  async function triggerCompile() {
    setPreview(true);
    previewStatus.textContent = "⏳ compiling…";
    try {
      await fetch(cfg.compileUrl, {
        method: "POST",
        headers: { "X-CSRFToken": csrfToken(), "X-SPA": "1" },
        body: new URLSearchParams({ latex_source: editor.getValue() }),
      });
      if (!polling) polling = setInterval(poll, 1500);
    } catch {
      previewStatus.textContent = "⚠ could not start compile";
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
