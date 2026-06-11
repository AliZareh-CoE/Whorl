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
      await fetch(cfg.compileUrl, {
        method: "POST",
        headers: { "X-CSRFToken": csrfToken(), "X-SPA": "1" },
        body: new URLSearchParams({ latex_source: editor.getValue() }),
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
