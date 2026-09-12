/* Atlas LaTeX editor — CodeMirror 6 core (Owner idea #28, Backlog #135, migration Slice A).
 *
 * A vanilla-JS (no React) island that Vite bundles. This slice stands up CM6 with single-file
 * parity for the editor MECHANICS and leans on codemirror-lang-latex's BUILT-IN command/
 * environment/math autocomplete, auto-close \end tags, and snippets — deleting the entire
 * hand-rolled CM5 snippet walker + four hint functions (rule #28: borrow, don't reinvent).
 * Only the Atlas-specific cite-key completion is custom. Multi-file buffers, the comment
 * gutter, the compile-diagnostics lint, and cite B1/B2 land in Slices B and C.
 */
import { defaultKeymap, history, historyKeymap, indentWithTab } from "@codemirror/commands";
import { latex, latexCompletionSource } from "codemirror-lang-latex";
import { boostFor, enclosingEnvironment } from "./context";
import { autocompletion, closeBrackets, closeBracketsKeymap, completionKeymap, type CompletionContext, type CompletionResult, type Completion, type CompletionSource } from "@codemirror/autocomplete";
import { type Diagnostic, linter, setDiagnostics } from "@codemirror/lint";
import { highlightSelectionMatches, openSearchPanel, search, searchKeymap } from "@codemirror/search";
import {
  Compartment,
  EditorState,
  RangeSet,
  StateEffect,
  StateField,
  type Extension,
} from "@codemirror/state";
import {
  EditorView,
  GutterMarker,
  gutter,
  highlightActiveLine,
  highlightActiveLineGutter,
  keymap,
  lineNumbers,
} from "@codemirror/view";
// Resizable panels (Owner idea #28: Split.js, MIT ~2KB, instead of hand-rolled drag math)
export { default as Split } from "split.js";

export type EditorCfg = {
  citeKeys?: string[];
  initialDoc?: string;
  initialFileId?: number; // the file id the initial doc belongs to (multi-file)
  citeLibraryUrl?: string; // B1: whole-library cite source + auto-link (Slice C)
  // #445: when the typed \cite fragment matches nothing, the completion offers to add a paper;
  // the host prompts for a DOI / arXiv id, adds + links it and calls `replace(key)`.
  onAddPaper?: (fragment: string, replace: (key: string) => void) => void;
  csrfToken?: string;
  extensions?: Extension[]; // studio: theme, extra keymaps
  fillHost?: boolean; // studio: the host is a flex child — fill it instead of 72vh
};

// Beyond-Overleaf B1/B2 (Slice C): \cite{} completes from the WHOLE project library; an
// unlinked paper shows "+ " and accepting it auto-creates the ManuscriptReference. Unknown
// \cite keys get a live amber cite-check diagnostic. The library loads async on mount.
type CiteRow = {
  reference_id?: number;
  key: string;
  title?: string;
  authors?: string;
  year?: number | null;
  linked?: boolean;
};
let citeLibrary: CiteRow[] = [];
let citeKnown = new Set<string>();
function loadCiteLibrary(cfg: EditorCfg) {
  citeKnown = new Set(cfg.citeKeys ?? []);
  if (!cfg.citeLibraryUrl) return;
  fetch(cfg.citeLibraryUrl)
    .then((r) => r.json())
    .then((d) => {
      citeLibrary = d.candidates || [];
      citeKnown = new Set([...(cfg.citeKeys ?? []), ...citeLibrary.map((c) => c.key)]);
    })
    .catch(() => {});
}
function autoLink(cfg: EditorCfg, referenceId: number) {
  if (!cfg.citeLibraryUrl) return;
  fetch(cfg.citeLibraryUrl, {
    method: "POST",
    headers: { "X-CSRFToken": cfg.csrfToken ?? "" },
    body: new URLSearchParams({ reference: String(referenceId) }),
  }).catch(() => {});
  const row = citeLibrary.find((c) => c.reference_id === referenceId);
  if (row) row.linked = true;
}

