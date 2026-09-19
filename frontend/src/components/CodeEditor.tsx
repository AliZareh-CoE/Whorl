/**
 * Backlog 358 (#577): a small CodeMirror editor for a general text file in the Files pane —
 * line numbers, undo history, search, ⌘S to save, a language for Markdown and LaTeX, the
 * Observatory palette through the `.md-editor` variables. Deliberately not the Studio's
 * editor (cite completions, gutters, multi-file buffers): a data file or a readme needs a
 * calm text editor, not a LaTeX workbench. Mounted once per file; the parent re-keys.
 */
import { useEffect, useRef } from "react";
import { EditorState, Prec, type Extension } from "@codemirror/state";
import { EditorView, keymap, lineNumbers, highlightActiveLine, highlightActiveLineGutter, drawSelection } from "@codemirror/view";
import { defaultKeymap, history, historyKeymap, indentWithTab } from "@codemirror/commands";
import { markdown, markdownLanguage } from "@codemirror/lang-markdown";
import { search, searchKeymap } from "@codemirror/search";
import { latex } from "codemirror-lang-latex";
import { theme, highlight } from "../app/notes/MarkdownEditor";

const gutters = EditorView.theme({
  ".cm-gutters": { backgroundColor: "transparent", border: "none", color: "var(--md-dim)" },
  ".cm-activeLineGutter": { backgroundColor: "var(--md-active-line)" },
  ".cm-lineNumbers .cm-gutterElement": { padding: "0 10px 0 14px", minWidth: "2.4em" },
  ".cm-content": { padding: "0 14px 0 4px" },
});

/** The language for a file, by its name: Markdown and LaTeX highlight; everything else
 *  (.csv, .txt, .bib, .json…) is plain text with line numbers. */
export function languageFor(filename: string): Extension[] {
  const name = filename.toLowerCase();
  if (/\.(md|markdown)$/.test(name)) return [markdown({ base: markdownLanguage })];
  if (/\.tex$/.test(name)) return [latex()];
  return [];
}

export default function CodeEditor({ value, onChange, onSave, filename, className = "" }: { value: string; onChange: (v: string) => void; onSave?: () => void; filename: string; className?: string }) {
  const host = useRef<HTMLDivElement>(null);
  const onChangeRef = useRef(onChange); onChangeRef.current = onChange;
  const onSaveRef = useRef(onSave); onSaveRef.current = onSave; // ⌘S saves with the note as it is now, not as it was at mount

  useEffect(() => {
    if (!host.current) return;
    const extensions: Extension[] = [
      lineNumbers(), highlightActiveLineGutter(), history(), drawSelection(), highlightActiveLine(), EditorView.lineWrapping,
      ...languageFor(filename), theme, highlight, gutters, search(),
      Prec.highest(keymap.of([{ key: "Mod-s", run: () => { onSaveRef.current?.(); return true; } }])), // true: the browser's own save dialog never opens
      keymap.of([...searchKeymap, ...historyKeymap, ...defaultKeymap, indentWithTab]),
      EditorView.updateListener.of((u) => { if (u.docChanged) onChangeRef.current(u.state.doc.toString()); }),
    ];
    const view = new EditorView({ state: EditorState.create({ doc: value, extensions }), parent: host.current });
    view.focus();
    return () => view.destroy();
    // mount once per file; the parent re-keys on file change
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return <div ref={host} className={`md-editor h-[58vh] overflow-auto rounded border border-indigo-300 bg-white dark:border-stone-700 dark:bg-stone-900 ${className}`} data-testid="code-editor" />;
}
