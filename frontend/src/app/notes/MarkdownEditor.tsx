/* Notes editor v2 (2026-09-06): CodeMirror 6 with Markdown highlighting, `[[` note-link and
 * `@` cite completions served by the same /notes/suggest/ endpoint, ⌘B/⌘I/⌘K formatting and
 * ⌘S save. Colours come from CSS variables (`.md-editor` in app.css) so Observatory and Paper
 * both look right without re-mounting. */
import { useEffect, useRef } from "react";
import { EditorState, Prec, type Extension } from "@codemirror/state";
import { EditorView, keymap, placeholder as cmPlaceholder, highlightActiveLine, drawSelection } from "@codemirror/view";
import { defaultKeymap, history, historyKeymap, indentWithTab } from "@codemirror/commands";
import { markdown, markdownLanguage } from "@codemirror/lang-markdown";
import { HighlightStyle, syntaxHighlighting } from "@codemirror/language";
import { autocompletion, completionKeymap, type CompletionContext, type CompletionResult } from "@codemirror/autocomplete";
import { search, searchKeymap } from "@codemirror/search";
import { tags as t } from "@lezer/highlight";

export type Suggestion = { id: number; label: string; sublabel: string };
export type SuggestFn = (kind: "note" | "reference" | "tag", q: string) => Promise<Suggestion[]>;
export type MdHandle = { insert: (text: string) => void; focus: () => void; getValue: () => string };

const theme = EditorView.theme({
  "&": { backgroundColor: "transparent", color: "var(--md-fg)", fontSize: "13px" },
  ".cm-scroller": { fontFamily: "ui-monospace, SFMono-Regular, Menlo, Consolas, monospace", lineHeight: "1.65", padding: "12px 0" },
  ".cm-content": { padding: "0 20px", caretColor: "var(--md-accent)" },
  ".cm-cursor, .cm-dropCursor": { borderLeftColor: "var(--md-accent)" },
  "&.cm-focused": { outline: "none" },
  "&.cm-focused > .cm-scroller > .cm-selectionLayer .cm-selectionBackground, .cm-selectionBackground, ::selection": { backgroundColor: "var(--md-selection) !important" },
  ".cm-activeLine": { backgroundColor: "var(--md-active-line)" },
  ".cm-placeholder": { color: "var(--md-dim)", fontStyle: "normal" },
  ".cm-tooltip": { backgroundColor: "var(--md-panel)", border: "1px solid var(--md-line)", color: "var(--md-fg)", borderRadius: "10px", overflow: "hidden", boxShadow: "0 12px 30px rgba(0,0,0,0.18)" },
  ".cm-tooltip-autocomplete ul li": { padding: "5px 10px", fontFamily: "inherit" },
  ".cm-tooltip-autocomplete ul li[aria-selected]": { backgroundColor: "var(--md-selection)", color: "var(--md-fg)" },
  ".cm-completionDetail": { marginLeft: "8px", color: "var(--md-dim)", fontStyle: "normal" },
  ".cm-panels": { backgroundColor: "var(--md-panel)", color: "var(--md-fg)" },
  ".cm-searchMatch": { backgroundColor: "var(--md-match)" },
});
const highlight = syntaxHighlighting(HighlightStyle.define([
  { tag: t.heading1, color: "var(--md-heading)", fontWeight: "700", fontSize: "1.25em" },
  { tag: t.heading2, color: "var(--md-heading)", fontWeight: "700", fontSize: "1.12em" },
  { tag: [t.heading3, t.heading4, t.heading5, t.heading6], color: "var(--md-heading)", fontWeight: "700" },
  { tag: t.strong, fontWeight: "700", color: "var(--md-heading)" },
  { tag: t.emphasis, fontStyle: "italic" },
  { tag: t.strikethrough, textDecoration: "line-through", color: "var(--md-dim)" },
  { tag: [t.link, t.url], color: "var(--md-accent)", textDecoration: "underline" },
  { tag: t.monospace, color: "var(--md-code)", backgroundColor: "var(--md-code-bg)", borderRadius: "3px" },
  { tag: t.quote, color: "var(--md-dim)", fontStyle: "italic" },
  { tag: [t.list, t.processingInstruction, t.meta], color: "var(--md-dim)" },
  { tag: t.contentSeparator, color: "var(--md-dim)" },
]));

function wrapSelection(view: EditorView, left: string, right = left): boolean {
  const { from, to } = view.state.selection.main;
  const inner = view.state.sliceDoc(from, to);
  view.dispatch({ changes: { from, to, insert: `${left}${inner}${right}` }, selection: { anchor: from + left.length, head: from + left.length + inner.length } });
  return true;
}