// --- comment gutter (Slice B): a chat-bubble marker on lines that carry comments ----
// inline stroke SVG, not an emoji (#146 — the rail's icon language, Owner #27 lesson)
class CommentMarker extends GutterMarker {
  toDOM() {
    const span = document.createElement("span");
    span.className = "comment-dot";
    span.innerHTML =
      '<svg width="11" height="11" viewBox="0 0 24 24" fill="none" stroke="currentColor" ' +
      'stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">' +
      '<path d="M21 11.5a8.4 8.4 0 0 1-8.5 8.3 8.9 8.9 0 0 1-3.8-.8L3 21l2-5.2a8 8 0 0 1-1-3.8A8.4 8.4 0 0 1 12.5 3.2 8.4 8.4 0 0 1 21 11.5Z"/></svg>';
    span.style.cursor = "pointer";
    span.style.color = "#4f46e5";
    return span;
  }
}
const setCommentLinesEffect = StateEffect.define<number[]>(); // 1-based line numbers
const commentMarkField = StateField.define<RangeSet<GutterMarker>>({
  create: () => RangeSet.empty,
  update(set, tr) {
    set = set.map(tr.changes);
    for (const e of tr.effects) {
      if (e.is(setCommentLinesEffect)) {
        const marks = e.value
          .filter((ln) => ln >= 1 && ln <= tr.state.doc.lines)
          .map((ln) => new CommentMarker().range(tr.state.doc.line(ln).from));
        set = RangeSet.of(marks, true);
      }
    }
    return set;
  },
});

// --- compile diagnostics (Slice B): push status into a CM6 linter ------------------
// Kept as line numbers, never as absolute positions: the linter re-runs after every change
// and on every file switch, and a position computed against one document is garbage against
// the next (#470 found phantom underlines from exactly that).
type LineDiag = { line: number; level: string; message: string };
let currentDiagnostics: LineDiag[] = []; // compile + lint diagnostics (pushed by the Studio)
function positioned(state: EditorState, diags: LineDiag[]): Diagnostic[] {
  return diags
    .filter((d) => d.line)
    .map((d) => {
      const ln = state.doc.line(Math.max(1, Math.min(d.line, state.doc.lines)));
      return {
        from: ln.from,
        to: ln.to,
        severity: (d.level === "error" ? "error" : "warning") as Diagnostic["severity"],
        message: d.message,
      };
    });
}
function diagnosticsLinter() {
  return linter((view) => [...positioned(view.state, currentDiagnostics), ...citeCheckDiagnostics(view.state)]);
}

// #459 (backlog #117): the library's LaTeX completions, re-ranked by the enclosing environment —
// \item first in a list, \includegraphics in a figure, \hline in a table, \label in math.
function contextAwareLatex(base: CompletionSource): CompletionSource {
  return async (context: CompletionContext) => {
    const result = await base(context);
    if (!result || !("options" in result)) return result;
    const env = enclosingEnvironment(context.state.sliceDoc(0, context.pos));
    if (!env) return result;
    return {
      ...result,
      options: result.options.map((o) => {
        const bonus = boostFor(env, o.label);
        return bonus ? { ...o, boost: Math.min(99, (o.boost ?? 0) + bonus) } : o;
      }),
    };
  };
}

const looksLikePaperId = (s: string) => /^(10\.\d{4,9}\/\S+|(?:arxiv:)?\d{4}\.\d{4,5}(?:v\d+)?)$/i.test(s.trim());

// B1: \cite{key} completes from the whole project library; accepting an unlinked paper
// auto-creates the ManuscriptReference link.
function citeCompletionSource(cfg: EditorCfg) {
  return (context: CompletionContext): CompletionResult | null => {
    const before = context.state.sliceDoc(
      context.state.doc.lineAt(context.pos).from,
      context.pos,
    );
    const cite = before.match(/\\\w*cite\w*\*?(?:\[[^\]]*\])*\{([^}]*)$/);
    if (!cite) return null;
    const frag = cite[1].split(",").pop()!.trim();
    const pool: CiteRow[] = citeLibrary.length
      ? citeLibrary
      : (cfg.citeKeys ?? []).map((k) => ({ key: k, linked: true }));
    // #445: filter here (key, title, authors) so an empty match can offer "add a paper"
    const needle = frag.toLowerCase();
    const hit = (c: CiteRow) =>
      !needle ||
      c.key.toLowerCase().includes(needle) ||
      (c.title ?? "").toLowerCase().includes(needle) ||
      (c.authors ?? "").toLowerCase().includes(needle);
    const matched = pool.filter(hit);
    const options: Completion[] = matched.map((c) => ({
      label: c.key,
      detail:
        (c.linked ? "" : "+ ") +
        [c.authors, c.year ? String(c.year) : "", c.title?.slice(0, 50)]
          .filter(Boolean)
          .join(" · "),
      type: "variable",
      apply: (view: EditorView, _c: unknown, from: number, to: number) => {
        view.dispatch({ changes: { from, to, insert: c.key }, selection: { anchor: from + c.key.length } });
        if (c.reference_id && !c.linked) autoLink(cfg, c.reference_id);
      },
    }));
    if (cfg.onAddPaper && (matched.length === 0 || looksLikePaperId(frag))) {
      options.push({
        label: looksLikePaperId(frag) ? `Add ${frag} to the library` : "Add a paper by DOI or arXiv id…",
        detail: matched.length === 0 ? "nothing in the library matches" : "fetch it, link it, cite it",
        type: "keyword",
        boost: -99,
        apply: (view: EditorView, _c: unknown, from: number, to: number) => {
          cfg.onAddPaper?.(frag, (key) => {
            view.dispatch({ changes: { from, to, insert: key }, selection: { anchor: from + key.length } });
          });
        },
      });
    }
    return { from: context.pos - frag.length, options, filter: false, validFor: /^[^},]*$/ };
  };
}

