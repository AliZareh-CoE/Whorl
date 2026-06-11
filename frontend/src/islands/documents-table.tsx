/** Island entry: mounts the shared DocumentsTable over the server-rendered fallback. */
import { createRoot } from "react-dom/client";
import { DocumentsTable } from "../components/DocumentsTable";

type Props = Parameters<typeof DocumentsTable>[0];

export default function mount(el: HTMLElement, props: Props) {
  el.innerHTML = ""; // replace the server-rendered fallback table
  createRoot(el).render(<DocumentsTable {...props} />);
}