export default function MarkdownEditor({ value, onChange, onSave, suggest, placeholder, className = "", handle }: { value: string; onChange: (v: string) => void; onSave?: () => void; suggest: SuggestFn; placeholder?: string; className?: string; handle?: (h: MdHandle | null) => void }) {
  const host = useRef<HTMLDivElement>(null);
  const viewRef = useRef<EditorView | null>(null);
  const onChangeRef = useRef(onChange); onChangeRef.current = onChange;
  const onSaveRef = useRef(onSave); onSaveRef.current = onSave;
  const suggestRef = useRef(suggest); suggestRef.current = suggest;

  useEffect(() => {
    if (!host.current) return;
    // `[[Title` → note titles (+ "new note" when nothing matches); `@key` → cite keys
    const wikiSource = async (ctx: CompletionContext): Promise<CompletionResult | null> => {
      const m = ctx.matchBefore(/\[\[[^\]\n]*/);
      if (!m) return null;
      const q = m.text.slice(2);
      const rows = await suggestRef.current("note", q);
      const options = rows.map((r) => ({ label: r.label, detail: r.sublabel, type: "text", apply: `[[${r.label}]]` }));
      if (q.trim() && !rows.some((r) => r.label.toLowerCase() === q.trim().toLowerCase())) options.push({ label: q.trim(), detail: "new note — created when you first open the link", type: "text", apply: `[[${q.trim()}]]` });
      return { from: m.from, options, filter: false, validFor: /^\[\[[^\]\n]*$/ };
    };
    const citeSource = async (ctx: CompletionContext): Promise<CompletionResult | null> => {
      const m = ctx.matchBefore(/(?:^|[\s(])@[\w:.-]*/);
      if (!m) return null;
      const at = m.text.indexOf("@");
      const q = m.text.slice(at + 1);
      const rows = await suggestRef.current("reference", q);
      return { from: m.from + at, options: rows.map((r) => ({ label: `@${r.label}`, detail: r.sublabel, type: "keyword", apply: `@${r.label} ` })), filter: false, validFor: /^@[\w:.-]*$/ };
    };
    // #504: `#tag` → the project's tags (most used first); a heading (`# `) never triggers
    const tagSource = async (ctx: CompletionContext): Promise<CompletionResult | null> => {
      const m = ctx.matchBefore(/(?:^|[\s(])#[A-Za-z][\w/-]*/);
      if (!m) return null;
      const hash = m.text.indexOf("#");
      const q = m.text.slice(hash + 1);
      const rows = await suggestRef.current("tag", q);
      if (!rows.length) return null;
      return { from: m.from + hash, options: rows.map((r) => ({ label: `#${r.label}`, detail: r.sublabel, type: "keyword", apply: `#${r.label} ` })), filter: false, validFor: /^#[\w/-]*$/ };
    };
    const extensions: Extension[] = [
      history(), drawSelection(), highlightActiveLine(), EditorView.lineWrapping,
      markdown({ base: markdownLanguage }), theme, highlight, search(),
      cmPlaceholder(placeholder ?? "Write in Markdown."),
      autocompletion({ override: [wikiSource, citeSource, tagSource], activateOnTyping: true, icons: false }),
      Prec.highest(keymap.of([
        { key: "Mod-s", run: () => { onSaveRef.current?.(); return true; } },
        { key: "Mod-b", run: (v) => wrapSelection(v, "**") },
        { key: "Mod-i", run: (v) => wrapSelection(v, "_") },
        { key: "Mod-k", run: (v) => { const { from, to } = v.state.selection.main; const inner = v.state.sliceDoc(from, to) || "text"; v.dispatch({ changes: { from, to, insert: `[${inner}](url)` }, selection: { anchor: from + inner.length + 3, head: from + inner.length + 6 } }); return true; } },
      ])),
      keymap.of([...completionKeymap, ...searchKeymap, ...historyKeymap, ...defaultKeymap, indentWithTab]),
      EditorView.updateListener.of((u) => { if (u.docChanged) onChangeRef.current(u.state.doc.toString()); }),
    ];
    const view = new EditorView({ state: EditorState.create({ doc: value, extensions }), parent: host.current });
    viewRef.current = view;
    handle?.({ insert: (text) => { const at = view.state.selection.main.head; view.dispatch({ changes: { from: at, insert: text }, selection: { anchor: at + text.length } }); view.focus(); }, focus: () => view.focus(), getValue: () => view.state.doc.toString() });
    return () => { handle?.(null); view.destroy(); viewRef.current = null; };
    // mount once per note; the parent re-keys on note change
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return <div ref={host} className={`md-editor min-h-[22rem] ${className}`} data-testid="md-editor" />;
}