// B2: unknown \cite keys → live amber cite-check diagnostics (merged with compile diags).
const CITE_TOKEN = /\\\w*cite\w*\*?(?:\[[^\]]*\])*\{([^}]+)\}/g;
const citeCheckListeners: Array<(keys: string[]) => void> = [];
function citeCheckDiagnostics(state: EditorState): Diagnostic[] {
  if (!citeKnown.size) {
    citeCheckListeners.forEach((fn) => fn([]));
    return [];
  }
  const missing = new Set<string>();
  const out: Diagnostic[] = [];
  for (let i = 1; i <= state.doc.lines; i++) {
    const line = state.doc.line(i);
    let m: RegExpExecArray | null;
    CITE_TOKEN.lastIndex = 0;
    while ((m = CITE_TOKEN.exec(line.text)) !== null) {
      const keysStart = m.index + m[0].indexOf("{") + 1;
      let offset = keysStart;
      for (const raw of m[1].split(",")) {
        const key = raw.trim();
        const at = line.text.indexOf(key, offset);
        offset = at + key.length;
        if (key && !citeKnown.has(key)) {
          missing.add(key);
          out.push({
            from: line.from + at,
            to: line.from + at + key.length,
            severity: "warning",
            message: `Citation “${key}” isn't in your library. Add it from the library or by DOI.`,
          });
        }
      }
    }
  }
  citeCheckListeners.forEach((fn) => fn([...missing]));
  return out;
}

export type EditorAdapter = {
  view: EditorView;
  getValue: () => string;
  setValue: (s: string) => void;
  onChange: (fn: () => void) => void;
  focus: () => void;
  setKeymap: (k: string) => void;
  setFontSize: (px: string) => void;
  setSpellcheck: (on: boolean) => void;
  openFind: () => void;
  // --- cursor / lines (Slice B) ---
  getCursorLine: () => number; // 1-based
  gotoLine: (line: number) => void; // 1-based, scrolls + focuses
  insertAtCursor: (text: string, caretOffset?: number) => void;
  lineText: (line: number) => string; // 1-based
  lineCount: () => number;
  // --- multi-file buffers (Slice B): one EditorState per file id ---
  switchFile: (id: number) => void;
  fileValue: (id: number) => string;
  setFileValue: (id: number, text: string) => void;
  activeFile: () => number;
  // --- comment gutter (Slice B) ---
  setCommentLines: (lines: number[]) => void;
  onGutterClick: (fn: (line: number) => void) => void;
  // --- compile diagnostics (Slice B) ---
  setDiagnostics: (diags: { line: number; level: string; message: string }[]) => void;
  // --- cite-check (Slice C): fires with the unknown \cite keys after each lint ---
  onCiteCheck: (fn: (missingKeys: string[]) => void) => void;
  reloadCiteLibrary: () => void; // after add-by-DOI, refresh the completion pool
};

const keymapCompartment = new Compartment();

