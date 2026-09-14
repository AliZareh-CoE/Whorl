/** The keyboard cheat sheet (#425): every shortcut the app answers to, on one card.
 *  Press `?` anywhere outside a text field, or run "Keyboard shortcuts" from ⌘K. */
import { noticeDialog } from "../components/Dialog";
import { isDesktop } from "./external";

const MOD = typeof navigator !== "undefined" && /Mac|iPhone|iPad/.test(navigator.platform) ? "⌘" : "Ctrl";

type Group = { title: string; rows: [string, string][] };

export function shortcutGroups(): Group[] {
  return [
    { title: "Everywhere", rows: [[`${MOD} K`, "Ask Atlas anything — jump, capture, complete, run a verb"], ["?", "This sheet"], ...(isDesktop() ? [["F12 · Ctrl Shift I", "Open the web inspector"] as [string, string]] : [])] },
    { title: "Inbox", rows: [["j / k", "Move between captures"], ["↵", "File the highlighted capture where Atlas suggests"], ["1 – 5", "File as paper · today · note · milestone · decision"], ["x", "Dismiss"], ["s", "Snooze until tomorrow"], ["w", "Snooze until next week"], [`${MOD} ↵`, "Capture what you typed"]] },
    { title: "Notes", rows: [[`${MOD} S`, "Save now (autosave runs anyway)"], ["[[", "Link a note (completion)"], ["@", "Cite a paper (completion)"]] },
    { title: "Studio", rows: [[`${MOD} S`, "Save"], [`${MOD} ↵`, "Compile"], [`${MOD} ⇧ J`, "Locate the cursor in the PDF"], [`${MOD} ⇧ D`, "Go to definition — \\ref → its \\label, \\cite → its .bib entry"], [`${MOD} ⇧ F`, "Find in project"], [`${MOD} B`, "Toggle the sidebar"], [`${MOD} \\`, "Toggle the PDF preview"], [`${MOD} J`, "Toggle the problems panel"], [`${MOD} P`, "Quick open a file or section"], [`${MOD} ⇧ P`, "Actions palette — every editor action with its key"]] },
    { title: "Reader", rows: [["← / →", "Previous / next page"], ["select text", "Highlight it — the bar offers a note"]] },
  ];
}

export function showShortcuts(): Promise<void> {
  const groups = shortcutGroups();
  return noticeDialog({
    title: "Keyboard shortcuts",
    okLabel: "Got it",
    wide: true,
    body: (
      <div className="grid gap-x-8 gap-y-5 text-sm sm:grid-cols-2" data-testid="shortcuts-sheet">
        {groups.map((g) => (
          <section key={g.title}>
            <h3 className="mb-1.5 text-[11px] font-semibold uppercase tracking-wider text-stone-400">{g.title}</h3>
            <dl className="space-y-1">
              {g.rows.map(([keys, what]) => (
                <div key={keys + what} className="flex items-baseline gap-3">
                  <dt className="shrink-0 rounded border border-stone-300 bg-stone-50 px-1.5 py-0.5 font-mono text-[11px] text-stone-700 dark:border-stone-700 dark:bg-stone-800 dark:text-stone-200">{keys}</dt>
                  <dd className="text-stone-600 dark:text-stone-300">{what}</dd>
                </div>
              ))}
            </dl>
          </section>
        ))}
      </div>
    ),
  });
}

function inTextField(target: EventTarget | null): boolean {
  const el = target as HTMLElement | null;
  if (!el) return false;
  const tag = el.tagName;
  return tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || el.isContentEditable || !!el.closest(".cm-editor");
}

let installed = false;
export function installShortcutsKey(): void {
  if (installed) return;
  installed = true;
  window.addEventListener("keydown", (e) => {
    if (e.key !== "?" || e.metaKey || e.ctrlKey || e.altKey || inTextField(e.target)) return;
    e.preventDefault();
    void showShortcuts();
  });
}
