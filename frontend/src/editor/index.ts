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
import { highlightSelectionMatches, openSearchPanel, search, searchKeymap } from "@codemirror/search";
import { Compartment, EditorState, type Extension } from "@codemirror/state";
import {
  EditorView,
  highlightActiveLine,
  highlightActiveLineGutter,
  keymap,
  lineNumbers,
} from "@codemirror/view";
import { vim } from "@replit/codemirror-vim";

export type EditorCfg = { citeKeys?: string[]; initialDoc?: string };

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
};

const keymapCompartment = new Compartment();

export function mountEditor(host: HTMLElement, cfg: EditorCfg): EditorAdapter {
  const changeListeners: Array<() => void> = [];
  const updateListener = EditorView.updateListener.of((u) => {
    if (u.docChanged) changeListeners.forEach((fn) => fn());
  });

  const extensions: Extension[] = [
    lineNumbers(),
    highlightActiveLine(),
    highlightActiveLineGutter(),
    history(),
    closeBrackets(),
    EditorView.lineWrapping,
    // lang-latex: grammar + folding + bracket matching + auto-close \end tags + tooltips.
    // Autocomplete is composed explicitly below so the Atlas cite source runs alongside the
    // library's built-in command/env/math source (rule #28: borrow the source, add cite).
    latex({ enableAutocomplete: false, autoCloseTags: true, enableTooltips: true }),
    autocompletion({
      override: [citeCompletionSource(cfg.citeKeys ?? []), latexCompletionSource(true)],
    }),
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

  const view = new EditorView({
    state: EditorState.create({ doc: cfg.initialDoc ?? "", extensions }),
    parent: host,
  });
  view.dom.style.minHeight = "72vh";

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
  };
}

export default function mount(host: HTMLElement, cfg: EditorCfg) {
  return mountEditor(host, cfg);
}
