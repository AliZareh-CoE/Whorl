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
import {
  autocompletion,
  closeBrackets,
  closeBracketsKeymap,
  completionKeymap,
  type CompletionContext,
  type CompletionResult,
} from "@codemirror/autocomplete";
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
import { vim } from "@replit/codemirror-vim";

export type EditorCfg = { citeKeys?: string[]; initialDoc?: string };

// --- comment gutter (Slice B): a 💬 marker on lines that carry comments -------------
class CommentMarker extends GutterMarker {
  toDOM() {
    const span = document.createElement("span");
    span.textContent = "💬";
    span.style.cursor = "pointer";
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
let currentDiagnostics: Diagnostic[] = [];
function diagnosticsLinter() {
  return linter(() => currentDiagnostics);
}

// Atlas-specific: \cite{key} completion from the manuscript's keys. (The whole-library
// B1 source with auto-link lands in Slice C.) Registered as language data so it MERGES with
// lang-latex's built-in command/env completion instead of overriding it.
function citeCompletionSource(citeKeys: string[]) {
  return (context: CompletionContext): CompletionResult | null => {
    const before = context.state.sliceDoc(
      context.state.doc.lineAt(context.pos).from,
      context.pos,
    );
    const cite = before.match(/\\\w*cite\w*\*?(?:\[[^\]]*\])*\{([^}]*)$/);
    if (!cite) return null;
    const frag = cite[1].split(",").pop()!.trim();
    return {
      from: context.pos - frag.length,
      options: citeKeys.map((k) => ({ label: k, type: "variable" })),
      validFor: /^[^},]*$/,
    };
  };
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
      lineNumbers(),
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
        override: [citeCompletionSource(cfg.citeKeys ?? []), latexCompletionSource(true)],
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
    ];
  }

  const newState = (doc: string) =>
    EditorState.create({ doc, extensions: buildExtensions() });

  const view = new EditorView({ state: newState(cfg.initialDoc ?? ""), parent: host });
  view.dom.style.minHeight = "72vh";

  // multi-file: keep an EditorState per file id; the live `view` holds the active one
  const states = new Map<number, EditorState>();
  let activeId = 0;
  states.set(activeId, view.state);

  return {
    view,
    getValue: () => view.state.doc.toString(),
    setValue: (s: string) =>
      view.dispatch({ changes: { from: 0, to: view.state.doc.length, insert: s } }),
    onChange: (fn) => changeListeners.push(fn),
    focus: () => view.focus(),
    setKeymap: (k: string) =>
      view.dispatch({ effects: keymapCompartment.reconfigure(k === "vim" ? [vim()] : []) }),
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

    setDiagnostics: (diags) => {
      const cm: Diagnostic[] = diags
        .filter((d) => d.line)
        .map((d) => {
          const ln = view.state.doc.line(Math.min(d.line, view.state.doc.lines));
          return {
            from: ln.from,
            to: ln.to,
            severity: (d.level === "error" ? "error" : "warning") as Diagnostic["severity"],
            message: d.message,
          };
        });
      currentDiagnostics = cm;
      view.dispatch(setDiagnostics(view.state, cm));
    },
  };
}

export default function mount(host: HTMLElement, cfg: EditorCfg) {
  return mountEditor(host, cfg);
}