export function mountEditor(host: HTMLElement, cfg: EditorCfg): EditorAdapter {
  const changeListeners: Array<() => void> = [];
  const gutterClickListeners: Array<(line: number) => void> = [];
  const updateListener = EditorView.updateListener.of((u) => {
    if (u.docChanged) changeListeners.forEach((fn) => fn());
  });

  function buildExtensions(): Extension[] {
    return [
      lineNumbers({
        domEventHandlers: {
          mousedown(v, line) {
            const ln = v.state.doc.lineAt(line.from).number;
            gutterClickListeners.forEach((fn) => fn(ln));
            return false; // don't swallow — selection still works
          },
        },
      }),
      gutter({
        class: "cm-comment-gutter",
        markers: (v) => v.state.field(commentMarkField),
        domEventHandlers: {
          mousedown(v, line) {
            const ln = v.state.doc.lineAt(line.from).number;
            gutterClickListeners.forEach((fn) => fn(ln));
            return true;
          },
        },
      }),
      commentMarkField,
      highlightActiveLine(),
      highlightActiveLineGutter(),
      history(),
      closeBrackets(),
      EditorView.lineWrapping,
      // lang-latex: grammar + folding + bracket matching + auto-close \end tags + tooltips.
      // Autocomplete is composed explicitly so the Atlas cite source runs alongside the
      // library's built-in command/env/math source (rule #28: borrow the source, add cite).
      latex({ enableAutocomplete: false, autoCloseTags: true, enableTooltips: true }),
      autocompletion({
        override: [citeCompletionSource(cfg), contextAwareLatex(latexCompletionSource(true))],
      }),
      diagnosticsLinter(),
      search(),
      highlightSelectionMatches(),
      keymapCompartment.of([]),
      keymap.of([
        ...closeBracketsKeymap,
        ...defaultKeymap,
        ...historyKeymap,
        ...searchKeymap,
        ...completionKeymap,
        indentWithTab,
      ]),
      updateListener,
      ...(cfg.extensions ?? []),
    ];
  }

  const newState = (doc: string) =>
    EditorState.create({ doc, extensions: buildExtensions() });

  loadCiteLibrary(cfg);
  const view = new EditorView({ state: newState(cfg.initialDoc ?? ""), parent: host });
  if (cfg.fillHost) {
    view.dom.style.height = "100%";
  } else {
    view.dom.style.minHeight = "72vh";
  }

  // multi-file: keep an EditorState per file id; the live `view` holds the active one
  const states = new Map<number, EditorState>();
  let activeId = cfg.initialFileId ?? 0;
  states.set(activeId, view.state);

  return {
    view,
    getValue: () => view.state.doc.toString(),
    setValue: (s: string) =>
      view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: s } }),
    onChange: (fn) => changeListeners.push(fn),
    focus: () => view.focus(),
    setKeymap: (k: string) => {
      // vim is ~half the editor bundle but a minority preference — load it on demand
      // (#137); the chunk is local (islands/), so this still works fully offline
      if (k === "vim") {
        import("@replit/codemirror-vim").then(({ vim }) => {
          view.dispatch({ effects: keymapCompartment.reconfigure([vim()]) });
        });
      } else {
        view.dispatch({ effects: keymapCompartment.reconfigure([]) });
      }
    },
    setFontSize: (px: string) => {
      view.dom.style.fontSize = `${px}px`;
    },
    setSpellcheck: (on: boolean) => {
      view.contentDOM.setAttribute("spellcheck", on ? "true" : "false");
    },
    openFind: () => openSearchPanel(view),

    getCursorLine: () => view.state.doc.lineAt(view.state.selection.main.head).number,
    gotoLine: (line: number) => {
      const pos = view.state.doc.line(Math.min(Math.max(1, line), view.state.doc.lines)).from;
      view.dispatch({ selection: { anchor: pos }, scrollIntoView: true });
      view.focus();
    },
    insertAtCursor: (text: string, caretOffset?: number) => {
      const at = view.state.selection.main.head;
      view.dispatch({
        changes: { from: at, insert: text },
        selection: { anchor: at + (caretOffset ?? text.length) },
      });
      view.focus();
    },
    lineText: (line: number) => view.state.doc.line(line).text,
    lineCount: () => view.state.doc.lines,

    switchFile: (id: number) => {
      if (id === activeId) return;
      states.set(activeId, view.state); // stash the outgoing file's full state
      activeId = id;
      view.setState(states.get(id) ?? newState(""));
    },
    fileValue: (id: number) =>
      id === activeId ? view.state.doc.toString() : (states.get(id)?.doc.toString() ?? ""),
    setFileValue: (id: number, text: string) => {
      if (id === activeId) {
        view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: text } });
      } else {
        states.set(id, newState(text));
      }
    },
    activeFile: () => activeId,

    setCommentLines: (lines: number[]) =>
      view.dispatch({ effects: setCommentLinesEffect.of(lines) }),
    onGutterClick: (fn) => gutterClickListeners.push(fn),

    onCiteCheck: (fn) => citeCheckListeners.push(fn),
    reloadCiteLibrary: () => loadCiteLibrary(cfg),

    setDiagnostics: (diags) => {
      currentDiagnostics = diags;
      view.dispatch(setDiagnostics(view.state, [...positioned(view.state, diags), ...citeCheckDiagnostics(view.state)]));
    },
  };
}

export default function mount(host: HTMLElement, cfg: EditorCfg) {
  return mountEditor(host, cfg);
}
